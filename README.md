# docker-wospi-vanilla

WOSPi - Weather Observation System for Raspberry Pi by Torkel M. Jodalen in a docker container



## Container build

First get the vcgencmd binary from the raspberry host
```
mk_vcgenbin_pkg.sh
```

Now you can build the container
```
cd <repo path>
docker build -t wospi-vanilla .
```

### configuration

Edit 'WOSPI_CONFIG'.

Copy the 'config.py' from the [original distribution file](https://www.annoyingdesigns.com/wospi)
or start the container and copy file to the host or use your current file 


### .env

Adjust according your needs



## Author

* **plix1014** - [plix1014](https://github.com/plix1014)


## License

This project is licensed under the Attribution-NonCommercial-ShareAlike 4.0 International License - see the [LICENSE.md](LICENSE.md) file for details

