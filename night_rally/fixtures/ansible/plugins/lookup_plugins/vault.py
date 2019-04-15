import os
import urllib2
import json
import ssl
from distutils.version import StrictVersion
from sys import version_info
from urlparse import urljoin

from ansible.errors import AnsibleError
import ansible.utils

try:
    from ansible.plugins.lookup import LookupBase
except ImportError:
    # ansible-1.9.x
    class LookupBase(object):
        def __init__(self, basedir=None, runner=None, **kwargs):
            self.runner = runner
            self.basedir = basedir or (self.runner.basedir if self.runner else None)

        def get_basedir(self, variables):
            return self.basedir


urllib3_available = True
try:
    import urllib3
except ImportError:
    urllib3_available = False

try:
    import certifi
except ImportError:
    # certifi not available, fall back to urllib2
    urllib3_available = False


class SmartRedirectHandler(urllib2.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):
        result = urllib2.HTTPRedirectHandler.http_error_301(
            self, req, fp, code, msg, headers
        )
        result.status = code
        return result

    def http_error_302(self, req, fp, code, msg, headers):
        result = urllib2.HTTPRedirectHandler.http_error_302(
            self, req, fp, code, msg, headers
        )
        result.status = code
        return result


class LookupModule(LookupBase):
    def run(self, terms, inject=None, variables=None, **kwargs):
        basedir = self.get_basedir(variables)

        if hasattr(ansible.utils, "listify_lookup_plugin_terms"):
            # ansible-1.9.x
            terms = ansible.utils.listify_lookup_plugin_terms(terms, basedir, inject)

        term_split = terms[0].split(" ", 1)
        key = term_split[0]
        if not key:
            raise AnsibleError("Key must be non-empty")

        try:
            parameters = term_split[1]

            parameters = parameters.split(" ")

            parameter_bag = {}
            for parameter in parameters:
                parameter_split = parameter.split("=")

                parameter_key = parameter_split[0]
                parameter_value = parameter_split[1]
                parameter_bag[parameter_key] = parameter_value

            data = json.dumps(parameter_bag)
        except:
            data = None

        try:
            field = terms[1]
        except:
            field = None

        # the environment variable takes precendence over the Ansible variable.
        # Ansible variables are passed via "variables" in ansible 2.x, "inject" in 1.9.x
        url = os.getenv("VAULT_ADDR") or (variables or inject).get("vault_addr")
        if not url:
            raise AnsibleError(
                "Vault address not set. Specify with"
                " VAULT_ADDR environment variable or vault_addr Ansible variable"
            )

        # the environment variable takes precedence over the file-based token.
        # intentionally do *not* support setting this via an Ansible variable,
        # so as not to encourage bad security practices.
        token = os.getenv("VAULT_TOKEN")
        if not token:
            try:
                with open(os.path.join(os.getenv("HOME"), ".vault-token")) as file:
                    token = file.read()
            except IOError:
                # token not found in file is same case below as not found in env var
                pass
        if not token:
            raise AnsibleError(
                "Vault authentication token missing. Specify with"
                " VAULT_TOKEN environment variable or $HOME/.vault-token"
            )

        cafile = os.getenv("VAULT_CACERT") or (variables or inject).get("vault_cacert")
        capath = os.getenv("VAULT_CAPATH") or (variables or inject).get("vault_capath")
        try:
            context = None
            if cafile or capath:
                context = ssl.create_default_context(cafile=cafile, capath=capath)
            request_url = urljoin(url, "v1/%s" % (key))

            if urllib3_available is True:
                http = urllib3.PoolManager(
                    cert_reqs="CERT_REQUIRED", ca_certs=certifi.where()
                )
                response = http.request(
                    "GET",
                    request_url,
                    headers={
                        "X-Vault-Token": token,
                        "Content-Type": "application/json",
                    },
                )
                result = json.loads(response.data.decode("utf-8"))
            else:
                req = urllib2.Request(request_url, data)
                req.add_header("X-Vault-Token", token)
                req.add_header("Content-Type", "application/json")
                opener = urllib2.build_opener(SmartRedirectHandler())
                response = (
                    opener.open(req, context=context) if context else opener.open(req)
                )
                result = json.loads(response.read())
        except AttributeError as e:
            python_version_cur = ".".join(
                [
                    str(version_info.major),
                    str(version_info.minor),
                    str(version_info.micro),
                ]
            )
            python_version_min = "2.7.9"
            if StrictVersion(python_version_cur) < StrictVersion(python_version_min):
                raise AnsibleError(
                    "Unable to read %s from vault:"
                    " Using Python %s, and vault lookup plugin requires at least %s"
                    " to use an SSL context (VAULT_CACERT or VAULT_CAPATH)"
                    % (key, python_version_cur, python_version_min)
                )
            else:
                raise AnsibleError("Unable to read %s from vault: %s" % (key, e))
        except urllib2.HTTPError as e:
            raise AnsibleError("Unable to read %s from vault: %s" % (key, e))
        except Exception as e:
            raise AnsibleError("Unable to read %s from vault: %s" % (key, e))

        return [result["data"][field]] if field is not None else [result["data"]]
