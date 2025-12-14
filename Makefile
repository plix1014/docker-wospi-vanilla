# Load .env variables if present
ifneq ("$(wildcard .env)","")
	include .env
	export $(shell sed 's/=.*//' .env)
endif

# Fallback defaults
TAG        ?= latest
OPTS       ?=
TARGET     ?= image-prod
CONT_VER   ?= 0.1.0
IMAGE_NAME ?= wospi
SLIM_IMAGE ?= $(IMAGE_NAME)-slim:$(BASE_TAG)
BASE_IMAGE ?= $(IMAGE_NAME)-base:$(BASE_TAG)
REGISTRY   ?= myrepo

# Recalculate full tag
TAG        := $(TAGNR)-$(TARGET)
CONT_VER   := $(TAG)
OS_TAG     := $(OS_TAG)

REGISTRY   := $(REPO_USER_USER)

# Lowercase everything
REGISTRY   := $(shell echo $(REGISTRY) | tr A-Z a-z)
TAG        := $(shell echo $(TAG) | tr A-Z a-z)
OS_TAG     := $(shell echo $(OS_TAG) | tr A-Z a-z)

# Compose image names
SLIM_IMAGE_NAME := $(IMAGE_NAME)-slim
SLIM_IMAGE := $(REGISTRY)/$(SLIM_IMAGE_NAME):$(OS_TAG)

BASE_IMAGE_NAME := $(IMAGE_NAME)-base
BASE_IMAGE := $(REGISTRY)/$(BASE_IMAGE_NAME):$(OS_TAG)

APP_IMAGE  := $(REGISTRY)/$(IMAGE_NAME):$(TAG)

.PHONY: all base app push-base push-app shell clean help

all: slim base app

slim:
	docker build $(OPTS) \
		--build-arg CONT_VER=$(OS_TAG) \
		--build-arg OS_TAG=$(OS_TAG) \
		-t $(SLIM_IMAGE) \
		-f Dockerfile.slim .

base:
	DOCKER_BUILDKIT=1 docker build $(OPTS) \
		--build-arg CONT_VER=$(OS_TAG) \
		--build-arg OS_TAG=$(OS_TAG) \
		-t $(BASE_IMAGE) \
		-f Dockerfile.base .

app:
	DOCKER_BUILDKIT=1 docker build $(OPTS) \
		--target $(TARGET) \
		--build-arg CONT_VER=$(CONT_VER) \
		--build-arg OS_TAG=$(OS_TAG) \
		--build-arg OS_IMAGE=$(BASE_IMAGE) \
		-t $(APP_IMAGE) \
		-f Dockerfile.wospi . 2>&1 | tee build-$(TARGET).log

push-slim:
	docker push $(SLIM_IMAGE)

push-base:
	docker push $(BASE_IMAGE)

push-app:
	docker push $(APP_IMAGE)

shell:
	docker run --rm -it $(BASE_IMAGE) bash

clean:
	docker rmi $(BASE_IMAGE) $(APP_IMAGE) || true

help:
	@echo "make slim        – Build base image (Dockerfile.slim)"
	@echo "make base        – Build base image (Dockerfile.base)"
	@echo "make app         – Build application image (Dockerfile.wospi) using --target=$(TARGET)"
	@echo "make push-slim   – Push slim image"
	@echo "make push-base   – Push base image"
	@echo "make push-app    – Push app image"
	@echo "make shell       – Run interactive shell in base image"
	@echo "make clean       – Remove local images"
	@echo "make help        – Show this help message"

