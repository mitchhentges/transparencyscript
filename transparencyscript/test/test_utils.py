import os
import requests
import requests_mock

from transparencyscript.utils import make_transparency_name, get_config_vars, get_task_vars, get_transparency_vars, \
    get_summary, set_aws_creds
from transparencyscript.test import get_fake_config, get_fake_task, get_fake_transparency, get_fake_config_no_aws
from transparencyscript.constants import SUMMARY_TEXT, TRANSPARENCY_SUFFIX


def test_make_transparency_name():
    correct_name = "eae00f676fc07354cd509994f9946956.462805e6950aacba4c1bc9028880efc2.53-0b5.firefox.0.stage.fx-trans.net"

    tree_head_hex = "eae00f676fc07354cd509994f9946956462805e6950aacba4c1bc9028880efc2"
    version = "53.0b5"
    product = "firefox"

    assert make_transparency_name(tree_head_hex, version, product) == correct_name


def test_get_config_vars():
    fake_config_vars = get_fake_config()

    config_path = os.path.join(os.getcwd(), 'transparencyscript/test/fake_config.json')
    config_vars = get_config_vars(config_path)

    assert config_vars == fake_config_vars


def test_get_task_vars():
    fake_task_vars = get_fake_task()

    task_path = os.path.join(os.getcwd(), 'transparencyscript/test/fake_task.json')
    task_vars = get_task_vars(task_path)

    assert task_vars == fake_task_vars


def test_get_transparency_vars():
    fake_transparency_vars = get_fake_transparency()
    fake_config_vars = get_fake_config_no_aws()
    fake_task_vars = get_fake_task()

    transparency_vars = get_transparency_vars(fake_config_vars, fake_task_vars)

    assert transparency_vars == fake_transparency_vars


def test_get_summary():
    with requests_mock.Mocker() as m:
        m.get("https://ipv.sx/tmp/SHA256SUMMARY",
              text=SUMMARY_TEXT)
        summary = requests.get("https://ipv.sx/tmp/SHA256SUMMARY").text

    assert get_summary("https://ipv.sx/tmp/SHA256SUMMARY")[0:447] == summary


def test_lego_env():
    correct_lego_env = {'AWS_ACCESS_KEY_ID': '*****', 'AWS_SECRET_ACCESS_KEY': '*****', 'AWS_REGION': 'us-west-2'}

    config_vars = get_fake_config()

    lego_env = {
        "AWS_ACCESS_KEY_ID": config_vars["AWS_KEYS"]["AWS_ACCESS_KEY_ID"],
        "AWS_SECRET_ACCESS_KEY": config_vars["AWS_KEYS"]["AWS_SECRET_ACCESS_KEY"],
        "AWS_REGION": "us-west-2",
    }

    assert lego_env == correct_lego_env


def test_lego_command():
    correct_lego_command = "/Users/btang/go/bin/lego  --dns route53  --domains invalid.stage.fx-trans.net  --domains " \
                           "eae00f676fc07354cd509994f9946956.462805e6950aacba4c1bc9028880efc2.53-0b5.firefox.0." \
                           "stage.fx-trans.net  --email btang@mozilla.com  --accept-tos run"

    config_vars = get_fake_config()
    base_name = "{}.{}".format("invalid", TRANSPARENCY_SUFFIX)
    trans_name = "eae00f676fc07354cd509994f9946956.462805e6950aacba4c1bc9028880efc2.53-0b5.firefox.0.stage.fx-trans.net"

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
    correct_save_command = "mv ./.lego/certificates/invalid.stage.fx-trans.net.crt TRANSPARENCY.pem"

    config_vars = get_fake_config()
    base_name = "{}.{}".format("invalid", TRANSPARENCY_SUFFIX)

    save_command = " ".join([
        "mv",
        "./.lego/certificates/{}.crt".format(base_name),
        config_vars["payload"]["chain"]
    ])

    assert save_command == correct_save_command


def test_set_aws_creds_config_vars():
    fake_config_vars_no_aws = get_fake_config_no_aws()

    fake_config_vars = get_fake_config()
    set_aws_creds(fake_config_vars)

    assert fake_config_vars_no_aws == fake_config_vars


def test_set_aws_creds_access_key_id():
    access_key_id = "*****"

    fake_config_vars = get_fake_config()
    set_aws_creds(fake_config_vars)

    assert os.environ.get("AWS_ACCESS_KEY_ID") == access_key_id


def test_set_aws_creds_secret_access_key():
    secret_access_key = "*****"

    fake_config_vars = get_fake_config()
    set_aws_creds(fake_config_vars)

    assert os.environ.get("AWS_SECRET_ACCESS_KEY") == secret_access_key
