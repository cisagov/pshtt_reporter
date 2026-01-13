# Official Docker images are in the form library/<app> while non-official
# images are in the form <user>/<app>.
FROM docker.io/library/python:3.14.2-trixie AS compile-stage

###
# Unprivileged user variables
###
ARG CISA_USER="cisa"
ENV CISA_HOME="/home/${CISA_USER}"
ENV VIRTUAL_ENV="${CISA_HOME}/.venv"

# Versions of the Python packages installed directly
ENV PYTHON_PIP_VERSION=25.3
ENV PYTHON_PIPENV_VERSION=2026.0.3
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
ENV DEPS="build-essential=12.12 \
    cmake=3.31.6-2 \
    libblas-dev=3.12.1-6 \
    libfontconfig1=2.15.0-2.3 \
    liblapack-dev=3.12.1-6 \
    libreadline-dev=8.2-6 \
    libssl-dev=3.5.4-1~deb13u1 \
    libxml2-dev=2.12.7+dfsg+really2.9.14-2.1+deb13u2 \
    libxslt1-dev=1.1.35-1.2+deb13u2 \
    libyaml-dev=0.2.5-2 \
    zlib1g-dev=1:1.3.dfsg+really1.3.1-1+b1 \
    autoconf=2.72-3.1 \
    automake=1:1.17-4 \
    bison=2:3.8.2+dfsg-1+b2 \
    libffi-dev=3.4.8-2 \
    libgdbm-dev=1.24-2 \
    libncurses-dev=6.5+20250216-2 \
    libsqlite3-dev=3.46.1-7 \
    libtool=2.5.4-4 \
    pkg-config=1.8.1-4 \
    libgeos-dev=3.13.1-1 \
    # Additional dependencies for python-build
    libbz2-dev=1.0.8-6 \
    llvm=1:19.0-63"
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
FROM docker.io/library/python:3.14.2-trixie AS build-stage

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
ENV DEPS="build-essential=12.12 \
    cmake=3.31.6-2 \
    curl=8.14.1-2+deb13u2 \
    git=1:2.47.3-0+deb13u1 \
    libblas3=3.12.1-6 \
    libc6=2.41-12+deb13u1 \
    libfontconfig1=2.15.0-2.3 \
    liblapack3=3.12.1-6 \
    libreadline8t64=8.2-6 \
    libssl3t64=3.5.4-1~deb13u1 \
    libxml2=2.12.7+dfsg+really2.9.14-2.1+deb13u2 \
    libxslt1.1=1.1.35-1.2+deb13u2 \
    libyaml-0-2=0.2.5-2 \
    make=4.4.1-2 \
    unzip=6.0-29 \
    wget=1.25.0-2 \
    zlib1g=1:1.3.dfsg+really1.3.1-1+b1 \
    autoconf=2.72-3.1 \
    automake=1:1.17-4 \
    bison=2:3.8.2+dfsg-1+b2 \
    #gawk=1:5.2.1-2+b1 \
    libffi8=3.4.8-2 \
    libgdbm6t64=1.24-2 \
    libncurses6=6.5+20250216-2 \
    libsqlite3-0=3.46.1-7 \
    libtool=2.5.4-4 \
    pkg-config=1.8.1-4 \
    sqlite3=3.46.1-7 \
    libgeos3.13.1=3.13.1-1 \
    # Additional dependencies for python-build
    libbz2-1.0=1.0.8-6 \
    llvm=1:19.0-63 \
    # libncursesw5-dev
    # Latex stuff
    xzdec=5.8.1-1 \
    texlive-latex-base=2024.20250309-1 \
    texlive-latex-recommended=2024.20250309-1 \
    texlive-latex-extra=2024.20250309-2 \
    texlive-xetex=2024.20250309-1 \
    fonts-lmodern=2.005-1 \
    lmodern=2.005-1 \
    texlive-science=2024.20250309-2 \
    fontconfig=2.15.0-2.3 \
    redis-tools=5:8.0.2-3+deb13u1"
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
