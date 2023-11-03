FROM debian:buster-slim

ARG CONT_VER WOSPI_VERSION WOSPI_RELEASE_DATE TERM LANG TZ USERHOME USERHOME CSVPATH TMPPATH WLOGPATH

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
RUN groupadd -g 1003 wospi && useradd -ms /bin/bash -u 1003 -g 1003 -G dialout -c "Weather Observation System for Raspberry Pi" -d $USERHOME wospi

# create directories
RUN bash -c 'mkdir -p $CSVPATH $WLOGPATH $BACKUPPATH'

WORKDIR $HOMEPATH

# wospi distribution start
# https://www.annoyingdesigns.com/wospi/wospi.zip

# variant 1
# adds layer; hide zip
#ADD https://www.annoyingdesigns.com/wospi/wospi.zip /tmp
#RUN unzip /tmp/wospi.zip && rm /tmp/wospi.zip

# variant 2
# without ADD
ENV WFILE=/tmp/wospi.zip
RUN curl -S -o $WFILE https://www.annoyingdesigns.com/wospi/wospi.zip && unzip $WFILE && rm $WFILE

# variant 3
# unzip and tar official software
#ADD data/wospi.20191127.tar.gz .
# wospi distribution end


# my personal changes and addons

# my tools for other weather sites
WORKDIR $USERHOME
ADD data/lftp.config.tar.gz $USERHOME
# add vcgen binary
ADD data/raspi.libs.tar.gz /

# add scripts
COPY data/scripts/entrypoint.sh /
COPY data/.vimrc /root
COPY data/.vimrc $USERHOME

# add cron jobs
COPY data/scripts/rc.wospi /etc/init.d/wospi
COPY data/cron/wospi_cron /etc/cron.d/wospi

# set permissions
RUN chown -R wospi:wospi $USERHOME $WLOGPATH $BACKUPPATH


# additional user, probably not required
RUN useradd -ms /home/wx/wxview.sh -c "WOSPI virtual terminal" wx
COPY --chown=wx:wospi --chmod=755 data/scripts/wxview.sh /home/wx


# only for dev
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

