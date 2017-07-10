Binary-Transparency ReadMe
==========================

Testing
-------

#. Clone the repo:
   ``git clone https://github.com/BrandonTang/binary-transparency.git``
#. Setup a python3 virtualenv and install required packages:
   ``pip install -r requirements.txt``
#. Create a script_config.json file referring to config\_example.json, that
   looks like:

    ::

        {
            "scriptworker_dir": ".",
            "work_dir": ".",
            "public_artifact_dir": ".",
            "lego-path": "/Users/btang/go/bin/lego",
            "payload": {
                "stage-product": "firefox",
                "version": "53.0b5",
                "contact": "btang@mozilla.com",
                "summary": "https://ipv.sx/tmp/SHA256SUMMARY",
                "chain": "TRANSPARENCY.pem"
            }
        }


#. Run the script and pass in the script_config file that is required:
   ``venv/bin/python transparencyscript/script.py script_config.json``
#. If using values from local task.json, add a task_json path to the script_config.json and run the previous command:
   ``"task_json": "/tmp/work/task.json"``
#. If using taskcluster to create task.json, put values in payload of task, then run scriptworker:
   ``scriptworker scriptworker.yaml``
#. For testing: ``pip install pytest`` and ``py.test transparencyscript/test/test_utils.py``
#. To create a source distribution: ``python setup.py sdist``