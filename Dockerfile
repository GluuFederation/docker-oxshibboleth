FROM ubuntu:14.04

MAINTAINER Gluu Inc. <support@gluu.org>

# ===============
# Ubuntu packages
# ===============

# JDK 8 repo
RUN echo "deb http://ppa.launchpad.net/openjdk-r/ppa/ubuntu trusty main" >> /etc/apt/sources.list.d/openjdk.list \
    && echo "deb-src http://ppa.launchpad.net/openjdk-r/ppa/ubuntu trusty main" >> /etc/apt/sources.list.d/openjdk.list \
    && apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 86F44E2A

RUN apt-get update && apt-get install -y \
    openjdk-8-jre-headless \
    unzip \
    wget \
    python \
    python-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# workaround for bug on ubuntu 14.04 with openjdk-8-jre-headless
RUN /var/lib/dpkg/info/ca-certificates-java.postinst configure

# Set openjdk 8 as default java
RUN cd /usr/lib/jvm && ln -s java-1.8.0-openjdk-amd64 default-java

# =====
# Jetty
# =====

ENV JETTY_VERSION 9.3.15.v20161220
ENV JETTY_TGZ_URL https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/${JETTY_VERSION}/jetty-distribution-${JETTY_VERSION}.tar.gz
ENV JETTY_HOME /opt/jetty
ENV JETTY_BASE /opt/gluu/jetty
ENV JETTY_USER_HOME_LIB /home/jetty/lib

# Install jetty
RUN wget -q ${JETTY_TGZ_URL} -O /tmp/jetty.tar.gz \
    && tar -xzf /tmp/jetty.tar.gz -C /opt \
    && mv /opt/jetty-distribution-${JETTY_VERSION} ${JETTY_HOME} \
    && rm -rf /tmp/jetty.tar.gz

# Ports required by jetty
EXPOSE 8080

# ============
# oxShibboleth
# ============

ENV OX_VERSION 3.1.0-SNAPSHOT
ENV OX_BUILD_DATE 2017-08-14
ENV OXSHIBBOLETH_DOWNLOAD_URL https://ox.gluu.org/maven/org/xdi/oxshibbolethIdp/${OX_VERSION}/oxshibbolethIdp-${OX_VERSION}.war

# the LABEL defined before downloading ox war/jar files to make sure
# it gets the latest build for specific version
LABEL vendor="Gluu Federation" \
      org.gluu.oxshibboleth.version="${OX_VERSION}" \
      org.gluu.oxshibboleth.build-date="${OX_BUILD_DATE}"

# Install oxShibboleth
RUN wget -q ${OXSHIBBOLETH_DOWNLOAD_URL} -O /tmp/oxshibboleth.war \
    && mkdir -p ${JETTY_BASE}/idp/webapps \
    && unzip -qq /tmp/oxshibboleth.war -d ${JETTY_BASE}/idp/webapps/idp \
    && java -jar ${JETTY_HOME}/start.jar jetty.home=${JETTY_HOME} jetty.base=${JETTY_BASE}/idp --add-to-start=deploy,http,jsp,http-forwarded \
    && rm -f /tmp/oxshibboleth.war

# ====
# tini
# ====

ENV TINI_VERSION v0.15.0
RUN wget -q https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini -O /tini \
    && chmod +x /tini
ENTRYPOINT ["/tini", "--"]

# ====
# gosu
# ====

ENV GOSU_VERSION 1.10
RUN wget -q https://github.com/tianon/gosu/releases/download/${GOSU_VERSION}/gosu-amd64 -O /usr/local/bin/gosu \
    && chmod +x /usr/local/bin/gosu

# ======
# Python
# ======
RUN pip install -U pip

# A workaround to address https://github.com/docker/docker-py/issues/1054
# and to make sure latest pip is being used, not from OS one
ENV PYTHONPATH="/usr/local/lib/python2.7/dist-packages:/usr/lib/python2.7/dist-packages"

RUN pip install "consulate==0.6.0"

# ==========
# misc stuff
# ==========

RUN mkdir -p /opt/shibboleth-idp/metadata/credentials \
    && mkdir -p /opt/shibboleth-idp/logs \
    && mkdir -p /opt/shibboleth-idp/lib \
    && mkdir -p /opt/shibboleth-idp/conf/authn \
    && mkdir -p /opt/shibboleth-idp/credentials \
    && mkdir -p /opt/shibboleth-idp/webapp

COPY templates /opt/templates
COPY static/password-authn-config.xml /opt/shibboleth-idp/conf/authn/

COPY scripts /opt/scripts
RUN chmod +x /opt/scripts/entrypoint.sh
CMD ["/opt/scripts/entrypoint.sh"]
