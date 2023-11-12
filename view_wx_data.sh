#!/bin/bash


. /opt/docker/wospi/.env

docker exec -ti ${IMAGE_NAME} bash -c "sudo su - wx"

