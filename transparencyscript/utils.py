import os
import re
import json
import sys
import requests

from transparencyscript.constants import TRANSPARENCY_VERSION, TRANSPARENCY_SUFFIX


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


# Return config values from config.json and task.json
def get_config_vars():

    config_json = os.path.join(os.getcwd(), 'config.json')
    if os.path.exists(config_json):
        with open(config_json) as config_file:
            config_vars = json.load(config_file)
    else:
        print("ERROR: config.json must exist in current directory.")
        sys.exit(1)

    if len(sys.argv) > 1:
        task_json = sys.argv[1]
        with open(task_json) as task_file:
            task_vars = json.load(task_file)

        transparency_vars = {**config_vars, **task_vars}

        return transparency_vars

    return config_vars


# Fetch summary file
def get_summary(summary):
    r = requests.get(summary)
    r.raise_for_status()
    return r.text
