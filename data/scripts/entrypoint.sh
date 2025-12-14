#!/bin/bash
#

#set -eu
set -o pipefail

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH

RUNUSER=wospi
HOMEDIR=${HOMEDIR:-/home/$RUNUSER}

PROG=wospi.py
RUNSCR=$HOMEDIR/$PROG

#------------------------
#
logMSG() {
    #DT=$(date +'%Y-%m-%e %H:%M:%S')
    DT=$(date +'%a %b %e %T %Y')
    echo "$DT $1: $2"
}

run_cron() {
    logMSG INFO "#1 start cron daemon"
    sudo /usr/sbin/service cron start
}

run_wospi() {
    logMSG INFO "#2 start wospi"

    PATH=$PATH:$HOMEDIR:$HOMEDIR/tools
    cd $HOMEDIR

    #sudo /etc/init.d/wospi start
    /usr/bin/python3 $RUNSCR 
    el=$?

    if [ $el -ne 0 ]; then
	logMSG ERROR "failed to start wospi"
	exit 1
    else
	PID=$(ps -ef|grep wospi.p[y] | awk '{print $2}')
	logMSG INFO "wospi is running with PID $PID"
	ps -ef|grep pytho[n]
    fi
}


#------------------------
#
case "$1" in
	cron)
	    run_cron
	    ;;
	wospi)
	    run_cron
	    run_wospi
	    ;;
	bash)
	    exec "$@"
	    ;;
	*)
	    if [ -$# -eq 0]; then
		logMSG WARN "${0##*/} no parameter given."
	    else
		logMSG INFO "${0##*/} called with unknown parameter: '${@}'"
	    fi
	    logMSG INFO "usage: ${0##*/} { cron|wospi|bash }"
	    exit 1
	    ;;
esac

exit 0

