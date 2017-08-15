import os
import re
import json
import sys
import requests
import subprocess
import hashlib

from redo import retry

from transparencyscript.constants import TRANSPARENCY_VERSION, TRANSPARENCY_SUFFIX, ERROR


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


# Return values from script_config.json - the default set of configurations
def get_config_vars(config_path):
    if os.path.exists(config_path):
        with open(config_path) as config_file:
            config_vars = json.load(config_file)
        return config_vars
    else:
        print("ERROR: Given script_config.json file does not exist.")
        sys.exit(1)


# Return values from passwords.json - contains AWS credentials
def get_password_vars(password_path):
    if os.path.exists(password_path):
        with open(password_path) as password_file:
            password_vars = json.load(password_file)
        return password_vars
    else:
        print("ERROR: passwords.json must exist in current directory.")
        sys.exit(1)


# Return values from task.json if path is given in config.sjon - file created when when scriptworker task begins
def get_task_vars(task_path):
    if os.path.exists(task_path):
        with open(task_path) as task_file:
            task_vars = json.load(task_file)
        return task_vars
    else:
        print("ERROR: task.json must exist in given path.")
        sys.exit(1)


# Return values from both config.json and task.json, where task.json overwrites config.json duplicate values
def get_transparency_vars(config_vars, task_vars):
    transparency_vars = {**config_vars, **task_vars}
    return transparency_vars


# Fetch summary file
def get_summary(summary):
    r = requests.get(summary)
    r.raise_for_status()
    return r.text


# Fetch tree head from summary file - needed to create transparency name
def get_tree_head(config_vars):
    summary = retry(get_summary, args=(config_vars["payload"]["summary"],))
    tree_head = None
    for line in summary.split("\n"):
        tokens = re.split(r'\s+', line)
        if len(tokens) == 2 and tokens[1] == "TREE_HEAD":
            tree_head = tokens[0]
    return tree_head


# Return lego_env required for lego_command
def get_lego_env(password_vars):
    lego_env = {
        "AWS_ACCESS_KEY_ID": password_vars["AWS_KEYS"]["AWS_ACCESS_KEY_ID"],
        "AWS_SECRET_ACCESS_KEY": password_vars["AWS_KEYS"]["AWS_SECRET_ACCESS_KEY"],
        "AWS_REGION": "us-west-2",
    }
    return lego_env


# Return lego_command for first check_call in transparencyscript/script.py
def get_lego_command(config_vars, base_name, trans_name):
    lego_command = " ".join([
        config_vars["lego-path"],
        " --dns route53",
        " --domains {}".format(base_name),
        " --domains {}".format(trans_name),
        " --email {}".format(config_vars["payload"]["contact"]),
        " --path {}/lego".format(config_vars["work_dir"]),
        " --accept-tos",
        "run"
    ])
    return lego_command


# Return save_command for second check_call in transparencyscript/script.py
def get_save_command(config_vars, base_name):
    save_command = " ".join([
        "mv",
        "{}/lego/certificates/{}.crt".format(config_vars["work_dir"], base_name),
        "{}/{}".format(config_vars["public_artifact_dir"], config_vars["payload"]["chain"])
    ])
    return save_command


# Use chain file obtained from Let's Encrypt to create json of certificates
def get_chain(config_vars):
    chain_file = os.path.join(config_vars["public_artifact_dir"], config_vars["payload"]["chain"])

    certdata = []
    with open(chain_file) as f:
        lines = ''.join(f.readlines())
        lines = lines.split("-----BEGIN CERTIFICATE-----\n")
        for line in lines:
            line = line.replace("-----END CERTIFICATE-----", "")
            line = line.replace("\r", "")
            line = line.replace("\n", "")
            certdata.append(line)
        del certdata[0]
    req = '{"chain" : ["' + '", "'.join(certdata) + '"]}'

    return req


# Using certificates json, retrieve SCTs through post requests to CT logs
def post_chain(config_vars, req):
    resp_list = []
    log_list = config_vars["log_list"]

    for log in log_list.keys():
        r = requests.post(log_list[log] + "/ct/v1/add-chain", data=req, verify=False, timeout=2)

        if r.status_code != 200:
            print(r.text)
        else:
            r = json.loads(r.text)
            print("\tSCT Version", r['sct_version'])
            print("\tID", r['id'])
            print("\tTimestamp", r['timestamp'])
            print("\tExtensions", r['extensions'])
            print("\tSignature", r['signature'])

        resp_list.append(r)

    return resp_list


# Write 'contents' to 'file_path' according to 'open_mode' with optional verbose parameter
def write_to_file(file_path, contents, open_mode, verbose=False):
    print("Writing to file %s" % file_path)

    if verbose:
        print("Contents:")
        for line in contents.splitlines():
            print(" %s" % line)

    with open(file_path, open_mode) as f:
        f.write(contents)


# Converts public key from PEM format to DER format, followed by calculating the SHA256 for the SPKI
def get_spki(config_vars):
    chain_file = os.path.join(config_vars["public_artifact_dir"], config_vars["payload"]["chain"])

    public_key = subprocess.Popen(("openssl", "x509", "-in", chain_file, "-pubkey", "-noout"), stdout=subprocess.PIPE)
    der_format = subprocess.check_output(("openssl", "rsa", "-pubin", "-outform", "der"), stdin=public_key.stdout)
    public_key.wait()
    sha256 = hashlib.sha256(der_format).hexdigest()

    return sha256
