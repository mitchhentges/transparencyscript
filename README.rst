Binary-Transparency ReadMe
==========================

Testing
-------

#. Clone the repo:
   ``git clone https://github.com/BrandonTang/binary-transparency.git``
#. Setup a python3 virtualenv and install required packages:
   ``pip install -r requirements.txt``
#. Create a config.json file referring to config\_example.json, that
   looks like:

   ::

       {
           "AWS_KEYS": {
               "AWS_ACCESS_KEY_ID": "*****",
               "AWS_SECRET_ACCESS_KEY": "*****"
           },
           "lego-path": "...",
           "payload": {
               "stage-product": "...",
               "version": "...",
               "contact": "...",
               "summary": "...",
               "chain": "..."
           }
       }

#. If using values from only config.json:
   ``venv/bin/python transparencyscript/script.py``
#. If using values from local task.json: ‘venv/bin/python
   ``transparencyscript/script.py /tmp/work/task.json``
#. If using taskcluster to create task.json, put values in payload of
   task: ``scriptworker scriptworker.yaml``