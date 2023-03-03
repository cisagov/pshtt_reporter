# Set up cross-compilation scripts
FROM --platform=${BUILDPLATFORM} tonistiigi/xx:1.2.1 as xx

FROM --platform=${BUILDPLATFORM} python:3.11.2-bullseye

# Copy in cross-compilation scripts
COPY --from=xx / /

# Export the target platform
ARG TARGETPLATFORM

###
# For a list of pre-defined annotation keys and value types see:
# https://github.com/opencontainers/image-spec/blob/master/annotations.md
#
# Note: Additional labels are added by the build workflow.
LABEL org.opencontainers.image.authors="vm-fusion-dev-group@trio.dhs.gov"
LABEL org.opencontainers.image.vendor="Cybersecurity and Infrastructure Security Agency"

###
# Unprivileged user setup variables
###
ARG CISA_UID=421
ARG CISA_GID=${CISA_UID}
ARG CISA_USER="cisa"
ENV CISA_GROUP=${CISA_USER}
ENV CISA_HOME="/home/${CISA_USER}"

###
# Upgrade the system
###
RUN apt-get update --quiet --quiet \
    && apt-get upgrade --quiet --quiet

###
# Create unprivileged user
###
RUN groupadd --system --gid ${CISA_GID} ${CISA_GROUP} \
    && useradd --system --uid ${CISA_UID} --gid ${CISA_GROUP} --comment "${CISA_USER} user" ${CISA_USER}

###
# Install everything we need
#
# Install dependencies are only needed for software installation and
# will be removed at the end of the build process.
###
ENV DEPS \
    curl \
    git \
    libfontconfig1 \
    unzip \
    wget \
    gawk \
    pkg-config \
    sqlite3 \
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
ENV BUILD_DEPS \
    autoconf \
    automake \
    bison \
    build-essential \
    # Additional dependencies for python-build
    libbz2-dev \
    libc6-dev \
    libffi-dev \
    libgdbm-dev \
    libgeos-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    libtool \
    libxml2-dev \
    libxslt1-dev \
    libyaml-dev \
    llvm \
    make \
    zlib1g-dev

# ENV INSTALL_DEPS \
#     git
RUN apt-get install --quiet --quiet --yes \
    --no-install-recommends --no-install-suggests \
    $DEPS $INSTALL_DEPS

RUN xx-apt-get install --quiet --quiet --yes \
    --no-install-recommends --not-install-suggests \
    $BUILD_DEPS

###
# Make sure pip, setuptools, and wheel are the latest versions
#
# Note that we use pip3 --no-cache-dir to avoid writing to a local
# cache.  This results in a smaller final image, at the cost of
# slightly longer install times.
###
RUN pip3 install --no-cache-dir --upgrade \
    pip \
    setuptools \
    wheel

# Setup texlive latex stuff.
RUN tlmgr init-usertree

###
# Install requirements for report generation
#
# Note that we use pip3 --no-cache-dir to avoid writing to a local
# cache.  This results in a smaller final image, at the cost of
# slightly longer install times.
#
# numpy seems to be required to build basemap's wheel, so we'll
# install it first.
#
# Note that matplotlib.basemap is currently incompatible with
# matplotlib 3.x.
RUN pip3 install --no-cache-dir --upgrade numpy \
    && pip3 install --no-cache-dir --upgrade \
    chevron \
    docopt \
    geos \
    matplotlib \
    https://github.com/cisagov/mongo-db-from-config/tarball/develop \
    pandas \
    pypdf2

###
# Remove install dependencies
###
# RUN apt-get remove --quiet --quiet $INSTALL_DEPS

###
# Clean up aptitude cruft
###
RUN apt-get --quiet --quiet clean \
    && rm --recursive --force /var/lib/apt/lists/*

###
# Setup working directory and entrypoint
###

# Put this just before we change users because the copy (and every
# step after it) will always be rerun by Docker, but we need to be
# root for the chown command.
COPY src ${CISA_HOME}
RUN chown --recursive ${CISA_USER}:${CISA_GROUP} ${CISA_HOME}

###
# Prepare to run
###
# Right now we need to run as root for the font stuff
# USER ${CISA_USER}:${CISA_GROUP}
WORKDIR ${CISA_HOME}
ENTRYPOINT ["./report.sh"]
