import contextlib
import glob
import logging.config
import os
import time

from pygluu.containerlib.document import RClone

from settings import LOGGING_CONFIG

ROOT_DIR = "/repository/default"
SYNC_DIR = "/opt/shibboleth-idp"

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("webdav")


def sync_from_webdav(url, username, password):
    rclone = RClone(url, username, password)
    rclone.configure()

    logger.info(f"Sync files with remote directory {url}{ROOT_DIR}{SYNC_DIR}")
    rclone.copy_from(SYNC_DIR, SYNC_DIR)


def prune_local_tr(url, username, password):
    def remote_tr_files(files):
        for f in files:
            f = f.strip().split(" ")[1]
            if f.endswith("-sp-metadata.xml"):
                yield f

    rclone = RClone(url, username, password)
    rclone.configure()

    logger.info(f"Removing obsolete local TR files (if any)")
    out = rclone.ls("/opt/shibboleth-idp/metadata")
    files = tuple(remote_tr_files(out.decode().splitlines()))

    for file_ in glob.iglob("/opt/shibboleth-idp/metadata/*-sp-metadata.xml"):
        basename = os.path.basename(file_)
        if basename in files:
            continue

        with contextlib.suppress(FileNotFoundError):
            os.unlink(file_)


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


def get_jackrabbit_url():
    if "GLUU_JCA_URL" in os.environ:
        return os.environ["GLUU_JCA_URL"]
    return os.environ.get("GLUU_JACKRABBIT_URL", "http://localhost:8080")


def main():
    store_type = os.environ.get("GLUU_DOCUMENT_STORE_TYPE", "LOCAL")
    if store_type != "JCA":
        logger.warning(f"Using {store_type} document store; sync is disabled ...")
        return

    url = get_jackrabbit_url()

    admin_id = "admin"
    admin_id_file = os.environ.get("GLUU_JACKRABBIT_ADMIN_ID_FILE", "/etc/gluu/conf/jackrabbit_admin_id")
    with contextlib.suppress(FileNotFoundError):
        with open(admin_id_file) as f:
            admin_id = f.read().strip()

    username = password = admin_id

    sync_interval = get_sync_interval()
    try:
        while True:
            sync_from_webdav(url, username, password)
            prune_local_tr(url, username, password)
            time.sleep(sync_interval)
    except KeyboardInterrupt:
        logger.warning("Canceled by user; exiting ...")


if __name__ == "__main__":
    main()
