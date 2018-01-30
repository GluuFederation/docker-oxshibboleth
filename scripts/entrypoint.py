import glob
import os
import re
import shlex
import subprocess

import consulate

GLUU_LDAP_URL = os.environ.get("GLUU_LDAP_URL", "localhost:1636")
GLUU_KV_HOST = os.environ.get("GLUU_KV_HOST", "localhost")
GLUU_KV_PORT = os.environ.get("GLUU_KV_PORT", 8500)

consul = consulate.Consul(host=GLUU_KV_HOST, port=GLUU_KV_PORT)


def safe_render(text, ctx):
    text = re.sub(r"%([^\(])", r"%%\1", text)
    # There was a % at the end?
    text = re.sub(r"%$", r"%%", text)
    return text % ctx


def render_templates():
    ldap_hostname, ldaps_port = GLUU_LDAP_URL.split(":")
    ctx = {
        "hostname": consul.kv.get("hostname"),
        "shibJksPass": consul.kv.get("shibJksPass"),
        "certFolder": "/etc/certs",
        "ldap_hostname": ldap_hostname,
        "ldaps_port": ldaps_port,
        "ldap_protocol": "ldaps" if consul.kv.get("use_ssl") else "ldap",
        "ldap_use_ssl": consul.kv.get("ldap_use_ssl"),
        "ldap_binddn": consul.kv.get("ldap_binddn"),
        "ldapPass": consul.kv.get("encoded_ldap_pw"),
        "inumOrg": consul.kv.get("inumOrg"),
        "idp3SigningCertificateText": load_cert_text("/etc/certs/idp-signing.crt", "idp3SigningCertificateText"),
        "idp3EncryptionCertificateText": load_cert_text("/etc/certs/idp-encryption.crt", "idp3EncryptionCertificateText"),
        "orgName": consul.kv.get("orgName"),
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
    shibJksPass = consul.kv.get("shibJksPass")
    out, err, retcode = exec_cmd("java -classpath /tmp/idp3_cml_keygenerator.jar "
                                 "'org.xdi.oxshibboleth.keygenerator.KeyGenerator' "
                                 "/opt/shibboleth-idp/credentials {}".format(shibJksPass))
    return out, err, retcode


def load_cert_text(path, key):
    cert = consul.kv.get(key)
    with open(path, "w") as fw:
        fw.write(cert)
    return cert.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').strip()


if __name__ == "__main__":
    render_templates()
    gen_idp3_key()
