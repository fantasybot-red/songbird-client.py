import re
from setuptools import setup

with open("req.txt", "r") as f:
    req = f.read().splitlines()

with open('songbird/__init__.py') as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE).group(1)

setup(
   name='songbird-client.py',
   version=version,
   license="Apache License, Version 2.0",
   author='The DT',
   packages=["songbird"],
   install_requires=req
)
