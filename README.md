# docker-oxshibboleth

Docker image packaging for oxShibboleth

## Environment Variables

- `GLUU_KV_HOST`: host/IP address of Consul server.
- `GLUU_KV_PORT`: port where Consul server is listening to.
- `GLUU_LDAP_URL`: URL to LDAP server (in `host:port` format).
- `GLUU_SHIB_SOURCE_DIR`: absolute path to directory where shared Shibboleth files are copied from.
- `GLUU_SHIB_TARGET_DIR`: absolute path to directory where shared Shibboleth files are copied to.

## Volumes

- `/opt/shared-shibboleth-idp`: a directory where Shibboleth config, metadata, etc are shared between oxTrust and oxShibboleth containers.

## Running Container

Here's an example on how to run the container:

```
docker run \
    -d \
    -v $PWD/shared-shibboleth-idp:/opt/shibboleth-idp \
    -e GLUU_KV_HOST=consul.example.com \
    -e GLUU_KV_PORT=8500 \
    -e GLUU_LDAP_URL=ldap.example.com:1636 \
    gluufederation/oxshibboleth:3.1.2_dev
```

## Design Decisions

1.  Mounting the volume from host to container, as seen on `-v $PWD/shared-shibboleth-idp:/opt/shared-shibboleth-idp` option,
    is required to ensure oxShibboleth can load the configuration correctly.

    By design, each time a Trust Relationship entry added/updated/deleted via oxTrust GUI,
    some Shibboleth-related files will be generated/modified by oxTrust and saved to `/opt/shibboleth-idp` directory
    inside the oxTrust container. A background job in oxTrust container ensures those files are copied to `/opt/shared-shibboleth-idp`
    directory (also inside oxTrust container, which must be mounted from container to host).

    After those Shibboleth-related files copied to `/opt/shared-shibboleth`, a background job in oxShibboleth copies them
    to `/opt/shibboleth-idp` directory inside oxShibboleth container. To ensure files are synchronized between oxTrust and oxShibboleth,
    both containers must use a same mounted volume `/opt/shared-shibboleth-idp`.

2.  The `/opt/shibboleth-idp` directory is not mounted directly into container as there are 2 known-issues with this approach.
    First of all, oxShibboleth container has its own default `/opt/shibboleth-idp` directory required to start the app itself.
    By mounting `/opt/shibboleth-idp` directly from host, the directory will be replaced and oxShibboleth app won't run correctly.
    Secondly, oxTrust _renames_ metadata file which unfortunately didn't work as expected in mounted volume.
