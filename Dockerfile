FROM python:3.10.2-bullseye

# For a list of pre-defined annotation keys and value types see:
# https://github.com/opencontainers/image-spec/blob/master/annotations.md
# Note: Additional labels are added by the build workflow.
LABEL org.opencontainers.image.authors="jeremy.frasier@cisa.dhs.gov"
LABEL org.opencontainers.image.vendor="Cybersecurity and Infrastructure Security Agency"

###
# Setup the user and its home directory
###

ARG CISA_GID=421
ARG CISA_UID=${CISA_GID}
ENV CISA_USER="cisa"
ENV CISA_GROUP=${CISA_USER}
ENV CISA_HOME="/home/cisa"

###
# Create unprivileged user
###
RUN groupadd --system --gid ${CISA_GID} ${CISA_GROUP}
RUN useradd --system --uid ${CISA_UID} --gid ${CISA_GROUP} --comment "${CISA_USER} user" ${CISA_USER}

###
# Install everything we need
###

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
    texlive-science \
    fontconfig \
    redis-tools

# Setup texlive latex stuff.
RUN tlmgr init-usertree

###
# Install requirements for report generation
#
# Make sure pip and setuptools are the latest versions
#
# Note that we use pip --no-cache-dir to avoid writing to a local
# cache.  This results in a smaller final image, at the cost of
# slightly longer install times.
#
# numpy seems to be required to build basemap's wheel, so we'll
# install it first.
#
# Note that matplotlib.basemap is currently incompatible with
# matplotlib 3.x.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --upgrade numpy \
    && pip install --no-cache-dir --upgrade \
    chevron \
    docopt \
    geos \
    matplotlib \
    https://github.com/cisagov/mongo-db-from-config/tarball/develop \
    pandas \
    pypdf2

###
# Clean up aptitude cruft
###
RUN apt-get --quiet --quiet clean
RUN rm -rf /var/lib/apt/lists/*

###
# Setup working directory and entrypoint
###

# Put this just before we change users because the copy (and every
# step after it) will always be rerun by Docker, but we need to be
# root for the chown command.
COPY src ${CISA_HOME}
RUN chown -R ${CISA_USER}:${CISA_GROUP} ${CISA_HOME}

###
# Prepare to Run
###
# Right now we need to run as root for the font stuff
# USER ${CISA_USER}:${CISA_GROUP}
WORKDIR ${CISA_HOME}
ENTRYPOINT ["./report.sh"]
