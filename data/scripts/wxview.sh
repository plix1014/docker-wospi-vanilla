#!/bin/bash
#
# display weather data output on tty6 (ref. inittab)
# user 'wx' will have the default shell set to this script
# sed removes HTML formatting and special &xxx; characters
#
clear
#
echo 'Weather data will appear here shortly. Please be patient.'

WX=/var/tmp/wxdata.txt


while : 
do
    if [ -f "$WX" ]
    then
	tail -f -n 50 "$WX" | sed -e 's/&amp;/and/g;s/<[^>]*>//g;s/&[^;]*;/ /g'
    else
	echo
	echo "ERROR: file '$WX' not found. aborting..."
	echo
	break
    fi
    sleep 1
done

