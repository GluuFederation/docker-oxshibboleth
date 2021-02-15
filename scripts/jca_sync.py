import contextlib
import glob
import logging.config
import os
import shutil
import time

from webdav3.client import Client
from webdav3.exceptions import RemoteResourceNotFound
from webdav3.exceptions import NoConnection

from settings import LOGGING_CONFIG

ROOT_DIR = "/repository/default"
SYNC_DIR = "/opt/shibboleth-idp"
TMP_DIR = "/tmp/webdav"

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("webdav")


def sync_from_webdav(url, username, password):
    client = Client({
        "webdav_hostname": url,
        "webdav_login": username,
        "webdav_password": password,
        "webdav_root": ROOT_DIR,
    })
    client.verify = False

    try:
        logger.info(f"Sync files from {url}{ROOT_DIR}{SYNC_DIR}")
        # download files to temporary directory to avoid `/opt/shibboleth-idp`
        # getting deleted
        client.download(SYNC_DIR, TMP_DIR)

        # copy all downloaded files to /opt/shibboleth-idp
        for subdir, _, files in os.walk(TMP_DIR):
            for file_ in files:
                src = os.path.join(subdir, file_)
                dest = src.replace(TMP_DIR, SYNC_DIR)

                if not os.path.exists(os.path.dirname(dest)):
                    os.makedirs(os.path.dirname(dest))
                # logger.info(f"Copying {src} to {dest}")
                shutil.copyfile(src, dest)
    except (RemoteResourceNotFound, NoConnection) as exc:
        logger.warning(f"Unable to sync files from {url}{ROOT_DIR}{SYNC_DIR}; reason={exc}")


def get_jackrabbit_url():
    if "GLUU_JCA_URL" in os.environ:
        return os.environ["GLUU_JCA_URL"]
    return os.environ.get("GLUU_JACKRABBIT_URL", "http://localhost:8080")


def get_sync_interval():
    default = 5 * 60  # 5 minutes

    if "GLUU_JCA_SYNC_INTERVAL" in os.environ:
        env_name = "GLUU_JCA_SYNC_INTERVAL"
    else:
        env_name = "GLUU_JACKRABBIT_SYNC_INTERVAL"

    try:
        interval = int(os.environ.get(env_name, default))
    except ValueError:
        interval = default
    return interval


def main():
    store_type = os.environ.get("GLUU_DOCUMENT_STORE_TYPE", "LOCAL")
    if store_type != "JCA":
        logger.warning(f"Using {store_type} document store; sync is disabled ...")
        return

    url = get_jackrabbit_url()

    username = os.environ.get("GLUU_JACKRABBIT_ADMIN_ID", "admin")
    password = ""

    password_file = os.environ.get(
        "GLUU_JACKRABBIT_ADMIN_PASSWORD_FILE",
        "/etc/gluu/conf/jackrabbit_admin_password",
    )
    with contextlib.suppress(FileNotFoundError):
        with open(password_file) as f:
            password = f.read().strip()
    password = password or username

    sync_interval = get_sync_interval()
    try:
        while True:
            sync_from_webdav(url, username, password)
            prune_local_tr(url, username, password)
            time.sleep(sync_interval)
    except KeyboardInterrupt:
        logger.warning("Canceled by user; exiting ...")


def prune_local_tr(url, username, password):
    def remote_tr_files(files):
        for f in files:
            if f.endswith("-sp-metadata.xml"):
                yield f

    client = Client({
        "webdav_hostname": url,
        "webdav_login": username,
        "webdav_password": password,
        "webdav_root": ROOT_DIR,
    })
    client.verify = False

    try:
        logger.info("Removing obsolete local TR files (if any)")

        files = client.list("/opt/shibboleth-idp/metadata")
        files = tuple(remote_tr_files(files))

        for file_ in glob.iglob("/opt/shibboleth-idp/metadata/*-sp-metadata.xml"):
            basename = os.path.basename(file_)
            if basename in files:
                continue

            with contextlib.suppress(FileNotFoundError):
                os.unlink(file_)
    except (RemoteResourceNotFound, NoConnection) as exc:
        logger.warning(f"Unable to get TR files from {url}{ROOT_DIR}{SYNC_DIR}/metadata; reason={exc}")


if __name__ == "__main__":
    main()
