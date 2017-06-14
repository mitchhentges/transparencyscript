import re

from subprocess import check_call
from redo import retry

from constants import TRANSPARENCY_SUFFIX
from utils import make_transparency_name, get_config_vars, get_summary


def issue_cert():
    # Store default parameters and keys in config_vars
    config_vars = get_config_vars()

    # Parse tree head from summary file
    summary = retry(get_summary, args=(config_vars["payload"]["summary"],))
    tree_head = None
    for line in summary.split("\n"):
        tokens = re.split(r'\s+', line)
        if len(tokens) == 2 and tokens[1] == "TREE_HEAD":
            tree_head = tokens[0]

    if tree_head is None:
        raise Exception("No tree head found in summary file")

    base_name = "{}.{}".format("invalid", TRANSPARENCY_SUFFIX)
    trans_name = make_transparency_name(tree_head, config_vars["payload"]["version"],
                                        config_vars["payload"]["stage-product"])

    # Issue and save the certificate, then delete the extra files lego created
    lego_env = {
        "AWS_ACCESS_KEY_ID": config_vars["AWS_KEYS"]["AWS_ACCESS_KEY_ID"],
        "AWS_SECRET_ACCESS_KEY": config_vars["AWS_KEYS"]["AWS_SECRET_ACCESS_KEY"],
        "AWS_REGION": "us-west-2",
    }
    lego_command = " ".join([
        config_vars["payload"]["lego-path"],
        " --dns route53",
        " --domains {}".format(base_name),
        " --domains {}".format(trans_name),
        " --email {}".format(config_vars["payload"]["contact"]),
        " --accept-tos",
        "run"
    ])

    save_command = " ".join([
        "mv",
        "./.lego/certificates/{}.crt".format(base_name),
        config_vars["payload"]["chain"]
    ])

    cleanup_command = "rm -rf ./.lego"

    check_call(lego_command, env=lego_env, shell=True)
    check_call(save_command, shell=True)
    check_call(cleanup_command, shell=True)


if __name__ == "__main__":
    issue_cert()
