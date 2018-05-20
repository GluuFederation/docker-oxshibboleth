# Docker - oxShibboleth

oxShibboleth is a Gluu Server implementation of the single sign-on Shibboleth system, packaged in a Docker image.

## Environment Variables

- `GLUU_KV_HOST`: host/IP address of Consul server
- `GLUU_KV_PORT`: port where Consul server is listening
- `GLUU_LDAP_URL`: URL to LDAP server (in `host:port` format)
- `GLUU_SHIB_SOURCE_DIR`: absolute path to directory that shared Shibboleth files are copied from
- `GLUU_SHIB_TARGET_DIR`: absolute path to directory that shared Shibboleth files are copied to

## Volumes

- `/opt/shared-shibboleth-idp`: a directory where Shibboleth configuration, metadata, etc are shared between the oxTrust and oxShibboleth containers

## Running Container

Here's an example of how to run the container:

```
docker run \
    -d \
    -v $PWD/shared-shibboleth-idp:/opt/shared-shibboleth-idp \
    -e GLUU_KV_HOST=consul.example.com \
    -e GLUU_KV_PORT=8500 \
    -e GLUU_LDAP_URL=ldap.example.com:1636 \
    -p 8086:8080
    gluufederation/oxshibboleth:3.1.3_dev
```

## Design Decisions

1.  Mounting the volume from host to container, as seen in the `-v $PWD/shared-shibboleth-idp:/opt/shared-shibboleth-idp` option, is required to ensure oxShibboleth can load the configuration correctly.

    By design, each time a Trust Relationship entry is added/updated/deleted via oxTrust GUI, some Shibboleth-related files will be generated/modified by oxTrust and saved to `/opt/shibboleth-idp` directory inside the oxTrust container. A background job in oxTrust container ensures those files are copied to `/opt/shared-shibboleth-idp` directory (also inside the oxTrust container, which must be mounted from container to host).

    After those Shibboleth-related files are copied to `/opt/shared-shibboleth`, a background job in oxShibboleth copies them to the `/opt/shibboleth-idp` directory inside oxShibboleth container. To ensure files are synchronized between oxTrust and oxShibboleth, both containers must use a same mounted volume `/opt/shared-shibboleth-idp`.

2.  The `/opt/shibboleth-idp` directory is not mounted directly into the container, as there are two known issues with this approach. First, oxShibboleth container has its own default `/opt/shibboleth-idp` directory required to start the app itself. By mounting `/opt/shibboleth-idp` directly from the host, the directory will be replaced and the oxShibboleth app won't run correctly. Secondly, oxTrust _renames_ the metadata file, which unfortunately didn't work as expected in the mounted volume.
