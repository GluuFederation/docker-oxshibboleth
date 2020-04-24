import logging.config
import os
import shutil
import time

from webdav3.client import Client
from webdav3.exceptions import RemoteResourceNotFound
from webdav3.exceptions import NoConnection

from settings import LOGGING_CONFIG

LOCAL_DIR = "/opt/webdav"
REMOTE_DIR = "repository/default/opt/shibboleth-idp"

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("webdav")


def sync_from_webdav(url, username, password):
    options = {
        "webdav_hostname": url,
        "webdav_login": username,
        "webdav_password": password,
    }
    client = Client(options)

    try:
        logger.info(f"Sync files from remote directory {url}/{REMOTE_DIR} into local directory {LOCAL_DIR}")
        # download remote dirs to new directory
        client.download_sync(REMOTE_DIR, LOCAL_DIR)

        # copy all downloaded files to /opt/shibboleth-idp
        for subdir, _, files in os.walk(LOCAL_DIR):
            for file_ in files:
                src = os.path.join(subdir, file_)
                dest = src.replace(LOCAL_DIR, "/opt/shibboleth-idp")

                if not os.path.exists(os.path.dirname(dest)):
                    os.makedirs(os.path.dirname(dest))

                logger.info(f"Copying {src} to {dest}")
                shutil.copyfile(src, dest)
    except (RemoteResourceNotFound, NoConnection) as exc:
        logger.warning(f"Unable to sync files from remote directory {url}/{REMOTE_DIR}; reason={exc}")


def get_sync_interval():
    default = 5 * 60  # 5 minutes

    try:
        interval = int(os.environ.get("GLUU_JCA_SYNC_INTERVAL", default))
    except ValueError:
        interval = default
    return interval


def main():
    url = os.environ.get("GLUU_JCA_URL", "http://localhost:8080")
    username = os.environ.get("GLUU_JCA_USERNAME", "admin")
    password = "admin"

    password_file = os.environ.get("GLUU_JCA_PASSWORD_FILE", "/etc/gluu/conf/jca_password")
    if os.path.isfile(password_file):
        with open(password_file) as f:
            password = f.read().strip()

    sync_interval = get_sync_interval()
    while True:
        sync_from_webdav(url, username, password)
        time.sleep(sync_interval)


if __name__ == "__main__":
    main()
