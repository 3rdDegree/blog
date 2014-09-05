#!/bin/bash
SCRIPT_XSESSION=~/.xsession 
SCRIPT_SPLASH=/etc/init.d/asplashscreen 
INITTAB=/etc/inittab
RDP_HOST=192.168.0.100

# Update/install packages
sudo apt-get update && sudo apt-get upgrade 
sudo apt-get -y install rdesktop fbi 
sudo apt-get -y install opensc libpcsclite1 pcscd pcsc-tools coolkey

# Kiosk setup
cat > $SCRIPT_XSESSION <<ENDSCRIPT 
#!/bin/bash 

xset s off 
xset -dpms 
while true; do 
    # Reset the user's home dir to known good state 
    # rsync -qr --delete --exclude='.Xauthority' /opt/kiosk/ $HOME/ 
    rdesktop -z -T MOBILE -u administrator -x l -P -f -r sound:remote -r scard $RDP_HOST 
done 
ENDSCRIPT

# Display spash screen
sudo cat > $SCRIPT_SPLASH <<ENDSCRIPT 
#! /bin/sh 
### BEGIN INIT INFO 
# Provides:          asplashscreen 
# Required-Start: 
# Required-Stop: 
# Should-Start: 
# Default-Start:     S 
# Default-Stop: 
# Short-Description: Show custom splashscreen 
# Description:       Show custom splashscreen 
### END INIT INFO 

do_start () { 

    /usr/bin/fbi -T 1 -noverbose -a /etc/splash.png 
    exit 0 
} 

case "$1" in 
  start|"") 
    do_start 
    ;; 
  restart|reload|force-reload) 
    echo "Error: argument '$1' not supported" >&2 
    exit 3 
    ;; 
  stop) 
    # No-op 
    ;; 
  status) 
    exit 0 
    ;; 
  *) 
    echo "Usage: asplashscreen [start|stop]" >&2 
    exit 3 
    ;; 
esac 
ENDSCRIPT

# Configure splash script & image
sudo chmod a+x $SCRIPT_SPLASH 
sudo insserv $SCRIPT_SPLASH 
sudo cp ./splash.png /etc/splash.png

# Auto-login the user
mv $INITTAB $INITTAB.old 
sed 's/\(1:2345:respawn:\).*/\1\/bin\/login -f pi tty1 <\/dev\/tty1 >\/dev\/tty1 2>\&1/' $INITTAB.old > $INITTAB 
rm -f $INITTAB.old

