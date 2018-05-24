def create_client():
    import configparser
    import os
    import elasticsearch
    import certifi

    def load():
        config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        config.read("%s/fixtures/ansible/roles/rally-update/templates/rally.ini.j2" % os.path.dirname(os.path.realpath(__file__)))
        return config

    complete_cfg = load()
    cfg = complete_cfg["reporting"]
    if cfg["datastore.secure"] == "True":
        secure = True
    elif cfg["datastore.secure"] == "False":
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

    return elasticsearch.Elasticsearch(hosts=hosts, http_auth=http_auth, ca_certs=certs)
