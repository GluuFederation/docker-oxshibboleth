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
    if [ -n "$(ls -A $GLUU_SHIB_SOURCE_DIR/ 2>/dev/null)" ]; then
        cp -r $GLUU_SHIB_SOURCE_DIR/* $GLUU_SHIB_TARGET_DIR/
    fi
}

if [ ! -f /deploy/touched ]; then
    if [ -f /touched ]; then
        # backward-compat
        mv /touched /deploy/touched
    else
        if [ -f /etc/redhat-release ]; then
            source scl_source enable ptyhon27 && python /opt/scripts/wait_for.py --deps="config,secret,ldap" && python /opt/scripts/entrypoint.py
        else
            python /opt/scripts/wait_for.py --deps="config,secret,ldap" && python /opt/scripts/entrypoint.py
        fi

        import_ssl_cert
        pull_shared_shib_files
        touch /deploy/touched
    fi
fi

# monitor filesystem changes in Shibboleth-related files
sh /opt/scripts/shibwatcher.sh &

cd /opt/gluu/jetty/idp
exec java -jar /opt/jetty/start.jar \
    -server \
    -XX:+DisableExplicitGC \
    -XX:+UnlockExperimentalVMOptions \
    -XX:+UseCGroupMemoryLimitForHeap \
    -XX:MaxRAMFraction=$GLUU_MAX_RAM_FRACTION \
    -Dgluu.base=/etc/gluu \
    -Dserver.base=/opt/gluu/jetty/idp
