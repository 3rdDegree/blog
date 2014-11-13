#!/usr/bin/python
import getpass
import os
import random
import re
import string
import subprocess
import sys
import tempfile

class JarSigner:

    def __init__(self, storepass, storealias, jardir):
        self.storepass  = storepass
        self.storealias = storealias
        self.jardir     = jardir

    def get_inner_jarname(self):
        # Return None if <> 1 jar in the dir
        jarname = None

        files = os.listdir(os.getcwd())

        if len(files) == 1:
            if files[0].endswith(".jar"):
                jarname = files[0]
        return jarname

    def handle_pack200(self, javafile):
        print "[*] PACK200 processor called: %s" % javafile

        (jarname, ext) = javafile.split(".pack.gz")
        tmpdir = ''.join(random.choice(string.hexdigits) for n in xrange(6))
        os.mkdir(tmpdir)

        subprocess.Popen("unpack200.exe %s %s\\%s" % (javafile, tmpdir, jarname), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        os.chdir(tmpdir)
        # Should only be 1 jar in this directory
        if not os.path.isfile(jarname):
            print "[-] Could not unpack jar file."
            return False

        self.handle_jar(jarname)

        # Pack the jar
        subprocess.Popen("pack200.exe %s %s" % (javafile, jarname), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        # Overwrite pack200 file with new one
        subprocess.Popen("move /y %s ..\\%s" % (javafile, javafile), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        # Cleanup
        os.chdir(self.jardir)
        subprocess.Popen("rmdir /s /q %s" % tmpdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        return True

    def handle_jarjar(self, javafile):
        print "[*] JARJAR processor called: %s" % javafile

        tmpdir = ''.join(random.choice(string.hexdigits) for n in xrange(6))
        os.mkdir(tmpdir)
        os.chdir(tmpdir)

        # Unzip jarjar
        subprocess.Popen("jar.exe -xf ..\\%s" % javafile, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        jarname = self.get_inner_jarname()

        if not jarname:
            print "[-] Unpacked file doesn't contain exactly 1 jar. Quitting."
            return False

        self.handle_jar(jarname)

        # Pack the jar
        subprocess.Popen("jar.exe -cMf %s %s" % (javafile, jarname), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        # Overwrite jarjar file with new one
        subprocess.Popen("move /y %s ..\\%s" % (javafile, javafile), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        # Cleanup
        os.chdir(self.jardir)
        subprocess.Popen("rmdir /s /q %s" % tmpdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        return True

    def handle_jar(self, javafile):

        print "[*] JAR processor called: %s" % javafile

        (jarname, ext) = javafile.split(".jar")

        # Remove old directory, if present
        if os.path.isdir(jarname):
            subprocess.Popen("rmdir /s /q %s" % jarname, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        # Unpack jar
        os.mkdir(jarname)
        currjardir = os.getcwd()
        os.chdir(jarname)
        subprocess.Popen("jar.exe -xf ..\\%s" % javafile, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        #Delete manifest (old signatures) and old Jar
        subprocess.Popen("rmdir /s /q META-INF", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()
        os.chdir(currjardir)
        os.unlink(javafile)

        # Create new jar
        jarcmd = "jar.exe -cfm %s %s -C %s ." % (javafile, self.manifest_file, jarname)
        subprocess.Popen(jarcmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        # Sign new jar
        jarsignercmd = "jarsigner.exe -storepass %s %s %s" % (self.storepass, javafile, self.storealias)
        subprocess.Popen(jarsignercmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()

        # Cleanup
        subprocess.Popen("rmdir /s /q %s" % jarname, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).wait()
        return True

    def create_jar_manifest(self):
        print "[*] Creating manifest for JAR files"
        app_name  = raw_input("Enter the name of the application: ")
        site_list = raw_input("Enter the sites (space seperated) which will serve these JAR files (e.g. '*.mydomain.com static.mydmn.com'): ")

        manifest_content = [
            "Manifest-Version: 1.0",
            "Trusted-Library: true",
            "Application-Name: %s" % app_name,
            "Permissions: all-permissions",
            "Caller-Allowable-Codebase: %s 127.0.0.1" % site_list,
        ]

        with tempfile.NamedTemporaryFile(delete=False) as manifest:
            manifest.write("\n".join(manifest_content))
            manifest.write("\n\n")  # write extra lines to appease jar.exe
            manifest.flush()
            self.manifest_file = manifest.name

    def run(self):
        self.create_jar_manifest()

        # List directory, process each file
        os.chdir(self.jardir)

        for javafile in os.listdir(self.jardir):

            if os.path.isfile(javafile):

                if javafile.find(".pack.gz") > 0:
                    if not self.handle_pack200(javafile):
                        break

                elif javafile.find(".jarjar") > 0:
                    if not self.handle_jarjar(javafile):
                        break

                elif javafile.find(".jar") > 0:
                    if not self.handle_jar(javafile):
                        break

        os.unlink(self.manifest_file)
        print "[+] Done"

def get_storeinfo():
    storepass  = None
    storealias = None

    for tries in range(5):
        storepass = getpass.getpass("Enter keystore password: ")
        login_cmd = "keytool.exe -list"
        login_proc = subprocess.Popen(login_cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Send the keystore password to the keytool command
        login_result = login_proc.communicate(input=storepass)[0]

        if not "password was incorrect" in login_result:
            aliases = re.findall("\n(.*?),.*?, PrivateKeyEntry", login_result)
            storealias = get_storealias(aliases)
            break
        else:
            print "[-] The password is not correct"
            print
            storepass  = None

    return storepass, storealias

def get_storealias(aliases):
    if len(aliases) == 1:
        return aliases[0]

    elif len(aliases) > 1:
        alias_menu = ["%d. %s" % (n+1, alias) for n, alias in enumerate(aliases)]
        print "\n".join(alias_menu)
        selection = raw_input("Select alias [1]: ")

        try:
            return aliases[selection]
        except:
            return aliases[0]


if __name__=="__main__":

    storepass  = None
    storealias = None
    jardir     = None

    try:
        jardir = sys.argv[1]
        if not os.path.isdir(jardir):
            print "[-] Directory %s not found." % jardir
            raise Exception

        storepass, storealias = get_storeinfo()

        if storepass is None:
            print "[-] Too many invalid login attempts."
            raise Exception

        if storealias is None:
            print "[-] No stores contain a private key for signing!"
            raise Exception

    except:
        print """
Signs jars, jarjars, and jar.pack.gz files. Note: %JDK_PATH%\\bin must
be in your %PATH% for this to work.

Usage:
    jarsigner.py <jar_directory>

Example:
    jarsigner.py C:\Temp\jars
        """
        sys.exit()

    jarsigner = JarSigner(storepass, storealias, jardir)
    jarsigner.run()
