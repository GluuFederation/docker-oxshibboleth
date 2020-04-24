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

# ==========
# ENTRYPOINT
# ==========

if [ -f /etc/redhat-release ]; then
    source scl_source enable python27 && run_wait
    source scl_source enable python27 && run_entrypoint
else
    run_wait
    run_entrypoint
fi

# sync files from JCR/webdav
python3 /app/scripts/jca_sync.py &

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
