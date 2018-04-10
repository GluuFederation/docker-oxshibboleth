#!/bin/sh
set -e

watch_shib_conf() {
    while inotifywait -r -e modify,create /opt/custom-shib-conf; do
        rsync -avz /opt/custom-shib-conf/* /opt/shibboleth-idp/conf
    done
}

if [ ! -f /touched ]; then
    python /opt/scripts/entrypoint.py
    touch /touched
fi

if [ -d /opt/custom-shib-conf ]; then
    watch_shib_conf &
fi

cd /opt/gluu/jetty/idp
exec java -jar /opt/jetty/start.jar -server \
    -Xms256m -Xmx2048m -XX:+DisableExplicitGC \
    -Dgluu.base=/etc/gluu \
    -Dserver.base=/opt/gluu/jetty/idp
