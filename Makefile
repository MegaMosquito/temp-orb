all: build run

build:
	docker build -t ibmosquito/temp-orb:1.0.0 -f Dockerfile .

dev: build stop
	-docker rm -f temp-orb 2> /dev/null || :
	docker run -it --privileged --name temp-orb --volume `pwd`:/outside ibmosquito/temp-orb:1.0.0 /bin/bash

run: stop
	-docker rm -f temp-orb 2>/dev/null || :
	docker run -d --restart=unless-stopped --privileged --name temp-orb ibmosquito/temp-orb:1.0.0

exec:
	docker exec -it temp-orb /bin/sh

push:
	docker push ibmosquito/temp-orb:1.0.0

stop:
	-docker rm -f temp-orb 2>/dev/null || :

clean: stop
	-docker rmi ibmosquito/temp-orb:1.0.0 2>/dev/null || :

.PHONY: all build dev run exec push stop clean
