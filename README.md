# docker-wospi-vanilla

WOSPi - Weather Observation System for Raspberry Pi by Torkel M. Jodalen in a docker container

Container build script for WOSPi. 

Based on the default distribution files from Torkel M. Jodalen.

An extended version is available at [docker-wospi extended](https://github.com/plix1014/docker-wospi). This contains additional reports.

One reason for putting WOSPi into the container was easier migration from one raspberryi/Raspberry Pi OS to another (newer).
The second reason was the python2 issue with the current Pi OS bookworm.

This vanilla version was the startingpoint for the 'dockerization'.

## Container build

First get the vcgencmd binary from the raspberry host
```
mk_vcgenbin_pkg.sh
```

Then check and edit the `.env` file.


Now you can build the container
```
cd <repo path>
docker build -t wospi-vanilla .
```

or
```
cd <repo path>
./build.sh
```

User in container runs with UID `6003`. if you want to change it, you could use the build argument `UIDGID`

You should create a user with the same UID on the docker host

e.g.
```
docker build  --target image-prod --build-arg="UIDGID=5100" -t wospi-vanilla .
```


### configuration

#### .env

Adjust according your needs


#### config.py

Edit `WOSPI_CONFIG`.

You could use:
| config file            | description |
|------------------------|-------------|
| `data/config.py`|slightly modified file with scp/fscp selection|
| `data/config.py.default`|original file from distribution file|

Or copy the `config.py` from the [original distribution file](https://www.annoyingdesigns.com/wospi)
or start the container and copy file to the host or use your current file 

#### docker-compose.yml

Check and edit the docker-compose.yml

e.g. the Volume mounts
| volumne            | description |
|--------------------|-------------|
|`${CSV_DATA}:/csv_data:rw`|path to csv_data directory|
|`${WOSPI_CONFIG}:$HOMEDIR/config.py:r`|path to config.py|
|`${BACKUP_DIR}:/backup:rw`|path to backup dir|
|`${NETRC_CONFIG}:$HOMEDIR/.netrc:r`|.netrc if needed => fscp selection in config.py|
|`${HOME}/.ssh:$HOMEDIR/.ssh:r`|ssh private key for upload => scp selection in config.py|


## operation

### start the container

```
cd <install path>
docker compose up -d
```

### enter into the container
```
./log2cont.sh
```

### view wxdata
view the wxdata.xml file. As you would login to the wx user
```
./view_wx_data.sh
```


## Dockerfile

packages installed in container

### mandatory wospi tools
* gnuplot 
* gsfonts 
* python-serial 
* python-dateutil 


### additional helper
* net-tools 
* procps
* sudo 
* vim 

* curl 
* unzip 
* zip 
* mutt 
* bc 
* lftp 


## Docker Hub

Link to docker hub
* [wospi-vanilla](https://hub.docker.com/repository/docker/juharov/wospi-vanilla/general)

## Credits

* WOSPi - [Weather Observation System for Raspberry Pi](http://wx.annoyingdesigns.com) by Torkel M. Jodalen
* Davis Vantage - [Davis Vantage Pro2 Weather station](https://www.davisnet.com/pages/vantage-pro2)

## Author

of the container build script

* **plix1014** - [plix1014](https://github.com/plix1014)


## License

This project is licensed under the Attribution-NonCommercial-ShareAlike 4.0 International License - see the [LICENSE.md](LICENSE.md) file for details

