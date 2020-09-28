#!/bin/sh
set -e

# ==========
# ENTRYPOINT
# ==========

python3 /app/scripts/wait.py
python3 /app/scripts/jca_sync.py &

if [ ! -f /deploy/touched ]; then
    python3 /app/scripts/entrypoint.py
    touch /deploy/touched
fi

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
    -Dpython.home=/opt/jython \
    ${GLUU_JAVA_OPTIONS} \
    -jar /opt/jetty/start.jar
