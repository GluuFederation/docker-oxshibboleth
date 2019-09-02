#!/bin/sh
set -e

# =========
# FUNCTIONS
# =========

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

# ==========
# ENTRYPOINT
# ==========

cat << LICENSE_ACK

# ================================================================================================ #
# Gluu License Agreement: https://github.com/GluuFederation/enterprise-edition/blob/4.0.0/LICENSE. #
# The use of Gluu Server Enterprise Edition is subject to the Gluu Support License.                #
# ================================================================================================ #

LICENSE_ACK

# check persistence type
case "${GLUU_PERSISTENCE_TYPE}" in
    ldap|couchbase|hybrid)
        ;;
    *)
        echo "unsupported GLUU_PERSISTENCE_TYPE value; please choose 'ldap', 'couchbase', or 'hybrid'"
        exit 1
        ;;
esac

# check mapping used by LDAP
if [ "${GLUU_PERSISTENCE_TYPE}" = "hybrid" ]; then
    case "${GLUU_PERSISTENCE_LDAP_MAPPING}" in
        default|user|cache|site|token)
            ;;
        *)
            echo "unsupported GLUU_PERSISTENCE_LDAP_MAPPING value; please choose 'default', 'user', 'cache', 'site', or  'token'"
            exit 1
            ;;
    esac
fi

# run wait_for functions
deps="config,secret"

if [ "${GLUU_PERSISTENCE_TYPE}" = "hybrid" ]; then
    deps="${deps},ldap,couchbase"
else
    deps="${deps},${GLUU_PERSISTENCE_TYPE}"
fi

if [ -f /etc/redhat-release ]; then
    source scl_source enable python27 && gluu-wait --deps="$deps"
else
    gluu-wait --deps="$deps"
fi

if [ ! -f /deploy/touched ]; then
    if [ -f /touched ]; then
        # backward-compat
        mv /touched /deploy/touched
    else
        if [ -f /etc/redhat-release ]; then
            source scl_source enable python27 && python /app/scripts/entrypoint.py
        else
            python /app/scripts/entrypoint.py
        fi

        import_ssl_cert
        pull_shared_shib_files
        touch /deploy/touched
    fi
fi

# monitor filesystem changes in Shibboleth-related files
sh /app/scripts/shibwatcher.sh &

cd /opt/gluu/jetty/idp
exec java -jar /opt/jetty/start.jar \
    -server \
    -XX:+DisableExplicitGC \
    -XX:+UseContainerSupport \
    -XX:MaxRAMPercentage=$GLUU_MAX_RAM_PERCENTAGE \
    -Dgluu.base=/etc/gluu \
    -Dserver.base=/opt/gluu/jetty/idp \
    -Dorg.ldaptive.provider=org.ldaptive.provider.unboundid.UnboundIDProvider
