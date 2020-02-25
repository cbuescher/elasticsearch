def create_client(configuration_name):
    import configparser
    import elasticsearch
    import certifi
    import pathlib

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
    http_auth = (cfg["datastore.user"], cfg["datastore.password"]) if secure else None
    certs = certifi.where() if secure else None

    return elasticsearch.Elasticsearch(hosts=hosts, http_auth=http_auth, ca_certs=certs, timeout=60)
