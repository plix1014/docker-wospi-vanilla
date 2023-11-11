#------------------------------------------------------------------------------------------
# checkout git
FROM alpine/git:latest
WORKDIR /addon
RUN git clone https://github.com/plix1014/wospi-addon.git
WORKDIR /addon/wospi-addon
RUN git pull

#------------------------------------------------------------------------------------------
# build image
FROM debian:buster-slim as base

ARG CONT_VER WOSPI_VERSION WOSPI_RELEASE_DATE
ARG UIDGID=6003


ENV CONT_VER=${CONT_VER:-0.5}
ENV WOSPI_VERSION=${WOSPI_VERSION:-20191127}
ENV WOSPI_RELEASE_DATE=${WOSPI_RELEASE_DATE:-2019-11-27}
ENV TERM=${TERM:-xterm-256color}
ENV LANG=${LANG:-en_US.UTF-8}
ENV TZ=${TZ:-Europe/Vienna}
# wospi config
ENV USERHOME=${USERHOME:-/home/wospi}
ENV HOMEPATH=${HOMEPATH:-${USERHOME}}
ENV CSVPATH=${CSVPATH:-/csv_data}
ENV BACKUPPATH=${BACKUPPATH:-/backup}
ENV TMPPATH=${TMPPATH:-/var/tmp/}
ENV WLOGPATH=${WLOGPATH:-/var/log/wospi}
ENV MAILTO=${MAILTO}
ENV PYTHONUNBUFFERED=1


# some lables
LABEL com.wospi.version=${WOSPI_VERSION}
LABEL com.wospi.release-date=${WOSPI_RELEASE_DATE}
LABEL com.wospi.maintainer="Torkel M. Jodalen <tmj@bitwrap.no>"
LABEL com.wospi.container.maintainer="plix1014@gmail.com"

# os config
RUN apt update && \
  apt install -y curl unzip gnupg lsb-release ca-certificates net-tools coreutils locales cron bc zip mutt lftp gnuplot gsfonts vim sudo python-serial python-dateutil procps && \
  sed -i 's,^# en_US,en_US,g' /etc/locale.gen && \
  locale-gen en_US.UTF-8 && \
  update-locale && \
  apt-get -y clean && \
  rm -r /var/cache/apt /var/lib/apt/lists/* /var/log/*log


# user setup
RUN groupadd -g ${UIDGID} wospi && useradd -ms /bin/bash -u ${UIDGID} -g ${UIDGID} -G dialout -c "Weather Observation System for Raspberry Pi" -d $USERHOME wospi

# create directories
RUN bash -c 'mkdir -p $CSVPATH $WLOGPATH $BACKUPPATH'


#------------------------------------------------------------------------------------------
# build wospi vanilla image
FROM base as image-vanilla

WORKDIR $HOMEPATH

# wospi distribution start
# https://www.annoyingdesigns.com/wospi/wospi.zip
#
ENV WFILE=/tmp/wospi.zip
RUN curl -S -o $WFILE https://www.annoyingdesigns.com/wospi/wospi.zip && unzip $WFILE && rm $WFILE
#
# wospi distribution end

# add scripts
COPY data/scripts/entrypoint.sh /
COPY data/.vimrc /root
COPY data/.vimrc $USERHOME
# 
COPY data/scripts/wxBackup.sh $USERHOME

# add cron jobs
COPY --chown=root:root --chmod=0755 data/scripts/rc.wospi /etc/init.d/wospi
COPY --chown=root:root --chmod=0644 data/cron/wospi_cron /etc/cron.d/wospi

# set permissions
RUN chown -R wospi:wospi $USERHOME $WLOGPATH $BACKUPPATH


# additional user, probably not required
RUN useradd -ms /home/wx/wxview.sh -c "WOSPI virtual terminal" wx
COPY --chown=wx:wospi --chmod=755 data/scripts/wxview.sh /home/wx


# sudo and vim nice to have, but not necessary
RUN echo "wospi ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/030_wospi-nopasswd


USER wospi

# set default dir
WORKDIR $HOMEPATH

# volume for csv files
VOLUME [ "$CSVPATH", "$TMPPATH", "$BACKUPPATH" ]

# start wospi
ENTRYPOINT ["/entrypoint.sh"]
CMD ["wospi"]


#------------------------------------------------------------------------------------------
# build prod image
FROM image-vanilla as image-prod
USER root

# add vcgen binary
ADD data/raspi.libs.tar.gz /

# my additional scripts
COPY --from=0 /addon/wospi-addon/transfer/fscp /usr/local/bin
# lftp config
ADD data/lftp.config.tar.gz $USERHOME
# set permissions
RUN chown -R wospi:wospi $USERHOME 

USER wospi

#------------------------------------------------------------------------------------------
