import os
import sys
from subprocess import check_call

from transparencyscript.constants import TRANSPARENCY_SUFFIX
from transparencyscript.utils import make_transparency_name, get_config_vars, get_password_vars, get_task_vars, \
    get_transparency_vars, get_tree_head, get_lego_env, get_lego_command, get_save_command, get_chain, post_chain, \
    write_to_file
from transparencyscript.signed_certificate_timestamp import SignedCertificateTimestamp


def main(name=None):
    if name not in (None, '__main__'):
        return

    # Store default parameters and keys in config_vars
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        config_vars = get_config_vars(config_path)
    else:
        print("ERROR: script_config.json path is required as an argument.")
        sys.exit(1)

    # Store AWS credentials in password_vars
    password_path = os.path.join(os.path.dirname(config_path), 'passwords.json')
    password_vars = get_password_vars(password_path)

    # Concatenate local config_vars with task_vars created from task.json
    if "task_json" in config_vars:
        task_path = config_vars["task_json"]
        task_vars = get_task_vars(task_path)
        config_vars = get_transparency_vars(config_vars, task_vars)

    # Parse tree head from summary file
    tree_head = get_tree_head(config_vars)

    if tree_head is None:
        raise Exception("No tree head found in summary file")

    base_name = "{}.{}".format("invalid", TRANSPARENCY_SUFFIX)
    trans_name = make_transparency_name(tree_head, config_vars["payload"]["version"],
                                        config_vars["payload"]["stage-product"])

    # Issue and save the certificate, then delete the extra files lego created
    lego_env = get_lego_env(password_vars)
    lego_command = get_lego_command(config_vars, base_name, trans_name)
    save_command = get_save_command(config_vars, base_name)
    cleanup_command = "rm -rf {}/lego".format(config_vars["work_dir"])

    check_call(lego_command, env=lego_env, shell=True)
    check_call(save_command, shell=True)
    check_call(cleanup_command, shell=True)

    # Submit chain to certificate transparency log if log_list exists
    if 'log_list' in config_vars:
        req = get_chain(config_vars)
        resp_list = post_chain(config_vars["log_list"], req)

        # Remove sct_list file if it already exists
        sct_file_path = os.path.join(config_vars["public_artifact_dir"], config_vars["sct_filename"])
        try:
            os.remove(sct_file_path)
        except OSError:
            pass

        # Append to sct_list file for each chain
        for resp in resp_list:
            sct = SignedCertificateTimestamp(resp)
            write_to_file(sct_file_path, sct.to_rfc6962(), open_mode='ab')


main(name=__name__)
