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


# Return lego_env required for lego_command
def get_lego_env(config_vars):
    lego_env = {
        "AWS_ACCESS_KEY_ID": config_vars["AWS_KEYS"]["AWS_ACCESS_KEY_ID"],
        "AWS_SECRET_ACCESS_KEY": config_vars["AWS_KEYS"]["AWS_SECRET_ACCESS_KEY"],
        "AWS_REGION": "us-west-2",
    }
    return lego_env


# Return lego_command for first check_call in script.py
def get_lego_command(config_vars, base_name, trans_name):
    lego_command = " ".join([
        config_vars["lego-path"],
        " --dns route53",
        " --domains {}".format(base_name),
        " --domains {}".format(trans_name),
        " --email {}".format(config_vars["payload"]["contact"]),
        " --accept-tos",
        "run"
    ])
    return lego_command


# Return save_command for second check_call in script.py
def get_save_command(config_vars, base_name):
    save_command = " ".join([
        "mv",
        "./.lego/certificates/{}.crt".format(base_name),
        config_vars["payload"]["chain"]
    ])
    return save_command
