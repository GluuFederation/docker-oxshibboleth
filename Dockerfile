FROM adoptopenjdk/openjdk11:alpine-jre

# symlink JVM
RUN mkdir -p /usr/lib/jvm/default-jvm /usr/java/latest \
    && ln -sf /opt/java/openjdk /usr/lib/jvm/default-jvm/jre \
    && ln -sf /usr/lib/jvm/default-jvm/jre /usr/java/latest/jre

# ===============
# Alpine packages
# ===============

RUN apk update \
    && apk add --no-cache openssl py3-pip tini \
    && apk add --no-cache --virtual build-deps wget git

# =====
# Jetty
# =====

ARG JETTY_VERSION=9.4.26.v20200117
ARG JETTY_HOME=/opt/jetty
ARG JETTY_BASE=/opt/gluu/jetty
ARG JETTY_USER_HOME_LIB=/home/jetty/lib

# Install jetty
RUN wget -q https://repo1.maven.org/maven2/org/eclipse/jetty/jetty-distribution/${JETTY_VERSION}/jetty-distribution-${JETTY_VERSION}.tar.gz -O /tmp/jetty.tar.gz \
    && mkdir -p /opt \
    && tar -xzf /tmp/jetty.tar.gz -C /opt \
    && mv /opt/jetty-distribution-${JETTY_VERSION} ${JETTY_HOME} \
    && rm -rf /tmp/jetty.tar.gz

# Ports required by jetty
EXPOSE 8080

# ============
# oxShibboleth
# ============

ARG GLUU_VERSION=4.2.0-SNAPSHOT
ARG GLUU_BUILD_DATE="2020-06-18 13:55"

# Install oxShibboleth WAR
RUN wget -q https://ox.gluu.org/maven/org/gluu/oxshibbolethIdp/${GLUU_VERSION}/oxshibbolethIdp-${GLUU_VERSION}.war -O /tmp/oxshibboleth.war \
    && mkdir -p ${JETTY_BASE}/idp/webapps/idp \
    && unzip -qq /tmp/oxshibboleth.war -d ${JETTY_BASE}/idp/webapps/idp \
    && java -jar ${JETTY_HOME}/start.jar jetty.home=${JETTY_HOME} jetty.base=${JETTY_BASE}/idp --add-to-start=server,deploy,annotations,resources,http,http-forwarded,threadpool,jsp \
    && rm -f /tmp/oxshibboleth.war

# Install Shibboleth JAR
RUN wget -q https://ox.gluu.org/maven/org/gluu/oxShibbolethStatic/${GLUU_VERSION}/oxShibbolethStatic-${GLUU_VERSION}.jar -O /tmp/shibboleth-idp.jar \
    && unzip -qq /tmp/shibboleth-idp.jar -d /opt \
    && rm -rf /opt/META-INF \
    && rm -f /tmp/shibboleth-idp.jar

# RUN mkdir -p /opt/shibboleth-idp/lib \
#     && cp ${JETTY_BASE}/idp/webapps/idp/WEB-INF/lib/saml-openid-auth-client-${GLUU_VERSION}.jar /opt/shibboleth-idp/lib/

# ======
# rclone
# ======

ARG RCLONE_VERSION=v1.51.0
RUN wget -q https://github.com/rclone/rclone/releases/download/${RCLONE_VERSION}/rclone-${RCLONE_VERSION}-linux-amd64.zip -O /tmp/rclone.zip \
    && unzip -qq /tmp/rclone.zip -d /tmp \
    && mv /tmp/rclone-${RCLONE_VERSION}-linux-amd64/rclone /usr/bin/ \
    && rm -rf /tmp/rclone-${RCLONE_VERSION}-linux-amd64 /tmp/rclone.zip

# ======
# Python
# ======

RUN apk add --no-cache py3-cryptography
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -U pip \
    && pip3 install --no-cache-dir -r /tmp/requirements.txt

# =======
# Cleanup
# =======

RUN apk del build-deps \
    && rm -rf /var/cache/apk/*

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

ENV GLUU_PERSISTENCE_TYPE=ldap \
    GLUU_PERSISTENCE_LDAP_MAPPING=default \
    GLUU_LDAP_URL=localhost:1636 \
    GLUU_COUCHBASE_URL=localhost \
    GLUU_COUCHBASE_USER=admin \
    GLUU_COUCHBASE_CERT_FILE=/etc/certs/couchbase.crt \
    GLUU_COUCHBASE_PASSWORD_FILE=/etc/gluu/conf/couchbase_password \
    GLUU_COUCHBASE_CONN_TIMEOUT=10000 \
    GLUU_COUCHBASE_CONN_MAX_WAIT=20000 \
    GLUU_COUCHBASE_SCAN_CONSISTENCY=not_bounded

# ===========
# Generic ENV
# ===========

ENV GLUU_MAX_RAM_PERCENTAGE=75.0 \
    GLUU_WAIT_MAX_TIME=300 \
    GLUU_WAIT_SLEEP_DURATION=10 \
    GLUU_OXTRUST_BACKEND=localhost:8082 \
    GLUU_DOCUMENT_STORE_TYPE=LOCAL \
    GLUU_JCA_URL=http://localhost:8080 \
    GLUU_JCA_USERNAME=admin \
    GLUU_JCA_PASSWORD_FILE=/etc/gluu/conf/jca_password \
    GLUU_JCA_SYNC_INTERVAL=300

# ==========
# misc stuff
# ==========

LABEL name="oxShibboleth" \
    maintainer="Gluu Inc. <support@gluu.org>" \
    vendor="Gluu Federation" \
    version="4.2.0" \
    release="dev" \
    summary="Gluu oxShibboleth" \
    description="Shibboleth project for the Gluu Server's SAML IDP functionality"

RUN mkdir -p /opt/shibboleth-idp/metadata/credentials \
    /opt/shibboleth-idp/logs \
    /opt/shibboleth-idp/lib \
    /opt/shibboleth-idp/conf/authn \
    /opt/shibboleth-idp/credentials \
    /opt/shibboleth-idp/webapp \
    /etc/certs \
    /etc/gluu/conf \
    /deploy \
    /app

COPY static /app/static
RUN cp /app/static/idp3/password-authn-config.xml /opt/shibboleth-idp/conf/authn/ \
    && cp /app/static/idp3/oxauth-supported-principals.xml /opt/shibboleth-idp/conf/authn/

COPY templates /app/templates
COPY scripts /app/scripts
RUN chmod +x /app/scripts/entrypoint.sh

ENTRYPOINT ["tini", "-e", "143", "-g", "--"]
CMD ["sh", "/app/scripts/entrypoint.sh"]
