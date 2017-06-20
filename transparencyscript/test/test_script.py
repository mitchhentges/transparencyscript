import re

from redo import retry

from transparencyscript.constants import TRANSPARENCY_SUFFIX
from transparencyscript.test import get_fake_config
from transparencyscript.utils import get_summary, make_transparency_name

correct_lego_env = {'AWS_ACCESS_KEY_ID': '*****', 'AWS_SECRET_ACCESS_KEY': '*****', 'AWS_REGION': 'us-west-2'}
correct_lego_command = "/Users/btang/go/bin/lego  --dns route53  --domains invalid.stage.fx-trans.net  --domains " \
                       "eae00f676fc07354cd509994f9946956.462805e6950aacba4c1bc9028880efc2.53-0b5.firefox.0." \
                       "stage.fx-trans.net  --email btang@mozilla.com  --accept-tos run"
correct_save_command = "mv ./.lego/certificates/invalid.stage.fx-trans.net.crt TRANSPARENCY.pem"
correct_cleanup_command = "rm -rf ./.lego"

config_vars = get_fake_config()

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


def test_lego_env():
    lego_env = {
        "AWS_ACCESS_KEY_ID": config_vars["AWS_KEYS"]["AWS_ACCESS_KEY_ID"],
        "AWS_SECRET_ACCESS_KEY": config_vars["AWS_KEYS"]["AWS_SECRET_ACCESS_KEY"],
        "AWS_REGION": "us-west-2",
    }

    assert lego_env == correct_lego_env


def test_lego_command():
    lego_command = " ".join([
        config_vars["lego-path"],
        " --dns route53",
        " --domains {}".format(base_name),
        " --domains {}".format(trans_name),
        " --email {}".format(config_vars["payload"]["contact"]),
        " --accept-tos",
        "run"
    ])

    assert lego_command == correct_lego_command


def test_save_command():
    save_command = " ".join([
        "mv",
        "./.lego/certificates/{}.crt".format(base_name),
        config_vars["payload"]["chain"]
    ])

    assert save_command == correct_save_command
