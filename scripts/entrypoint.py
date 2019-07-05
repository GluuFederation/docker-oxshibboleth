import base64
import glob
import os
import re
import shlex
import subprocess

import pyDes

from gluulib import get_manager
from cbm import CBM

GLUU_LDAP_URL = os.environ.get("GLUU_LDAP_URL", "localhost:1636")
GLUU_COUCHBASE_URL = os.environ.get("GLUU_COUCHBASE_URL", "localhost")
GLUU_PERSISTENCE_TYPE = os.environ.get("GLUU_PERSISTENCE_TYPE", "ldap")
GLUU_PERSISTENCE_LDAP_MAPPING = os.environ.get("GLUU_PERSISTENCE_LDAP_MAPPING", "default")

manager = get_manager()


def safe_render(text, ctx):
    text = re.sub(r"%([^\(])", r"%%\1", text)
    # There was a % at the end?
    text = re.sub(r"%$", r"%%", text)
    return text % ctx


def render_idp3_templates():
    ldap_hostname, ldaps_port = GLUU_LDAP_URL.split(":")
    ctx = {
        "hostname": manager.config.get("hostname"),
        "shibJksPass": manager.secret.get("shibJksPass"),
        "certFolder": "/etc/certs",
        "ldap_hostname": ldap_hostname,
        "ldaps_port": ldaps_port,
        "ldap_binddn": manager.config.get("ldap_binddn"),
        "ldapPass": decrypt_text(manager.secret.get("encoded_ox_ldap_pw"), manager.secret.get("encoded_salt")),
        "idp3SigningCertificateText": load_cert_text("/etc/certs/idp-signing.crt"),
        "idp3EncryptionCertificateText": load_cert_text("/etc/certs/idp-encryption.crt"),
        "orgName": manager.config.get("orgName"),
        "ldapCertFn": "/etc/certs/{}.crt".format(manager.config.get("ldap_type")),
        "couchbase_hostname": GLUU_COUCHBASE_URL,
        "couchbaseShibUserPassword": manager.secret.get("couchbase_shib_user_password"),
    }

    for file_path in glob.glob("/app/templates/idp3/*.properties"):
        with open(file_path) as fr:
            rendered_content = safe_render(fr.read(), ctx)
            fn = os.path.basename(file_path)
            with open("/opt/shibboleth-idp/conf/{}".format(fn), 'w') as fw:
                fw.write(rendered_content)

    file_path = "/app/templates/idp3/idp-metadata.xml"
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

    with open("/app/templates/salt.tmpl") as fr:
        txt = fr.read()
        with open("/etc/gluu/conf/salt", "w") as fw:
            rendered_txt = txt % {"encode_salt": encode_salt}
            fw.write(rendered_txt)


def render_ldap_properties():
    with open("/app/templates/gluu-ldap.properties.tmpl") as fr:
        txt = fr.read()

        ldap_hostname, ldaps_port = GLUU_LDAP_URL.split(":")

        with open("/etc/gluu/conf/gluu-ldap.properties", "w") as fw:
            rendered_txt = txt % {
                "ldap_binddn": manager.config.get("ldap_binddn"),
                "encoded_ox_ldap_pw": manager.secret.get("encoded_ox_ldap_pw"),
                "ldap_hostname": ldap_hostname,
                "ldaps_port": ldaps_port,
                "ldapTrustStoreFn": manager.config.get("ldapTrustStoreFn"),
                "encoded_ldapTrustStorePass": manager.secret.get("encoded_ldapTrustStorePass"),
            }
            fw.write(rendered_txt)


def get_couchbase_mappings():
    mappings = {
        "default": {
            "bucket": "gluu",
            "alias": "",
        },
        "user": {
            "bucket": "gluu_user",
            "alias": "people, groups"
        },
        "cache": {
            "bucket": "gluu_cache",
            "alias": "cache",
        },
        "statistic": {
            "bucket": "gluu_statistic",
            "alias": "statistic",
        },
        "site": {
            "bucket": "gluu_site",
            "alias": "site",
        }
    }

    if GLUU_PERSISTENCE_TYPE == "hybrid":
        mappings = {
            name: mapping for name, mapping in mappings.iteritems()
            if name != GLUU_PERSISTENCE_LDAP_MAPPING
        }

    return mappings


def render_couchbase_properties():
    _couchbase_mappings = get_couchbase_mappings()
    couchbase_buckets = []
    couchbase_mappings = []

    for _, mapping in _couchbase_mappings.iteritems():
        couchbase_buckets.append(mapping["bucket"])

        if not mapping["alias"]:
            continue

        couchbase_mappings.append("bucket.{0}.mapping: {1}".format(
            mapping["bucket"], mapping["alias"],
        ))

    # always have `gluu` as default bucket
    if "gluu" not in couchbase_buckets:
        couchbase_buckets.insert(0, "gluu")

    with open("/app/templates/gluu-couchbase.properties.tmpl") as fr:
        txt = fr.read()

        ldap_hostname, ldaps_port = GLUU_LDAP_URL.split(":")

        with open("/etc/gluu/conf/gluu-couchbase.properties", "w") as fw:
            rendered_txt = txt % {
                "hostname": GLUU_COUCHBASE_URL,
                "couchbase_server_user": manager.config.get("couchbase_server_user"),
                "encoded_couchbase_server_pw": manager.secret.get("encoded_couchbase_server_pw"),
                "couchbase_buckets": ", ".join(couchbase_buckets),
                "default_bucket": "gluu",
                "couchbase_mappings": "\n".join(couchbase_mappings),
                "encryption_method": "SSHA-256",
                "ssl_enabled": "true",
                "couchbaseTrustStoreFn": manager.config.get("couchbaseTrustStoreFn"),
                "encoded_couchbaseTrustStorePass": manager.secret.get("encoded_couchbaseTrustStorePass"),
            }
            fw.write(rendered_txt)


def render_hybrid_properties():
    _couchbase_mappings = get_couchbase_mappings()

    ldap_mapping = GLUU_PERSISTENCE_LDAP_MAPPING

    if GLUU_PERSISTENCE_LDAP_MAPPING == "default":
        default_storage = "ldap"
    else:
        default_storage = "couchbase"

    couchbase_mappings = [
        mapping["alias"] for name, mapping in _couchbase_mappings.iteritems()
        if name != ldap_mapping
    ]

    out = [
        "storages: ldap, couchbase",
        "storage.default: {}".format(default_storage),
        "storage.ldap.mapping: {}".format(ldap_mapping),
        "storage.couchbase.mapping: {}".format(
            ", ".join(filter(None, couchbase_mappings))
        ),
    ]

    with open("/etc/gluu/conf/gluu-hybrid.properties", "w") as fw:
        fw.write("\n".join(out))


def render_gluu_properties():
    with open("/app/templates/gluu.properties.tmpl") as fr:
        txt = fr.read()

        ldap_hostname, ldaps_port = GLUU_LDAP_URL.split(":")

        with open("/etc/gluu/conf/gluu.properties", "w") as fw:
            rendered_txt = txt % {
                "gluuOptPythonFolder": "/opt/gluu/python",
                "certFolder": "/etc/certs",
                "persistence_type": GLUU_PERSISTENCE_TYPE,
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


def sync_couchbase_pkcs12():
    with open(manager.config.get("couchbaseTrustStoreFn"), "wb") as fw:
        encoded_pkcs = manager.secret.get("couchbase_pkcs12_base64")
        pkcs = decrypt_text(encoded_pkcs, manager.secret.get("encoded_salt"))
        fw.write(pkcs)


def saml_couchbase_settings():
    # Add couchbase bean to global.xml
    global_xml_fn = "/opt/shibboleth-idp/conf/global.xml"
    with open(global_xml_fn) as f:
        global_xml = f.read()

    with open("/app/static/couchbase_bean.xml") as f:
        bean_xml = f.read()

    with open(global_xml_fn, "w") as f:
        global_xml = global_xml.replace("</beans>", bean_xml + "\n\n</beans>")
        f.write(global_xml)

    # Add datasource.properties to idp.properties
    idp_properties_fn = "/opt/shibboleth-idp/conf/idp.properties"
    with open(idp_properties_fn) as f:
        idp3_properties = f.readlines()

    for i, l in enumerate(idp3_properties):
        if l.strip().startswith('idp.additionalProperties'):
            idp3_properties[i] = l.strip() + ', /conf/datasource.properties\n'

    with open(idp_properties_fn, "w") as f:
        new_idp3_props = ''.join(idp3_properties)
        f.write(new_idp3_props)


def create_couchbase_shib_user():
    hostname = GLUU_COUCHBASE_URL
    user = manager.config.get("couchbase_server_user")
    password = decrypt_text(
        manager.secret.get("encoded_couchbase_server_pw"),
        manager.secret.get("encoded_salt")
    )
    cbm = CBM(hostname, user, password)

    cbm.create_user(
        'couchbaseShibUser',
        manager.secret.get("couchbase_shib_user_password"),
        'Shibboleth IDP',
        'query_select[*]',
    )


if __name__ == "__main__":
    sync_idp_certs()
    sync_idp_keys()
    sync_idp_jks()
    sync_sealer_jks()

    render_idp3_templates()
    render_salt()
    render_gluu_properties()

    if GLUU_PERSISTENCE_TYPE in ("ldap", "hybrid"):
        render_ldap_properties()
        sync_ldap_cert()
        sync_ldap_pkcs12()

    if GLUU_PERSISTENCE_TYPE in ("couchbase", "hybrid"):
        render_couchbase_properties()
        sync_couchbase_pkcs12()
        create_couchbase_shib_user()

        if "user" in get_couchbase_mappings():
            saml_couchbase_settings()

    if GLUU_PERSISTENCE_TYPE == "hybrid":
        render_hybrid_properties()

    render_ssl_cert()
    render_ssl_key()

    modify_jetty_xml()
    modify_webdefault_xml()
