import random


def get_random_race_configs_id():
    race_configs_ids = [
        "resources/race-configs-group-1.json",
        "resources/race-configs-group-2.json",
        "/foo/bar/some_adhoc_conffile.json",
    ]
    return random.choice(race_configs_ids)
