# NOTE: replace address@example.com with the intended RECIPIENT address
# Refer to the WOSPi documentation for further configuration details.
# 20160116/TMJ

#!/bin/bash

ZIFILE=/var/tmp/wxdata.zip

SOURCEDATA=$(grep ^CSVPATH $HOMEDIR/config.py \
    | awk -F"=" '{print $2}' \
    | sed -e 's, ,,g' -e "s,',,g")

zip $ZIPFILE $SOURCEDATA/*

if [ -n "$MAILTO" ]; then
    echo "Please find a backup archive of WOSPi weather observations attached." \
	| mutt $MAILTO -s "WOSPi weather data - BACKUP" -a $ZIPFILE
else
    echo "WARN: MAILTO variable not set."
fi


[ -f "$ZIPFILE" ] && rm $ZIPFILE

