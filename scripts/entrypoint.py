import base64
import glob
import os
import re
import shlex
import subprocess

import consulate
import pyDes

GLUU_LDAP_URL = os.environ.get("GLUU_LDAP_URL", "localhost:1636")
GLUU_KV_HOST = os.environ.get("GLUU_KV_HOST", "localhost")
GLUU_KV_PORT = os.environ.get("GLUU_KV_PORT", 8500)

consul = consulate.Consul(host=GLUU_KV_HOST, port=GLUU_KV_PORT)

CONFIG_PREFIX = "gluu/config/"


def merge_path(name):
    # example: `hostname` renamed to `gluu/config/hostname`
    return "".join([CONFIG_PREFIX, name])


def get_config(name, default=None):
    return consul.kv.get(merge_path(name), default)


def safe_render(text, ctx):
    text = re.sub(r"%([^\(])", r"%%\1", text)
    # There was a % at the end?
    text = re.sub(r"%$", r"%%", text)
    return text % ctx


def render_templates():
    ldap_hostname, ldaps_port = GLUU_LDAP_URL.split(":")
    ctx = {
        "hostname": get_config("hostname"),
        "shibJksPass": get_config("shibJksPass"),
        "certFolder": "/etc/certs",
        "ldap_hostname": ldap_hostname,
        "ldaps_port": ldaps_port,
        "ldap_protocol": "ldaps",
        "ldap_use_ssl": get_config("ldap_use_ssl"),
        "ldap_binddn": get_config("ldap_binddn"),
        "ldapPass": get_config("encoded_ldap_pw"),
        "inumOrg": get_config("inumOrg"),
        "idp3SigningCertificateText": load_cert_text("/etc/certs/idp-signing.crt"),
        "idp3EncryptionCertificateText": load_cert_text("/etc/certs/idp-encryption.crt"),
        "orgName": get_config("orgName"),
        "ldap_ssl_cert_fn": "/etc/certs/{}.crt".format(get_config("ldap_type")),
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


def gen_idp3_key():
    shibJksPass = get_config("shibJksPass")
    out, err, retcode = exec_cmd("java -classpath /tmp/idp3_cml_keygenerator.jar "
                                 "'org.xdi.oxshibboleth.keygenerator.KeyGenerator' "
                                 "/opt/shibboleth-idp/credentials {}".format(shibJksPass))
    return out, err, retcode


def load_cert_text(path):
    with open(path) as f:
        cert = f.read()
        return cert.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').strip()


def sync_idp_certs():
    cert = get_config("idp3SigningCertificateText")
    with open("/etc/certs/idp-signing.crt", "w") as f:
        f.write(cert)

    cert = get_config("idp3EncryptionCertificateText")
    with open("/etc/certs/idp-encryption.crt", "w") as f:
        f.write(cert)


def sync_idp_keys():
    key = get_config("idp3SigningKeyText")
    with open("/etc/certs/idp-signing.key", "w") as f:
        f.write(key)

    key = get_config("idp3EncryptionKeyText")
    with open("/etc/certs/idp-encryption.key", "w") as f:
        f.write(key)


def render_salt():
    encode_salt = get_config("encoded_salt")

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
                "ldap_binddn": get_config("ldap_binddn"),
                "encoded_ox_ldap_pw": get_config("encoded_ox_ldap_pw"),
                "inumAppliance": get_config("inumAppliance"),
                "ldap_url": GLUU_LDAP_URL,
                "ldapTrustStoreFn": get_config("ldapTrustStoreFn"),
                "encoded_ldapTrustStorePass": get_config("encoded_ldapTrustStorePass")
            }
            fw.write(rendered_txt)


def decrypt_text(encrypted_text, key):
    cipher = pyDes.triple_des(b"{}".format(key), pyDes.ECB,
                              padmode=pyDes.PAD_PKCS5)
    encrypted_text = b"{}".format(base64.b64decode(encrypted_text))
    return cipher.decrypt(encrypted_text)


def sync_ldap_pkcs12():
    pkcs = decrypt_text(get_config("ldap_pkcs12_base64"),
                        get_config("encoded_salt"))

    with open(get_config("ldapTrustStoreFn"), "wb") as fw:
        fw.write(pkcs)


def sync_ldap_cert():
    cert = decrypt_text(get_config("ldap_ssl_cert"),
                        get_config("encoded_salt"))

    with open("/etc/certs/{}.crt".format(get_config("ldap_type")), "wb") as fw:
        fw.write(cert)


def sync_idp_jks():
    jks = decrypt_text(get_config("shibIDP_jks_base64"),
                       get_config("encoded_salt"))

    with open("/etc/certs/shibIDP.jks", "wb") as fw:
        fw.write(jks)


def render_ssl_cert():
    ssl_cert = get_config("ssl_cert")
    if ssl_cert:
        with open("/etc/certs/gluu_https.crt", "w") as fd:
            fd.write(ssl_cert)


def render_ssl_key():
    ssl_key = get_config("ssl_key")
    if ssl_key:
        with open("/etc/certs/gluu_https.key", "w") as fd:
            fd.write(ssl_key)


if __name__ == "__main__":
    sync_idp_certs()
    sync_idp_keys()
    sync_idp_jks()
    render_templates()
    gen_idp3_key()
    render_salt()
    render_ldap_properties()
    sync_ldap_pkcs12()
    sync_ldap_cert()
    render_ssl_cert()
    render_ssl_key()
