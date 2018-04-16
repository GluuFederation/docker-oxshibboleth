#!/bin/sh
set -e

import_ssl_cert() {
    if [ -f /etc/certs/gluu_https.crt ]; then
        openssl x509 -outform der -in /etc/certs/gluu_https.crt -out /etc/certs/gluu_https.der
        keytool -importcert -trustcacerts \
            -alias gluu_https \
            -file /etc/certs/gluu_https.der \
            -keystore /usr/lib/jvm/default-jvm/jre/lib/security/cacerts \
            -storepass changeit \
            -noprompt
    fi
}

pull_shared_shib_files() {
    mkdir -p $GLUU_SHIB_TARGET_DIR $GLUU_SHIB_SOURCE_DIR
    # sync existing files in source directory (mapped volume)
    if [ ! -z $(ls -A $GLUU_SHIB_SOURCE_DIR) ]; then
        cp -R $GLUU_SHIB_SOURCE_DIR/* $GLUU_SHIB_TARGET_DIR/
    fi
}

if [ ! -f /touched ]; then
    python /opt/scripts/entrypoint.py
    import_ssl_cert
    pull_shared_shib_files
    touch /touched
fi

# monitor filesystem changes in Shibboleth-related files
sh /opt/scripts/shibwatcher.sh &

cd /opt/gluu/jetty/idp
exec java -jar /opt/jetty/start.jar -server \
    -Xms256m -Xmx2048m -XX:+DisableExplicitGC \
    -Dgluu.base=/etc/gluu \
    -Dserver.base=/opt/gluu/jetty/idp
