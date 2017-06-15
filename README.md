Binary-Transparency ReadMe
===============================

Testing
-------
1. Clone the repo: `git clone https://github.com/BrandonTang/binary-transparency.git`
2. Setup a python3 virtualenv and install required packages: `pip install -r requirements.txt`
3. Create a config.json file referring to config_example.json, that looks like:
```
    {
          "AWS_KEYS": {
              "AWS_ACCESS_KEY_ID": "*****",
              "AWS_SECRET_ACCESS_KEY": "*****"
          },
          "payload": {
              "lego-path": "...",
              "stage-product": "...",
              "version": "...",
              "contact": "...",
              "summary": "...",
              "chain": "..."
          }
    }
```
4. If using values from only config.json: `venv/bin/python transparencyscript/script.py`
5. If using values from local task.json: 'venv/bin/python transparencyscript/script.py /tmp/work/task.json'
6. If using taskcluster to create task.json, put values in payload of task: 'scriptworker scriptworker.yaml'