#!/bin/sh
set -e

# =========
# FUNCTIONS
# =========

pull_shared_shib_files() {
    mkdir -p $GLUU_SHIB_TARGET_DIR $GLUU_SHIB_SOURCE_DIR
    if [ -n "$(ls -A $GLUU_SHIB_SOURCE_DIR/ 2>/dev/null)" ]; then
        cp -r $GLUU_SHIB_SOURCE_DIR/* $GLUU_SHIB_TARGET_DIR/
    fi
}

run_wait() {
    python /app/scripts/wait.py
}

run_entrypoint() {
    if [ ! -f /deploy/touched ]; then
        python /app/scripts/entrypoint.py
        touch /deploy/touched
    fi
    pull_shared_shib_files
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

if [ -f /etc/redhat-release ]; then
    source scl_source enable python27 && run_wait
    source scl_source enable python27 && run_entrypoint
else
    run_wait
    run_entrypoint
fi

# monitor filesystem changes in Shibboleth-related files
sh /app/scripts/shibwatcher.sh &

cd /opt/gluu/jetty/idp
exec java \
    -server \
    -XX:MaxGCPauseMillis=400 \
    -XX:+UseParallelGC \
    -XX:+DisableExplicitGC \
    -XX:+UseContainerSupport \
    -XX:MaxRAMPercentage=$GLUU_MAX_RAM_PERCENTAGE \
    -Dgluu.base=/etc/gluu \
    -Dserver.base=/opt/gluu/jetty/idp \
    -Dorg.ldaptive.provider=org.ldaptive.provider.unboundid.UnboundIDProvider \
    -jar /opt/jetty/start.jar
