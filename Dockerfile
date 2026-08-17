# Official Docker images are in the form library/<app> while non-official
# images are in the form <user>/<app>.
FROM docker.io/library/python:3.14.7-slim-trixie AS compile-stage

###
# Unprivileged user variables
###
ARG CISA_USER="cisa"
ENV CISA_HOME="/home/${CISA_USER}"
ENV VIRTUAL_ENV="${CISA_HOME}/.venv"

# Versions of the Python packages installed directly
# renovate: datasource=pypi depName=pip
ENV PYTHON_PIP_VERSION=26.2.1
# renovate: datasource=pypi depName=pipenv
ENV PYTHON_PIPENV_VERSION=2026.7.1
# renovate: datasource=pypi depName=setuptools
ENV PYTHON_SETUPTOOLS_VERSION=84.0.0

###
# Install the specified versions of pip and setuptools into the system
# Python environment; install the specified version of pipenv into the system Python
# environment; set up a Python virtual environment (venv); and install the specified
# versions of pip and setuptools into the venv.
#
# Note that we use the --no-cache-dir flag to avoid writing to a local
# cache.  This results in a smaller final image, at the cost of
# slightly longer install times.
###
RUN python3 -m pip install --no-cache-dir --upgrade \
        pip==${PYTHON_PIP_VERSION} \
        setuptools==${PYTHON_SETUPTOOLS_VERSION} \
    && python3 -m pip install --no-cache-dir --upgrade \
        pipenv==${PYTHON_PIPENV_VERSION} \
    # Manually create the virtual environment
    && python3 -m venv ${VIRTUAL_ENV} \
    # Ensure the core Python packages are installed in the virtual environment
    && ${VIRTUAL_ENV}/bin/python3 -m pip install --no-cache-dir --upgrade \
        pip==${PYTHON_PIP_VERSION} \
        setuptools==${PYTHON_SETUPTOOLS_VERSION}

###
# Install the Python dependencies into the virtual environment.
#
# Note that pipenv will install into a virtual environment if the VIRTUAL_ENV
# environment variable is set.
###
WORKDIR /tmp
COPY src/Pipfile src/Pipfile.lock ./
RUN pipenv install --clear --deploy --extra-pip-args="--no-cache-dir" --verbose

# Official Docker images are in the form library/<app> while non-official
# images are in the form <user>/<app>.
FROM docker.io/library/python:3.14.7-slim-trixie AS build-stage

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
# Install everything we need.
#
# Note that the suite name must be kept in sync with the version of
# Debian being used in the base containers.
###
# renovate: datasource=deb depName=fontconfig
ENV FONTCONFIG_VERSION=2.15.0-2.3
# renovate: datasource=deb depName=lmodern
ENV LMODERN_VERSION=2.005-1
# renovate: datasource=deb depName=redis-tools
ENV REDIS_TOOLS_VERSION=5:8.0.2-3+deb13u2
# renovate: datasource=deb depName=texlive-latex-base
ENV TEXLIVE_LATEX_BASE_VERSION=2024.20250309-1
# renovate: datasource=deb depName=texlive-latex-extra
ENV TEXLIVE_LATEX_EXTRA_VERSION=2024.20250309-2
# renovate: datasource=deb depName=texlive-latex-recommended
ENV TEXLIVE_LATEX_RECOMMENDED_VERSION=2024.20250309-1
# renovate: datasource=deb depName=texlive-science
ENV TEXLIVE_SCIENCE_VERSION=2024.20250309-2
# renovate: datasource=deb depName=texlive-xetex
ENV TEXLIVE_XETEX_VERSION=2024.20250309-1
# renovate: datasource=deb depName=unzip
ENV UNZIP_VERSION=6.0-29
# renovate: datasource=deb depName=wget
ENV WGET_VERSION=1.25.0-2
# renovate: datasource=deb depName=xzdec
ENV XZDEC_VERSION=5.8.1-1+deb13u1
ENV DEPS="fontconfig=${FONTCONFIG_VERSION} \
    lmodern=${LMODERN_VERSION} \
    redis-tools=${REDIS_TOOLS_VERSION} \
    texlive-latex-base=${TEXLIVE_LATEX_BASE_VERSION} \
    texlive-latex-extra=${TEXLIVE_LATEX_EXTRA_VERSION} \
    texlive-latex-recommended=${TEXLIVE_LATEX_RECOMMENDED_VERSION} \
    texlive-science=${TEXLIVE_SCIENCE_VERSION} \
    texlive-xetex=${TEXLIVE_XETEX_VERSION} \
    unzip=${UNZIP_VERSION} \
    wget=${WGET_VERSION} \
    xzdec=${XZDEC_VERSION}"
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
