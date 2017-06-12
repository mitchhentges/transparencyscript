import os
import re
import json
import requests

from constants import TRANSPARENCY_VERSION, TRANSPARENCY_SUFFIX


# Create transparency name for required lego_command parameter
def make_transparency_name(tree_head_hex, version, product):
    version = re.sub("\.", "-", version)

    name = "{}.{}.{}.{}".format(version, product, TRANSPARENCY_VERSION, TRANSPARENCY_SUFFIX)

    while len(tree_head_hex) > 32:
        label = tree_head_hex[-32:]
        tree_head_hex = tree_head_hex[:-32]
        name = "{}.{}".format(label, name)

    if len(tree_head_hex) > 0:
        name = "{}.{}".format(tree_head_hex, name)

    return name


# Return config values from config.json
def get_config_vars():
    here = os.path.dirname(os.path.abspath(__file__))
    config_json = os.path.join(here, '../config.json')

    with open(config_json) as config_file:
        config_vars = json.load(config_file)

    return config_vars


# Fetch summary file
def get_summary():
    config_vars = get_config_vars()
    r = requests.get(config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--summary"])
    r.raise_for_status()
    return r.text
