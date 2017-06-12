Binary-Transparency ReadMe
===============================

Testing
-------
1. Clone the repo: `git clone https://github.com/BrandonTang/binary-transparency.git`
2. Setup a virtualenv and install required packages: `pip install -r requirements.txt`
3. Create a config.json file referring to config_example.json, that looks like:
```
    {
          "AWS_KEYS": {
              "AWS_ACCESS_KEY_ID": "*****",
              "AWS_SECRET_ACCESS_KEY": "*****"
          },
          "ISSUE_TRANSPARENCY_CERT_ARGUMENTS": {
              "--stage-product": "...",
              "--version": "...",
              "--contact": "...",
              "--summary": "...",
              "--chain": "..."
          }
    }
```
4. Run the script: `python binarytransparencyscript/issue-transparency-script.py`
