import os
import sys
import json


def get_fake_config():
    config_json = os.path.join(os.getcwd(), 'transparencyscript/test/fake_config.json')
    if os.path.exists(config_json):
        with open(config_json) as config_file:
            config_vars = json.load(config_file)
            return config_vars
    else:
        print("ERROR: fake_config.json must exist in current directory.")
        sys.exit(1)


def get_fake_task():
    task_json = os.path.join(os.getcwd(), 'transparencyscript/test/fake_task.json')
    if os.path.exists(task_json):
        with open(task_json) as task_file:
            task_vars = json.load(task_file)
            return task_vars
    else:
        print("ERROR: fake_task.json must exist in current directory.")
        sys.exit(1)


def get_fake_transparency():
    transparency_json = os.path.join(os.getcwd(), 'transparencyscript/test/fake_transparency.json')
    if os.path.exists(transparency_json):
        with open(transparency_json) as transparency_file:
            transparency_vars = json.load(transparency_file)
            return transparency_vars
    else:
        print("ERROR: fake_transparency.json must exist in current directory.")
        sys.exit(1)
