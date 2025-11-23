# Official Docker images are in the form library/<app> while non-official
# images are in the form <user>/<app>.
FROM docker.io/library/python:3.14.0-bookworm AS compile-stage

###
# Unprivileged user variables
###
ARG CISA_USER="cisa"
ENV CISA_HOME="/home/${CISA_USER}"
ENV VIRTUAL_ENV="${CISA_HOME}/.venv"

# Versions of the Python packages installed directly
ENV PYTHON_PIP_VERSION=25.2
# This is the latest version of pipenv available for Python 3.12.3.
ENV PYTHON_PIPENV_VERSION=2025.0.4
ENV PYTHON_SETUPTOOLS_VERSION=80.9.0
ENV PYTHON_WHEEL_VERSION=0.45.1

###
# Install the specified versions of pip, setuptools, and wheel;
# install the specified version of pipenv; create the image dependency
# venv; and install the specified versions of pip, setuptools, and
# wheel into the dependency venv.
#
# Note that we use the --no-cache-dir flag to avoid writing to a local
# cache.  This results in a smaller final image, at the cost of
# slightly longer install times.
###
RUN python3 -m pip install --no-cache-dir --upgrade \
        pip==${PYTHON_PIP_VERSION} \
        setuptools==${PYTHON_SETUPTOOLS_VERSION} \
        wheel==${PYTHON_WHEEL_VERSION} \
    && python3 -m pip install --no-cache-dir --upgrade \
        pipenv==${PYTHON_PIPENV_VERSION} \
    # Manually create the virtual environment
    && python3 -m venv ${VIRTUAL_ENV} \
    # Ensure the core Python packages are installed in the virtual environment
    && ${VIRTUAL_ENV}/bin/python3 -m pip install --no-cache-dir --upgrade \
        pip==${PYTHON_PIP_VERSION} \
        setuptools==${PYTHON_SETUPTOOLS_VERSION} \
        wheel==${PYTHON_WHEEL_VERSION}

###
# Install everything we need to build wheels
#
# TODO: Remove any packages we don't need.  See #105 for more details.
#
# TODO: Pin these packages to enable reproducible builds.  See #106
# for more details.
###
ENV DEPS="build-essential \
    cmake \
    curl \
    git \
    libblas-dev \
    libc6-dev \
    libfontconfig1 \
    liblapack-dev \
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
    libncursesw5-dev"
RUN apt update --quiet --quiet \
    && apt install --quiet --quiet --yes \
    --no-install-recommends --no-install-suggests \
    $DEPS

###
# Install the Python dependencies into the virtual environment.
#
# Note that pipenv will install into a virtual environment if the VIRTUAL_ENV
# environment variable is set.
###
WORKDIR /tmp
COPY src/Pipfile src/Pipfile.lock ./
RUN pipenv install --clear --deploy --extra-pip-args "--no-cache-dir" --verbose

# Official Docker images are in the form library/<app> while non-official
# images are in the form <user>/<app>.
FROM docker.io/library/python:3.14.0-bookworm AS build-stage

###
# For a list of pre-defined annotation keys and value types see:
# https://github.com/opencontainers/image-spec/blob/master/annotations.md
#
# Note: Additional labels are added by the build workflow.
LABEL org.opencontainers.image.authors="vm-dev@gwe.cisa.dhs.gov"
LABEL org.opencontainers.image.vendor="Cybersecurity and Infrastructure Security Agency"

###
# Unprivileged user setup variables
###
ARG CISA_UID=421
ARG CISA_GID=${CISA_UID}
ARG CISA_USER="cisa"
ENV CISA_GROUP=${CISA_USER}
ENV CISA_HOME="/home/${CISA_USER}"
ENV VIRTUAL_ENV="${CISA_HOME}/.venv"

###
# Create unprivileged user
###
RUN groupadd --system --gid ${CISA_GID} ${CISA_GROUP} \
    && useradd --system --uid ${CISA_UID} --gid ${CISA_GROUP} --comment "${CISA_USER} user" ${CISA_USER}

###
# Install everything we need
#
# TODO: Remove any packages we don't need.  See #105 for more details.
# For example, it should be possible to install libblas-dev above but
# only install libblas here.
#
# TODO: Pin these packages to enable reproducible builds.  See #106
# for more details.
###
ENV DEPS="build-essential \
    cmake \
    curl \
    git \
    libblas-dev \
    libc6-dev \
    libfontconfig1 \
    liblapack-dev \
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
    redis-tools"
RUN apt update --quiet --quiet \
    && apt install --quiet --quiet --yes \
    --no-install-recommends --no-install-suggests \
    $DEPS

# Setup texlive latex stuff.
RUN tlmgr init-usertree

###
# Copy in the Python virtual environment created in compile-stage, symlink the
# Python binary in the venv to the system-wide Python, and add the venv to the PATH.
#
# Note that we symlink the Python binary in the venv to the system-wide Python so that
# any calls to `python3` will use our virtual environment. We are using short flags
# because the ln binary in Alpine Linux does not support long flags. The -f instructs
# ln to remove the existing file and the -s instructs ln to create a symbolic link.
###
COPY --from=compile-stage --chown=${CISA_USER}:${CISA_GROUP} ${VIRTUAL_ENV} ${VIRTUAL_ENV}
RUN ln -fs "$(command -v python3)" "${VIRTUAL_ENV}"/bin/python3
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

###
# Clean up aptitude cruft
###
RUN apt --quiet --quiet clean \
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
