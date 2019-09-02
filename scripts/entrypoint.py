import glob
import os
import re

from pygluu.containerlib import get_manager
from pygluu.containerlib.utils import as_boolean
from pygluu.containerlib.utils import decode_text
from pygluu.containerlib.utils import exec_cmd
from pygluu.containerlib.utils import safe_render

from cbm import CBM

GLUU_LDAP_URL = os.environ.get("GLUU_LDAP_URL", "localhost:1636")
GLUU_COUCHBASE_URL = os.environ.get("GLUU_COUCHBASE_URL", "localhost")
GLUU_PERSISTENCE_TYPE = os.environ.get("GLUU_PERSISTENCE_TYPE", "ldap")
GLUU_PERSISTENCE_LDAP_MAPPING = os.environ.get("GLUU_PERSISTENCE_LDAP_MAPPING", "default")


def render_idp3_templates(manager):
    ldap_hostname, ldaps_port = GLUU_LDAP_URL.split(":")
    ctx = {
        "hostname": manager.config.get("hostname"),
        "shibJksPass": manager.secret.get("shibJksPass"),
        "certFolder": "/etc/certs",
        "ldap_hostname": ldap_hostname,
        "ldaps_port": ldaps_port,
        "ldap_binddn": manager.config.get("ldap_binddn"),
        "ldapPass": decode_text(manager.secret.get("encoded_ox_ldap_pw"), manager.secret.get("encoded_salt")),
        "idp3SigningCertificateText": load_cert_text("/etc/certs/idp-signing.crt"),
        "idp3EncryptionCertificateText": load_cert_text("/etc/certs/idp-encryption.crt"),
        "orgName": manager.config.get("orgName"),
        "ldapCertFn": "/etc/certs/opendj.crt",
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


def load_cert_text(path):
    with open(path) as f:
        cert = f.read()
        return cert.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').strip()


def render_salt(manager):
    encode_salt = manager.secret.get("encoded_salt")

    with open("/app/templates/salt.tmpl") as fr:
        txt = fr.read()
        with open("/etc/gluu/conf/salt", "w") as fw:
            rendered_txt = txt % {"encode_salt": encode_salt}
            fw.write(rendered_txt)


def render_ldap_properties(manager):
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
            "mapping": "",
        },
        "user": {
            "bucket": "gluu_user",
            "mapping": "people, groups, authorizations",
        },
        "cache": {
            "bucket": "gluu_cache",
            "mapping": "cache",
        },
        "site": {
            "bucket": "gluu_site",
            "mapping": "cache-refresh",
        },
        "token": {
            "bucket": "gluu_token",
            "mapping": "tokens",
        },
    }

    if GLUU_PERSISTENCE_TYPE == "hybrid":
        mappings = {
            name: mapping for name, mapping in mappings.iteritems()
            if name != GLUU_PERSISTENCE_LDAP_MAPPING
        }

    return mappings


def render_couchbase_properties(manager):
    _couchbase_mappings = get_couchbase_mappings()
    couchbase_buckets = []
    couchbase_mappings = []

    for _, mapping in _couchbase_mappings.iteritems():
        couchbase_buckets.append(mapping["bucket"])

        if not mapping["mapping"]:
            continue

        couchbase_mappings.append("bucket.{0}.mapping: {1}".format(
            mapping["bucket"], mapping["mapping"],
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
        mapping["mapping"] for name, mapping in _couchbase_mappings.iteritems()
        if name != ldap_mapping
    ]

    out = "\n".join([
        "storages: ldap, couchbase",
        "storage.default: {}".format(default_storage),
        "storage.ldap.mapping: {}".format(ldap_mapping),
        "storage.couchbase.mapping: {}".format(
            ", ".join(filter(None, couchbase_mappings))
        ),
    ]).replace("user", "people, groups")

    with open("/etc/gluu/conf/gluu-hybrid.properties", "w") as fw:
        fw.write(out)


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


def generate_idp3_sealer(manager):
    cmd = " ".join([
        "java",
        "-classpath '/opt/gluu/jetty/idp/webapps/idp/WEB-INF/lib/*'",
        "net.shibboleth.utilities.java.support.security.BasicKeystoreKeyStrategyTool",
        "--storefile /opt/shibboleth-idp/credentials/sealer.jks",
        "--versionfile /opt/shibboleth-idp/credentials/sealer.kver",
        "--alias secret",
        "--storepass {}".format(manager.secret.get("shibJksPass")),
    ])
    return exec_cmd(cmd)


def sync_sealer(manager):
    jks_fn = "/opt/shibboleth-idp/credentials/sealer.jks"
    kver_fn = "/opt/shibboleth-idp/credentials/sealer.kver"

    if not as_boolean(manager.config.get("sealer_generated", False)):
        # create sealer.jks and sealer.kver
        generate_idp3_sealer(manager)
        manager.secret.from_file("sealer_jks_base64", jks_fn, encode=True, binary_mode=True)
        manager.secret.from_file("sealer_kver_base64", kver_fn, encode=True, binary_mode=True)
        manager.config.set("sealer_generated", True)
        return

    manager.secret.to_file("sealer_jks_base64", jks_fn, decode=True, binary_mode=True)
    manager.secret.to_file("sealer_kver_base64", kver_fn, decode=True, binary_mode=True)


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


def create_couchbase_shib_user(manager):
    hostname = GLUU_COUCHBASE_URL
    user = manager.config.get("couchbase_server_user")
    password = decode_text(
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


def main():
    manager = get_manager()

    manager.secret.to_file("idp3SigningCertificateText", "/etc/certs/idp-signing.crt")
    manager.secret.to_file("idp3EncryptionCertificateText", "/etc/certs/idp-encryption.crt")
    manager.secret.to_file("idp3SigningKeyText", "/etc/certs/idp-signing.key")
    manager.secret.to_file("idp3EncryptionKeyText", "/etc/certs/idp-encryption.key")
    manager.secret.to_file("shibIDP_jks_base64", "/etc/certs/shibIDP.jks",
                           decode=True, binary_mode=True)
    sync_sealer(manager)

    render_idp3_templates(manager)
    render_salt(manager)
    render_gluu_properties()

    if GLUU_PERSISTENCE_TYPE in ("ldap", "hybrid"):
        render_ldap_properties(manager)

        manager.secret.to_file("ldap_ssl_cert", "/etc/certs/opendj.crt", decode=True)
        manager.secret.to_file(
            "ldap_pkcs12_base64",
            manager.config.get("ldapTrustStoreFn"),
            decode=True,
            binary_mode=True
        )

    if GLUU_PERSISTENCE_TYPE in ("couchbase", "hybrid"):
        render_couchbase_properties(manager)
        manager.secret.to_file("couchbase_chain_cert", "/etc/certs/couchbase.pem")
        manager.secret.to_file(
            "couchbase_pkcs12_base64",
            manager.config.get("couchbaseTrustStoreFn"),
            decode=True,
            binary_mode=True,
        )
        create_couchbase_shib_user(manager)

        if "user" in get_couchbase_mappings():
            saml_couchbase_settings()

    if GLUU_PERSISTENCE_TYPE == "hybrid":
        render_hybrid_properties()

    manager.secret.to_file("ssl_cert", "/etc/certs/gluu_https.crt")
    manager.secret.to_file("ssl_key", "/etc/certs/gluu_https.key")

    modify_jetty_xml()
    modify_webdefault_xml()


if __name__ == "__main__":
    main()
