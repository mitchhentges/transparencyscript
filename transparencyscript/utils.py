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


# Return values from config.json
def get_config_vars(config_path):
    if os.path.exists(config_path):
        with open(config_path) as config_file:
            config_vars = json.load(config_file)
        return config_vars
    else:
        print("ERROR: config.json must exist in current directory.")
        sys.exit(1)


# Return values from task.json
def get_task_vars(task_path):
    with open(task_path) as task_file:
        task_vars = json.load(task_file)
    return task_vars


# Return values from both config.json and task.json, where task.json overwrites config.json duplicate values
def get_transparency_vars(config_vars, task_vars):
    transparency_vars = {**config_vars, **task_vars}
    return transparency_vars


# Fetch summary file
def get_summary(summary):
    r = requests.get(summary)
    r.raise_for_status()
    return r.text
