import os
import re
import sys

from subprocess import check_call
from redo import retry

from transparencyscript.constants import TRANSPARENCY_SUFFIX
from transparencyscript.utils import make_transparency_name, get_config_vars, get_task_vars, get_transparency_vars, \
    get_summary, get_lego_env, get_lego_command, get_save_command


def main(name=None):
    if name not in (None, '__main__'):
        return

    # Store default parameters and keys in config_vars
    config_path = os.path.join(os.getcwd(), 'config.json')
    config_vars = get_config_vars(config_path)

    if len(sys.argv) > 1:
        task_path = sys.argv[1]
        task_vars = get_task_vars(task_path)
        config_vars = get_transparency_vars(config_vars, task_vars)

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
    lego_env = get_lego_env(config_vars)
    lego_command = get_lego_command(config_vars, base_name, trans_name)
    save_command = get_save_command(config_vars, base_name)
    cleanup_command = "rm -rf ./.lego"

    check_call(lego_command, env=lego_env, shell=True)
    check_call(save_command, shell=True)
    check_call(cleanup_command, shell=True)


main(name=__name__)
