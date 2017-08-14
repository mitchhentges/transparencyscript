import os
import requests
import requests_mock
import json

from transparencyscript.utils import make_transparency_name, get_config_vars, get_password_vars, get_task_vars, \
    get_transparency_vars, get_summary, get_lego_env, get_lego_command, get_save_command, get_chain, write_to_file
from transparencyscript.test import get_fake_config, get_fake_passwords, get_fake_task, get_fake_transparency
from transparencyscript.constants import SUMMARY_TEXT, TRANSPARENCY_SUFFIX


def test_make_transparency_name():
    correct_name = "eae00f676fc07354cd509994f9946956.462805e6950aacba4c1bc9028880efc2.53-0b5.firefox.0.stage." \
                   "fx-trans.net"

    tree_head_hex = "eae00f676fc07354cd509994f9946956462805e6950aacba4c1bc9028880efc2"
    version = "53.0b5"
    product = "firefox"

    assert make_transparency_name(tree_head_hex, version, product) == correct_name


def test_get_config_vars():
    fake_config_vars = get_fake_config()

    config_path = os.path.join(os.getcwd(), 'transparencyscript/test/fake_config.json')
    config_vars = get_config_vars(config_path)

    assert config_vars == fake_config_vars


def test_get_password_vars():
    fake_password_vars = get_fake_passwords()

    password_path = os.path.join(os.getcwd(), 'transparencyscript/test/fake_passwords.json')
    password_vars = get_password_vars(password_path)

    assert password_vars == fake_password_vars


def test_get_task_vars():
    fake_task_vars = get_fake_task()

    task_path = os.path.join(os.getcwd(), 'transparencyscript/test/fake_task.json')
    task_vars = get_task_vars(task_path)

    assert task_vars == fake_task_vars


def test_get_transparency_vars():
    fake_transparency_vars = get_fake_transparency()

    fake_config_vars = get_fake_config()
    fake_task_vars = get_fake_task()

    transparency_vars = get_transparency_vars(fake_config_vars, fake_task_vars)

    assert transparency_vars == fake_transparency_vars


def test_get_summary():
    with requests_mock.Mocker() as m:
        m.get("https://ipv.sx/tmp/SHA256SUMMARY", text=SUMMARY_TEXT)
        summary = requests.get("https://ipv.sx/tmp/SHA256SUMMARY").text

    assert get_summary("https://ipv.sx/tmp/SHA256SUMMARY")[0:447] == summary


def test_get_lego_env():
    correct_lego_env = {'AWS_ACCESS_KEY_ID': '*****', 'AWS_SECRET_ACCESS_KEY': '*****', 'AWS_REGION': 'us-west-2'}

    password_vars = get_fake_passwords()

    lego_env = get_lego_env(password_vars)

    assert lego_env == correct_lego_env


def test_get_lego_command():
    correct_lego_command = "/Users/btang/go/bin/lego  --dns route53  --domains invalid.stage.fx-trans.net  --domains " \
                           "eae00f676fc07354cd509994f9946956.462805e6950aacba4c1bc9028880efc2.53-0b5.firefox.0." \
                           "stage.fx-trans.net  --email btang@mozilla.com  --path ./lego  " \
                           "--accept-tos run"

    config_vars = get_fake_config()
    base_name = "{}.{}".format("invalid", TRANSPARENCY_SUFFIX)
    trans_name = "eae00f676fc07354cd509994f9946956.462805e6950aacba4c1bc9028880efc2.53-0b5.firefox.0.stage.fx-trans.net"

    lego_command = get_lego_command(config_vars, base_name, trans_name)

    assert lego_command == correct_lego_command


def test_get_save_command():
    correct_save_command = "mv ./lego/certificates/invalid.stage.fx-trans.net.crt " \
                           "./transparencyscript/test/FAKE_TRANSPARENCY.pem"

    config_vars = get_fake_config()
    base_name = "{}.{}".format("invalid", TRANSPARENCY_SUFFIX)

    save_command = get_save_command(config_vars, base_name)

    assert save_command == correct_save_command


def test_get_chain():
    correct_req = '{"chain" : ["CERTIFICATE1", "CERTIFICATE2"]}'

    config_vars = get_fake_config()
    req = get_chain(config_vars)

    assert req == correct_req


def test_post_chain():
    correct_resp_list = [{'sct_version': 0, 'id': 'testid1', 'timestamp': 12345, 'extensions': '',
                          'signature': 'signature1'},
                         {'sct_version': 0, 'id': 'testid2', 'timestamp': 54321, 'extensions': '',
                          'signature': 'signature2'}]

    config_vars = get_fake_config()
    req = '{"chain" : ["CERTIFICATE1", "CERTIFICATE2"]}'

    resp_list = []
    log_list = config_vars["log_list"]

    for log in log_list.keys():
        if log_list[log] == "https://ct.googleapis.com/pilot":
            with requests_mock.Mocker() as m:
                m.post("https://ct.googleapis.com/pilot" + "/ct/v1/add-chain",
                       text='{"sct_version":0,"id":"testid1","timestamp":12345,"extensions":"",'
                            '"signature":"signature1"}')
                r = requests.post("https://ct.googleapis.com/pilot" + "/ct/v1/add-chain", data=req, verify=False,
                                   timeout=2).text

        elif log_list[log] == "https://ct.googleapis.com/rocketeer":
            with requests_mock.Mocker() as m:
                m.post("https://ct.googleapis.com/rocketeer" + "/ct/v1/add-chain",
                       text='{"sct_version":0,"id":"testid2","timestamp":54321,"extensions":"",'
                            '"signature":"signature2"}')
                r = requests.post("https://ct.googleapis.com/rocketeer" + "/ct/v1/add-chain", data=req, verify=False,
                                   timeout=2).text

        else:
            assert False

        r = json.loads(r)

        resp_list.append(r)

    assert resp_list == correct_resp_list
