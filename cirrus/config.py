import os
import os.path
import yaml


def load_config(fpath=None):
    global settings

    if fpath is None:
        fpath = os.path.join(os.environ["HOME"], ".config", "cirrus.yaml")

    f = open(fpath, "r")
    return yaml.load(f)


settings = load_config()
