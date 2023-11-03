#!/bin/bash
#
#
LIST=$(mktemp -t .vcgen.list.XXXXXX)

RESULT=./data/raspi.libs.tar.gz

build_list() {
    OLD_PWD=`pwd`
    cd /
    find lib/ -name "*libvcos.so*"
    find lib/ -name "*libvchiq_arm.so*"
    find usr/ -name "vcgencmd"
    cd $OLD_PWD
}


if [ -f "$RESULT" ]; then
    echo "vcgen package '$RESULT' already exists"
else
    echo "build $RESULT"

    build_list > $LIST

    tar czf $RESULT --directory=/ -T $LIST
    if [ $? -eq 0 ]; then
	echo "done"
    else
	echo "failed"
    fi
fi

rm -f $LIST

