#!/bin/sh
set -e

if [ ! -f /touched ]; then
    python /opt/scripts/entrypoint.py
    touch /touched
fi

cd /opt/gluu/jetty/idp
exec java -jar /opt/jetty/start.jar -server \
    -Xms256m -Xmx2048m -XX:+DisableExplicitGC \
    -Dgluu.base=/etc/gluu \
    -Dserver.base=/opt/gluu/jetty/idp
