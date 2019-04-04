def create_client(configuration_name=None):
    import configparser
    import elasticsearch
    import certifi
    import pathlib

    def load():
        config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        if configuration_name:
            # invoked from night-rally
            _rally_ini_path = str(pathlib.Path.home()/".rally"/"rally-{}.ini".format(configuration_name))
        else:
            # invoked from e.g. night-rally-admin, ini files not deployed via Ansible
            _rally_ini_path = str(pathlib.PurePath(__file__).parent/"fixtures/ansible/roles/rally-update/templates/rally.ini.j2")
        config.read(_rally_ini_path)
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
