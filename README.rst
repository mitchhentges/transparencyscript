Binary-Transparency ReadMe
==========================

Testing
-------

#. Clone the repo:
   ``git clone https://github.com/BrandonTang/binary-transparency.git``
#. Setup a python3 virtualenv named transparencyscript-venv, activate, and install required packages:
   ``virtualenv -p python3 transparency-venv`` & ``source transparency-venv/bin/activate`` & ``pip install -r requirements.txt``
#. Install transparencyscript in developer mode into the virtualenv: ``pip install -e .``
#. Create a script_config.json file referring to script\_config\_example.json, that looks like:

    ::

        {
            "work_dir": ".",
            "public_artifact_dir": ".",
            "lego-path": "/Users/btang/go/bin/lego",
            "sct_filename": "sct_list.bin",
            "log_list": {
                "pilot": "https://ct.googleapis.com/pilot",
                "rocketeer": "https://ct.googleapis.com/rocketeer"
            },
            "payload": {
                "stage-product": "firefox",
                "version": "53.0b5",
                "contact": "btang@mozilla.com",
                "summary": "https://ipv.sx/tmp/SHA256SUMMARY",
                "chain": "TRANSPARENCY.pem"
            }
        }


#. Create a passwords.json file referring to passwords\_example.json, that looks like:

    ::

        {
            "AWS_KEYS": {
                "AWS_ACCESS_KEY_ID": "*****",
                "AWS_SECRET_ACCESS_KEY": "*****"
            }
        }



#. Run the script and pass in the script_config file that is required:
   ``transparency-venv/bin/python transparencyscript/script.py script_config.json``
#. If using values from local task.json, add a task_json path to the script_config.json, that looks like:
   ``"task_json": "/tmp/work/task.json"``
   Then, run the previous command.
#. If using taskcluster to create task.json, put values in payload of task, then run scriptworker:
   ``scriptworker scriptworker.yaml``
#. For testing: ``pip install pytest`` and ``py.test transparencyscript/test/test_utils.py``
#. To create a source distribution: ``python setup.py sdist``