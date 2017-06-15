import os
import json
from setuptools import setup, find_packages

PATH = os.path.join(os.path.dirname(__file__), "version.json")
with open(PATH) as filehandle:
    VERSION = json.load(filehandle)['version_string']

setup(
    name="transparencyscript",
    version=VERSION,
    description="TaskCluster Binary Transparency Script",
    author="Mozilla Release Engineering",
    author_email="release+python@mozilla.com",
    url="https://github.com/BrandonTang/binary-transparency",
    license="MPL2",
    classifiers=(
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
    ),
    packages=find_packages(),
    install_requires=[
        "redo",
        "requests",
        "scriptworker",
        "taskcluster"
    ],
    package_data={
        "": ["version.json"],
    },
    entry_points={
        "console_scripts": [
            "transparencyscript = transparencyscript.script:main",
        ],
    }
)
