#!/bin/sh
set -e

# =========
# FUNCTIONS
# =========

run_wait() {
    python /app/scripts/wait.py
}

run_entrypoint() {
    if [ ! -f /deploy/touched ]; then
        python /app/scripts/entrypoint.py
        touch /deploy/touched
    fi
}

run_sync_jca() {
    python /app/scripts/jca_sync.py &
}

# ==========
# ENTRYPOINT
# ==========

run_wait
run_sync_jca
run_entrypoint

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
