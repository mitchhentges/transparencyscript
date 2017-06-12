import os
import json
import re

TRANSPARENCY_VERSION = "0"
TRANSPARENCY_SUFFIX = "stage.fx-trans.net"


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


def issue_cert():
    import requests
    from subprocess import check_call
    from redo import retry

    # Store parameter values from config.json in config_vars
    here = os.path.dirname(os.path.abspath(__file__))
    config_json = os.path.join(here, '../config.json')

    with open(config_json) as config_file:
        config_vars = json.load(config_file)

    # Fetch summary file and parse out tree head
    def get_summary():
        r = requests.get(config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--summary"])
        r.raise_for_status()
        return r.text

    summary = retry(get_summary)
    tree_head = None
    for line in summary.split("\n"):
        tokens = re.split(r'\s+', line)
        if len(tokens) == 2 and tokens[1] == "TREE_HEAD":
            tree_head = tokens[0]

    if tree_head is None:
        raise Exception("No tree head found in summary file")

    base_name = "{}.{}".format("invalid", TRANSPARENCY_SUFFIX)
    trans_name = make_transparency_name(tree_head, config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--version"],
                                        config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--stage-product"])

    # Issue and save the certificate, then delete the extra files lego created
    lego_env = {
        "AWS_ACCESS_KEY_ID": config_vars["AWS_KEYS"]["AWS_ACCESS_KEY_ID"],
        "AWS_SECRET_ACCESS_KEY": config_vars["AWS_KEYS"]["AWS_SECRET_ACCESS_KEY"],
        "AWS_REGION": "us-west-2",
    }
    lego_command = " ".join([
        "/Users/btang/go/bin/lego",
        " --dns route53",
        " --domains {}".format(base_name),
        " --domains {}".format(trans_name),
        " --email {}".format(config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--contact"]),
        " --accept-tos",
        "run"
    ])

    save_command = " ".join([
        "mv",
        "./.lego/certificates/{}.crt".format(base_name),
        config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--chain"]
    ])

    cleanup_command = "rm -rf ./.lego"

    check_call(lego_command, env=lego_env, shell=True)
    check_call(save_command, shell=True)
    check_call(cleanup_command, shell=True)


if __name__ == "__main__":
    issue_cert()
