#!/bin/bash

#TAG=${1:-0.7}

. .env

export CONT_VER=$TAG

echo "docker build --build-arg $CONT_VER -t ${IMAGE_NAME}:$TAG"
docker build --build-arg $CONT_VER -t ${IMAGE_NAME}:$TAG  .

