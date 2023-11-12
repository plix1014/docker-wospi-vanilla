#!/bin/bash

. .env

export CONT_VER=$TAG

if [ $# -ne 1 ]; then
    echo
    echo "usage: ${0##*/} <inc|full>"
    echo
    exit 1
fi

OPTS=

if [ "$1" = "full" ]; then
    OPTS="--no-cache"
fi

echo "docker build $OPTS --target $TARGET --build-arg="CONT_VER=$CONT_VER" -t ${IMAGE_NAME}:$TAG"
time docker build $OPTS --target $TARGET --build-arg="CONT_VER=$CONT_VER" -t ${IMAGE_NAME}:$TAG  .

