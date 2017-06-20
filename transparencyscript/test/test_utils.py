import os
import requests
import requests_mock

from transparencyscript.utils import make_transparency_name, get_config_vars, get_task_vars, get_transparency_vars, \
    get_summary
from transparencyscript.test import get_fake_config, get_fake_task, get_fake_transparency


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
    fake_config_vars = get_fake_config()
    fake_task_vars = get_fake_task()

    transparency_vars = get_transparency_vars(fake_config_vars, fake_task_vars)

    assert transparency_vars == fake_transparency_vars


def test_get_summary():
    with requests_mock.Mocker() as m:
        m.get("https://ipv.sx/tmp/SHA256SUMMARY",
              text="eae00f676fc07354cd509994f9946956462805e6950aacba4c1bc9028880efc2 TREE_HEAD")
        summary = requests.get("https://ipv.sx/tmp/SHA256SUMMARY").text

    assert get_summary("https://ipv.sx/tmp/SHA256SUMMARY")[0:74] == summary
