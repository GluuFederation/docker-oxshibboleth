import base64
import glob
import os
import re
import shlex
import subprocess

import pyDes

from gluulib import get_manager

GLUU_LDAP_URL = os.environ.get("GLUU_LDAP_URL", "localhost:1636")

manager = get_manager()


def safe_render(text, ctx):
    text = re.sub(r"%([^\(])", r"%%\1", text)
    # There was a % at the end?
    text = re.sub(r"%$", r"%%", text)
    return text % ctx


def render_templates():
    ldap_hostname, ldaps_port = GLUU_LDAP_URL.split(":")
    ctx = {
        "hostname": manager.config.get("hostname"),
        "shibJksPass": manager.secret.get("shibJksPass"),
        "certFolder": "/etc/certs",
        "ldap_hostname": ldap_hostname,
        "ldaps_port": ldaps_port,
        "ldap_binddn": manager.config.get("ldap_binddn"),
        "ldapPass": decrypt_text(manager.secret.get("encoded_ox_ldap_pw"), manager.secret.get("encoded_salt")),
        "inumOrg": manager.config.get("inumOrg"),
        "idp3SigningCertificateText": load_cert_text("/etc/certs/idp-signing.crt"),
        "idp3EncryptionCertificateText": load_cert_text("/etc/certs/idp-encryption.crt"),
        "orgName": manager.config.get("orgName"),
        "ldapCertFn": "/etc/certs/{}.crt".format(manager.config.get("ldap_type")),
    }

    for file_path in glob.glob("/opt/templates/*.properties"):
        with open(file_path) as fr:
            rendered_content = safe_render(fr.read(), ctx)
            fn = os.path.basename(file_path)
            with open("/opt/shibboleth-idp/conf/{}".format(fn), 'w') as fw:
                fw.write(rendered_content)

    file_path = "/opt/templates/idp-metadata.xml"
    with open(file_path) as fr:
        rendered_content = safe_render(fr.read(), ctx)
        fn = os.path.basename(file_path)
        with open("/opt/shibboleth-idp/metadata/{}".format(fn), 'w') as fw:
            fw.write(rendered_content)


def exec_cmd(cmd):
    """Executes shell command.
    :param cmd: String of shell command.
    :returns: A tuple consists of stdout, stderr, and return code
              returned from shell command execution.
    """
    args = shlex.split(cmd)
    popen = subprocess.Popen(args,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    stdout, stderr = popen.communicate()
    retcode = popen.returncode
    return stdout, stderr, retcode


def load_cert_text(path):
    with open(path) as f:
        cert = f.read()
        return cert.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').strip()


def sync_idp_certs():
    cert = manager.secret.get("idp3SigningCertificateText")
    with open("/etc/certs/idp-signing.crt", "w") as f:
        f.write(cert)

    cert = manager.secret.get("idp3EncryptionCertificateText")
    with open("/etc/certs/idp-encryption.crt", "w") as f:
        f.write(cert)


def sync_idp_keys():
    key = manager.secret.get("idp3SigningKeyText")
    with open("/etc/certs/idp-signing.key", "w") as f:
        f.write(key)

    key = manager.secret.get("idp3EncryptionKeyText")
    with open("/etc/certs/idp-encryption.key", "w") as f:
        f.write(key)


def render_salt():
    encode_salt = manager.secret.get("encoded_salt")

    with open("/opt/templates/salt.tmpl") as fr:
        txt = fr.read()
        with open("/etc/gluu/conf/salt", "w") as fw:
            rendered_txt = txt % {"encode_salt": encode_salt}
            fw.write(rendered_txt)


def render_ldap_properties():
    with open("/opt/templates/ox-ldap.properties.tmpl") as fr:
        txt = fr.read()

        with open("/etc/gluu/conf/ox-ldap.properties", "w") as fw:
            rendered_txt = txt % {
                "ldap_binddn": manager.config.get("ldap_binddn"),
                "encoded_ox_ldap_pw": manager.secret.get("encoded_ox_ldap_pw"),
                "inumAppliance": manager.config.get("inumAppliance"),
                "ldap_url": GLUU_LDAP_URL,
                "ldapTrustStoreFn": manager.config.get("ldapTrustStoreFn"),
                "encoded_ldapTrustStorePass": manager.secret.get("encoded_ldapTrustStorePass")
            }
            fw.write(rendered_txt)


def decrypt_text(encrypted_text, key):
    cipher = pyDes.triple_des(b"{}".format(key), pyDes.ECB,
                              padmode=pyDes.PAD_PKCS5)
    encrypted_text = b"{}".format(base64.b64decode(encrypted_text))
    return cipher.decrypt(encrypted_text)


def sync_ldap_pkcs12():
    pkcs = decrypt_text(manager.secret.get("ldap_pkcs12_base64"),
                        manager.secret.get("encoded_salt"))

    with open(manager.config.get("ldapTrustStoreFn"), "wb") as fw:
        fw.write(pkcs)


def sync_ldap_cert():
    cert = decrypt_text(manager.secret.get("ldap_ssl_cert"),
                        manager.secret.get("encoded_salt"))

    with open("/etc/certs/{}.crt".format(manager.config.get("ldap_type")), "wb") as fw:
        fw.write(cert)


def sync_idp_jks():
    jks = decrypt_text(manager.secret.get("shibIDP_jks_base64"),
                       manager.secret.get("encoded_salt"))

    with open("/etc/certs/shibIDP.jks", "wb") as fw:
        fw.write(jks)


def render_ssl_cert():
    ssl_cert = manager.secret.get("ssl_cert")
    if ssl_cert:
        with open("/etc/certs/gluu_https.crt", "w") as fd:
            fd.write(ssl_cert)


def render_ssl_key():
    ssl_key = manager.secret.get("ssl_key")
    if ssl_key:
        with open("/etc/certs/gluu_https.key", "w") as fd:
            fd.write(ssl_key)


def sync_sealer_jks():
    jks = decrypt_text(manager.secret.get("sealer_jks_base64"),
                       manager.secret.get("encoded_salt"))

    with open("/opt/shibboleth-idp/credentials/sealer.jks", "wb") as fw:
        fw.write(jks)


def modify_jetty_xml():
    fn = "/opt/jetty/etc/jetty.xml"
    with open(fn) as f:
        txt = f.read()

    # disable contexts
    updates = re.sub(
        r'<New id="DefaultHandler" class="org.eclipse.jetty.server.handler.DefaultHandler"/>',
        r'<New id="DefaultHandler" class="org.eclipse.jetty.server.handler.DefaultHandler">\n\t\t\t\t <Set name="showContexts">false</Set>\n\t\t\t </New>',
        txt,
        flags=re.DOTALL | re.M,
    )

    # disable Jetty version info
    updates = re.sub(
        r'(<Set name="sendServerVersion"><Property name="jetty.httpConfig.sendServerVersion" deprecated="jetty.send.server.version" default=")true(" /></Set>)',
        r'\1false\2',
        updates,
        flags=re.DOTALL | re.M,
    )

    with open(fn, "w") as f:
        f.write(updates)


def modify_webdefault_xml():
    fn = "/opt/jetty/etc/webdefault.xml"
    with open(fn) as f:
        txt = f.read()

    # disable dirAllowed
    updates = re.sub(
        r'(<param-name>dirAllowed</param-name>)(\s*)(<param-value>)true(</param-value>)',
        r'\1\2\3false\4',
        txt,
        flags=re.DOTALL | re.M,
    )

    with open(fn, "w") as f:
        f.write(updates)


if __name__ == "__main__":
    sync_idp_certs()
    sync_idp_keys()
    sync_idp_jks()
    render_templates()
    sync_sealer_jks()
    render_salt()
    render_ldap_properties()
    sync_ldap_pkcs12()
    sync_ldap_cert()
    render_ssl_cert()
    render_ssl_key()
    modify_jetty_xml()
    modify_webdefault_xml()
