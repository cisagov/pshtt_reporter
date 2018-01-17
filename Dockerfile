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
    libssl-doc \
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
    python-pip \
    libgeos-dev \
    python3-dev \
    python3-pip \
    python3-tk \
    texlive-xetex \
    # Additional dependencies for python-build
    libbz2-dev \
    llvm \
    libncursesw5-dev \
    # Latex stuff
    xzdec \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    fonts-lmodern \
    lmodern \
    texlive-math-extra \
    fontconfig

# Setup texlive latex stuff.
# This command returns a bogus non-zero return value:
# https://www.tug.org/pipermail/tex-live/2016-March/037889.html
RUN tlmgr init-usertree || true \
    && tlmgr option repository ftp://tug.org/historic/systems/texlive/2015/tlnet-final \
    && tlmgr update --self \
    && tlmgr install arydshln

# Install requirements for report generation
RUN pip3 install --upgrade setuptools \
    && pip3 install \
    pymongo \
    pypdf2 \
    matplotlib \
    pystache \
    pandas \
    geos \
    https://github.com/matplotlib/basemap/archive/v1.1.0.tar.gz \
    pyyaml \
    docopt

###
# Create unprivileged User
###
ENV SCANNER_HOME=/home/scanner
RUN groupadd -r scanner \
    && useradd -r -c "Scanner user" -g scanner scanner

# It would be nice to get rid of some build dependencies at this point

# Clean up aptitude cruft
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Put this just before we change users because the copy (and every
# step after it) will always be rerun by docker, but we need to be
# root for the chown command.
COPY . $SCANNER_HOME
RUN chown -R scanner:scanner ${SCANNER_HOME}

###
# Prepare to Run
###
# Right now we need to run as root for the font stuff
# USER scanner:scanner
WORKDIR $SCANNER_HOME
ENTRYPOINT ["./report.sh"]
