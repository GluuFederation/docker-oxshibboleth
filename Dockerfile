FROM openjdk:8-jre-alpine

LABEL maintainer="Gluu Inc. <support@gluu.org>"

# ===============
# Alpine packages
# ===============

RUN apk update && apk add --no-cache \
    unzip \
    wget \
    py-pip \
    inotify-tools \
    openssl

# =====
# Jetty
# =====

ENV JETTY_VERSION 9.4.9.v20180320
ENV JETTY_TGZ_URL https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/${JETTY_VERSION}/jetty-distribution-${JETTY_VERSION}.tar.gz
ENV JETTY_HOME /opt/jetty
ENV JETTY_BASE /opt/gluu/jetty
ENV JETTY_USER_HOME_LIB /home/jetty/lib

# Install jetty
RUN wget -q ${JETTY_TGZ_URL} -O /tmp/jetty.tar.gz \
    && mkdir -p /opt \
    && tar -xzf /tmp/jetty.tar.gz -C /opt \
    && mv /opt/jetty-distribution-${JETTY_VERSION} ${JETTY_HOME} \
    && rm -rf /tmp/jetty.tar.gz

# Ports required by jetty
EXPOSE 8080

# ============
# oxShibboleth
# ============

ENV OX_VERSION 3.1.4.Final
ENV OX_BUILD_DATE 2018-09-27

# the LABEL defined before downloading ox war/jar files to make sure
# it gets the latest build for specific version
LABEL vendor="Gluu Federation" \
      org.gluu.oxshibboleth.version="${OX_VERSION}" \
      org.gluu.oxshibboleth.build-date="${OX_BUILD_DATE}"

# Install oxShibboleth WAR
RUN wget -q https://ox.gluu.org/maven/org/xdi/oxshibbolethIdp/${OX_VERSION}/oxshibbolethIdp-${OX_VERSION}.war -O /tmp/oxshibboleth.war \
    && mkdir -p ${JETTY_BASE}/idp/webapps \
    && unzip -qq /tmp/oxshibboleth.war -d ${JETTY_BASE}/idp/webapps/idp \
    && java -jar ${JETTY_HOME}/start.jar jetty.home=${JETTY_HOME} jetty.base=${JETTY_BASE}/idp --add-to-start=server,deploy,annotations,resources,http,http-forwarded,jsp \
    && rm -f /tmp/oxshibboleth.war

# Install Shibboleth JAR
RUN wget -q https://ox.gluu.org/maven/org/xdi/oxShibbolethStatic/${OX_VERSION}/oxShibbolethStatic-${OX_VERSION}.jar -O /tmp/shibboleth-idp.jar \
    && unzip -qq /tmp/shibboleth-idp.jar -d /opt \
    && rm -rf /opt/META-INF \
    && rm -f /tmp/shibboleth-idp.jar

# RUN mkdir -p /opt/shibboleth-idp/lib \
#     && cp ${JETTY_BASE}/idp/webapps/idp/WEB-INF/lib/saml-openid-auth-client-${OX_VERSION}.jar /opt/shibboleth-idp/lib/

# ====
# Tini
# ====

ENV TINI_VERSION v0.18.0
RUN wget -q https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-static -O /usr/bin/tini \
    && chmod +x /usr/bin/tini

# ======
# Python
# ======
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# ==========
# misc stuff
# ==========

RUN mkdir -p /opt/shibboleth-idp/metadata/credentials \
    && mkdir -p /opt/shibboleth-idp/logs \
    && mkdir -p /opt/shibboleth-idp/lib \
    && mkdir -p /opt/shibboleth-idp/conf/authn \
    && mkdir -p /opt/shibboleth-idp/credentials \
    && mkdir -p /opt/shibboleth-idp/webapp \
    && mkdir -p /etc/certs \
    && mkdir -p /etc/gluu/conf

COPY templates /opt/templates
COPY static/password-authn-config.xml /opt/shibboleth-idp/conf/authn/

ENV GLUU_CONFIG_ADAPTER consul
ENV GLUU_CONSUL_HOST localhost
ENV GLUU_CONSUL_PORT 8500
ENV GLUU_CONSUL_CONSISTENCY stale
ENV GLUU_CONSUL_SCHEME http
ENV GLUU_CONSUL_VERIFY false
ENV GLUU_CONSUL_CACERT_FILE /etc/certs/consul_ca.crt
ENV GLUU_CONSUL_CERT_FILE /etc/certs/consul_client.crt
ENV GLUU_CONSUL_KEY_FILE /etc/certs/consul_client.key
ENV GLUU_CONSUL_TOKEN_FILE /etc/certs/consul_token
ENV GLUU_LDAP_URL localhost:1636
ENV GLUU_KUBERNETES_NAMESPACE default
ENV GLUU_KUBERNETES_CONFIGMAP gluu
ENV GLUU_SHIB_SOURCE_DIR /opt/shared-shibboleth-idp
ENV GLUU_SHIB_TARGET_DIR /opt/shibboleth-idp
ENV GLUU_MAX_RAM_FRACTION 1

VOLUME /opt/shared-shibboleth-idp

COPY scripts /opt/scripts
RUN chmod +x /opt/scripts/entrypoint.sh
ENTRYPOINT ["tini", "--"]
CMD ["/opt/scripts/wait-for-it", "/opt/scripts/entrypoint.sh"]
