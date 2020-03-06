import glob
import os
import re

from pygluu.containerlib import get_manager
from pygluu.containerlib.persistence import render_hybrid_properties
from pygluu.containerlib.persistence import render_couchbase_properties
from pygluu.containerlib.persistence import sync_couchbase_cert
from pygluu.containerlib.persistence import sync_couchbase_truststore
from pygluu.containerlib.persistence import render_salt
from pygluu.containerlib.persistence import render_gluu_properties
from pygluu.containerlib.persistence import render_ldap_properties
from pygluu.containerlib.persistence import sync_ldap_truststore
from pygluu.containerlib.persistence.couchbase import get_couchbase_mappings
from pygluu.containerlib.persistence.couchbase import get_couchbase_user
from pygluu.containerlib.persistence.couchbase import get_couchbase_password
from pygluu.containerlib.persistence.couchbase import CouchbaseClient
from pygluu.containerlib.utils import as_boolean
from pygluu.containerlib.utils import decode_text
from pygluu.containerlib.utils import exec_cmd
from pygluu.containerlib.utils import safe_render
from pygluu.containerlib.utils import cert_to_truststore
from pygluu.containerlib.utils import get_server_certificate

GLUU_LDAP_URL = os.environ.get("GLUU_LDAP_URL", "localhost:1636")
GLUU_COUCHBASE_URL = os.environ.get("GLUU_COUCHBASE_URL", "localhost")


def render_idp3_templates(manager):
    ldap_hostname, ldaps_port = GLUU_LDAP_URL.split(":")

    persistence_type = os.environ.get("GLUU_PERSISTENCE_TYPE", "ldap")
    ldap_mapping = os.environ.get("GLUU_PERSISTENCE_LDAP_MAPPING", "default")

    idp_resolver_filter = "(|(uid=$requestContext.principalName)(mail=$requestContext.principalName))"

    if all([persistence_type in ("couchbase", "hybrid"),
            "user" in get_couchbase_mappings(persistence_type, ldap_mapping)]):
        idp_resolver_filter = "(&(|(lower(uid)=$requestContext.principalName)(mail=$requestContext.principalName))(objectClass=gluuPerson))"

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
        "idp_attribute_resolver_ldap.search_filter": idp_resolver_filter,
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
    user = get_couchbase_user(manager)
    password = get_couchbase_password(manager)

    cb_client = CouchbaseClient(hostname, user, password)
    cb_client.create_user(
        'couchbaseShibUser',
        manager.secret.get("couchbase_shib_user_password"),
        'Shibboleth IDP',
        'query_select[*]',
    )


def main():
    persistence_type = os.environ.get("GLUU_PERSISTENCE_TYPE", "ldap")
    ldap_mapping = os.environ.get("GLUU_PERSISTENCE_LDAP_MAPPING", "default")
    manager = get_manager()

    manager.secret.to_file("idp3SigningCertificateText", "/etc/certs/idp-signing.crt")
    manager.secret.to_file("idp3EncryptionCertificateText", "/etc/certs/idp-encryption.crt")
    manager.secret.to_file("idp3SigningKeyText", "/etc/certs/idp-signing.key")
    manager.secret.to_file("idp3EncryptionKeyText", "/etc/certs/idp-encryption.key")
    manager.secret.to_file("shibIDP_jks_base64", "/etc/certs/shibIDP.jks",
                           decode=True, binary_mode=True)
    sync_sealer(manager)

    render_idp3_templates(manager)
    render_salt(manager, "/app/templates/salt.tmpl", "/etc/gluu/conf/salt")
    render_gluu_properties("/app/templates/gluu.properties.tmpl", "/etc/gluu/conf/gluu.properties")

    if persistence_type in ("ldap", "hybrid"):
        render_ldap_properties(
            manager,
            "/app/templates/gluu-ldap.properties.tmpl",
            "/etc/gluu/conf/gluu-ldap.properties",
        )

        manager.secret.to_file("ldap_ssl_cert", "/etc/certs/opendj.crt", decode=True)
        sync_ldap_truststore(manager)

    if persistence_type in ("couchbase", "hybrid"):
        render_couchbase_properties(
            manager,
            "/app/templates/gluu-couchbase.properties.tmpl",
            "/etc/gluu/conf/gluu-couchbase.properties",
        )
        sync_couchbase_cert(manager)
        sync_couchbase_truststore(manager)
        create_couchbase_shib_user(manager)

        if "user" in get_couchbase_mappings(persistence_type, ldap_mapping):
            saml_couchbase_settings()

    if persistence_type == "hybrid":
        render_hybrid_properties("/etc/gluu/conf/gluu-hybrid.properties")

    get_server_certificate(manager.config.get("hostname"), 443, "/etc/certs/gluu_https.crt")
    cert_to_truststore(
        "gluu_https",
        "/etc/certs/gluu_https.crt",
        "/usr/lib/jvm/default-jvm/jre/lib/security/cacerts",
        "changeit",
    )

    modify_jetty_xml()
    modify_webdefault_xml()


if __name__ == "__main__":
    main()
