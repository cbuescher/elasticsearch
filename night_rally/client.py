def create_client(configuration_name):
    import configparser
    import elasticsearch
    import certifi
    import pathlib

    def host_string(host):
        # protocol can be set at either host or client opts level
        protocol = "https" if host.get("use_ssl") else "http"
        return f"{protocol}://{host['host']}:{host['port']}"

    def load():
        config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        config_file = pathlib.Path.home()/".rally"/"rally-{}.ini".format(configuration_name)
        if not config_file.exists():
            raise IOError("Config file [{}] is missing".format(config_file))
        config.read(str(config_file))
        return config

    complete_cfg = load()
    cfg = complete_cfg["reporting"]
    if cfg["datastore.secure"].lower() == "true":
        secure = True
    elif cfg["datastore.secure"].lower() == "false":
        secure = False
    else:
        raise ValueError("Setting [datastore.secure] is neither [True] nor [False] but [%s]" % cfg["datastore.secure"])
    hosts = [
        {
            "host": cfg["datastore.host"],
            "port": cfg["datastore.port"],
            "use_ssl": secure
        }
    ]
    basic_auth = (cfg["datastore.user"], cfg["datastore.password"]) if secure else None
    hosts = [host_string(h) for h in hosts]
    certs = certifi.where() if secure else None

    return elasticsearch.Elasticsearch(hosts=hosts, basic_auth=basic_auth, ca_certs=certs, timeout=60)


def normalize_hosts(hosts):
    # pylint: disable=import-outside-toplevel
    from urllib.parse import unquote, urlparse

    string_types = str, bytes
    # if hosts are empty, just defer to defaults down the line
    if hosts is None:
        return [{}]

    # passed in just one string
    if isinstance(hosts, string_types):
        hosts = [hosts]

    out = []
    # normalize hosts to dicts
    for host in hosts:
        if isinstance(host, string_types):
            if "://" not in host:
                host = "//%s" % host

            parsed_url = urlparse(host)
            h = {"host": parsed_url.hostname}

            if parsed_url.port:
                h["port"] = parsed_url.port

            if parsed_url.scheme == "https":
                h["port"] = parsed_url.port or 443
                h["use_ssl"] = True

            if parsed_url.username or parsed_url.password:
                h["http_auth"] = "%s:%s" % (
                    unquote(parsed_url.username),
                    unquote(parsed_url.password),
                )

            if parsed_url.path and parsed_url.path != "/":
                h["url_prefix"] = parsed_url.path

            out.append(h)
        else:
            out.append(host)
    return out
