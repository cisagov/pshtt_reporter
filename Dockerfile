FROM python:3.6
MAINTAINER Shane Frasier <jeremy.frasier@beta.dhs.gov>

###
# Dependencies
###
RUN apt-get update -qq \
    && apt-get install -qq --yes --no-install-recommends --no-install-suggests \
    build-essential \
    curl \
    git \
    libc6-dev \
    libfontconfig1 \
    libreadline-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    libyaml-dev \
    make \
    unzip \
    wget \
    zlib1g-dev \
    autoconf \
    automake \
    bison \
    gawk \
    libffi-dev \
    libgdbm-dev \
    libncurses5-dev \
    libsqlite3-dev \
    libtool \
    pkg-config \
    sqlite3 \
    libgeos-dev \
    # Additional dependencies for python-build
    libbz2-dev \
    llvm \
    libncursesw5-dev \
    # Latex stuff
    xzdec \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-xetex \
    fonts-lmodern \
    lmodern \
    texlive-math-extra \
    fontconfig \
    redis-tools

# Setup texlive latex stuff.
#
# The first command returns a bogus non-zero return value:
# https://www.tug.org/pipermail/tex-live/2016-March/037889.html
#
# The --no-persistent-downloads flag is necessary on the last command
# when the Docker container is built in TravisCI.
RUN tlmgr init-usertree || true \
    && tlmgr option repository ftp://tug.org/historic/systems/texlive/2015/tlnet-final \
    && tlmgr update --self \
    && tlmgr --no-persistent-downloads install arydshln

# Install requirements for report generation
RUN pip install --upgrade setuptools \
    && pip install \
    pymongo \
    pypdf2 \
    matplotlib \
    pystache \
    pandas \
    geos \
    pyyaml \
    docopt \
    https://github.com/matplotlib/basemap/archive/v1.1.0.tar.gz

###
# Create unprivileged User
###
ENV REPORTER_HOME=/home/reporter
RUN groupadd -r reporter \
    && useradd -r -c "Reporter user" -g reporter reporter

# It would be nice to get rid of some build dependencies at this point

# Clean up aptitude cruft
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Put this just before we change users because the copy (and every
# step after it) will always be rerun by docker, but we need to be
# root for the chown command.
COPY . $REPORTER_HOME
RUN chown -R reporter:reporter ${REPORTER_HOME}

###
# Prepare to Run
###
# Right now we need to run as root for the font stuff
# USER reporter:reporter
WORKDIR $REPORTER_HOME
ENTRYPOINT ["./report.sh"]
