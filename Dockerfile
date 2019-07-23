FROM adoptopenjdk/openjdk11:jre-11.0.4_11-alpine

# ===============
# Alpine packages
# ===============

RUN apk update && apk add --no-cache \
    unzip \
    wget \
    py-pip \
    inotify-tools \
    openssl \
    shadow \
    git

# =====
# Jetty
# =====

ENV JETTY_VERSION=9.4.19.v20190610 \
    JETTY_HOME=/opt/jetty \
    JETTY_BASE=/opt/gluu/jetty \
    JETTY_USER_HOME_LIB=/home/jetty/lib

# Install jetty
RUN wget -q https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/${JETTY_VERSION}/jetty-distribution-${JETTY_VERSION}.tar.gz -O /tmp/jetty.tar.gz \
    && mkdir -p /opt \
    && tar -xzf /tmp/jetty.tar.gz -C /opt \
    && mv /opt/jetty-distribution-${JETTY_VERSION} ${JETTY_HOME} \
    && rm -rf /tmp/jetty.tar.gz \
    && cp ${JETTY_HOME}/etc/webdefault.xml ${JETTY_HOME}/etc/webdefault.xml.bak \
    && cp ${JETTY_HOME}/etc/jetty.xml ${JETTY_HOME}/etc/jetty.xml.bak

# Ports required by jetty
EXPOSE 8080

# ============
# oxShibboleth
# ============

ENV OX_VERSION=4.0.b1 \
    OX_BUILD_DATE=2019-07-23

# the LABEL defined before downloading ox war/jar files to make sure
# it gets the latest build for specific version
LABEL maintainer="Gluu Inc. <support@gluu.org>" \
    vendor="Gluu Federation" \
    org.gluu.oxshibboleth.version="${OX_VERSION}" \
    org.gluu.oxshibboleth.build-date="${OX_BUILD_DATE}"

# Install oxShibboleth WAR
RUN wget -q https://ox.gluu.org/maven/org/gluu/oxshibbolethIdp/${OX_VERSION}/oxshibbolethIdp-${OX_VERSION}.war -O /tmp/oxshibboleth.war \
    && mkdir -p ${JETTY_BASE}/idp/webapps \
    && unzip -qq /tmp/oxshibboleth.war -d ${JETTY_BASE}/idp/webapps/idp \
    && java -jar ${JETTY_HOME}/start.jar jetty.home=${JETTY_HOME} jetty.base=${JETTY_BASE}/idp --add-to-start=server,deploy,annotations,resources,http,http-forwarded,threadpool,jsp \
    && rm -f /tmp/oxshibboleth.war

# Install Shibboleth JAR
RUN wget -q https://ox.gluu.org/maven/org/gluu/oxShibbolethStatic/${OX_VERSION}/oxShibbolethStatic-${OX_VERSION}.jar -O /tmp/shibboleth-idp.jar \
    && unzip -qq /tmp/shibboleth-idp.jar -d /opt \
    && rm -rf /opt/META-INF \
    && rm -f /tmp/shibboleth-idp.jar

# RUN mkdir -p /opt/shibboleth-idp/lib \
#     && cp ${JETTY_BASE}/idp/webapps/idp/WEB-INF/lib/saml-openid-auth-client-${OX_VERSION}.jar /opt/shibboleth-idp/lib/

# ====
# Tini
# ====

RUN wget -q https://github.com/krallin/tini/releases/download/v0.18.0/tini-static -O /usr/bin/tini \
    && chmod +x /usr/bin/tini

# ======
# Python
# ======

COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && apk del git

# =======
# License
# =======

RUN mkdir -p /licenses
COPY LICENSE /licenses/

# ==========
# Config ENV
# ==========

ENV GLUU_CONFIG_ADAPTER=consul \
    GLUU_CONFIG_CONSUL_HOST=localhost \
    GLUU_CONFIG_CONSUL_PORT=8500 \
    GLUU_CONFIG_CONSUL_CONSISTENCY=stale \
    GLUU_CONFIG_CONSUL_SCHEME=http \
    GLUU_CONFIG_CONSUL_VERIFY=false \
    GLUU_CONFIG_CONSUL_CACERT_FILE=/etc/certs/consul_ca.crt \
    GLUU_CONFIG_CONSUL_CERT_FILE=/etc/certs/consul_client.crt \
    GLUU_CONFIG_CONSUL_KEY_FILE=/etc/certs/consul_client.key \
    GLUU_CONFIG_CONSUL_TOKEN_FILE=/etc/certs/consul_token \
    GLUU_CONFIG_KUBERNETES_NAMESPACE=default \
    GLUU_CONFIG_KUBERNETES_CONFIGMAP=gluu \
    GLUU_CONFIG_KUBERNETES_USE_KUBE_CONFIG=false

# ==========
# Secret ENV
# ==========

ENV GLUU_SECRET_ADAPTER=vault \
    GLUU_SECRET_VAULT_SCHEME=http \
    GLUU_SECRET_VAULT_HOST=localhost \
    GLUU_SECRET_VAULT_PORT=8200 \
    GLUU_SECRET_VAULT_VERIFY=false \
    GLUU_SECRET_VAULT_ROLE_ID_FILE=/etc/certs/vault_role_id \
    GLUU_SECRET_VAULT_SECRET_ID_FILE=/etc/certs/vault_secret_id \
    GLUU_SECRET_VAULT_CERT_FILE=/etc/certs/vault_client.crt \
    GLUU_SECRET_VAULT_KEY_FILE=/etc/certs/vault_client.key \
    GLUU_SECRET_VAULT_CACERT_FILE=/etc/certs/vault_ca.crt \
    GLUU_SECRET_KUBERNETES_NAMESPACE=default \
    GLUU_SECRET_KUBERNETES_SECRET=gluu \
    GLUU_SECRET_KUBERNETES_USE_KUBE_CONFIG=false

# ===============
# Persistence ENV
# ===============

# available options: couchbase, ldap, hybrid
# only takes affect when GLUU_PERSISTENCE_TYPE is hybrid
# available options: default, user, cache, site, statistic
ENV GLUU_PERSISTENCE_TYPE=ldap \
    GLUU_PERSISTENCE_LDAP_MAPPING=default \
    GLUU_COUCHBASE_URL=localhost \
    GLUU_LDAP_URL=localhost:1636

# ===========
# Generic ENV
# ===========

ENV GLUU_SHIB_SOURCE_DIR=/opt/shared-shibboleth-idp \
    GLUU_SHIB_TARGET_DIR=/opt/shibboleth-idp \
    GLUU_MAX_RAM_PERCENTAGE=25.0 \
    GLUU_WAIT_MAX_TIME=300 \
    GLUU_WAIT_SLEEP_DURATION=5

# ==========
# misc stuff
# ==========

RUN mkdir -p /opt/shibboleth-idp/metadata/credentials \
    /opt/shibboleth-idp/logs \
    /opt/shibboleth-idp/lib \
    /opt/shibboleth-idp/conf/authn \
    /opt/shibboleth-idp/credentials \
    /opt/shibboleth-idp/webapp \
    /etc/certs \
    /etc/gluu/conf \
    /deploy \
    /opt/shared-shibboleth-idp \
    /app

# COPY static/idp3/password-authn-config.xml /opt/shibboleth-idp/conf/authn/
COPY static /app/static
RUN mv /app/static/idp3/password-authn-config.xml /opt/shibboleth-idp/conf/authn/
RUN cp /opt/shibboleth-idp/conf/global.xml /opt/shibboleth-idp/conf/global.xml.bak
COPY templates /app/templates
COPY scripts /app/scripts
# symlink for JRE
RUN mkdir -p /usr/lib/jvm/default-jvm \
    && ln -s /opt/java/openjdk /usr/lib/jvm/default-jvm/jre

# # create jetty user
# RUN useradd -ms /bin/sh --uid 1000 jetty \
#     && usermod -a -G root jetty

# # adjust ownership
# RUN chown -R 1000:1000 /opt/gluu/jetty \
#     && chown -R 1000:1000 /deploy \
#     && chown -R 1000:1000 /opt/shared-shibboleth-idp \
#     && chown -R 1000:1000 /opt/shibboleth-idp \
#     && chmod -R g+w /usr/lib/jvm/default-jvm/jre/lib/security/cacerts \
#     && chgrp -R 0 /opt/gluu/jetty && chmod -R g=u /opt/gluu/jetty \
#     && chgrp -R 0 /opt/shared-shibboleth-idp && chmod -R g=u /opt/shared-shibboleth-idp \
#     && chgrp -R 0 /opt/shibboleth-idp && chmod -R g=u /opt/shibboleth-idp \
#     && chgrp -R 0 /etc/certs && chmod -R g=u /etc/certs \
#     && chgrp -R 0 /etc/gluu && chmod -R g=u /etc/gluu \
#     && chgrp -R 0 /deploy && chmod -R g=u /deploy

# # run as non-root user
# USER 1000

ENTRYPOINT ["tini", "-g", "--"]
CMD ["sh", "/app/scripts/entrypoint.sh"]
