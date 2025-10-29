"""
Setup script for mrav2-syslog-connector
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mrav2-syslog-connector",
    version="2.6.7",
    author="Lookout",
    description="Lookout Mobile Risk API v2 to Syslog Connector",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.25.0",
        "requests-oauthlib>=1.3.0",
        "oauthlib>=3.1.0",
        "backoff>=1.10.0",
        "peewee>=3.14.0",
        "furl>=2.1.0",
        "importlib-metadata>=4.0.0",
    ],
    entry_points={
        "console_scripts": [
            "mrav2-syslog-connector=lookout_mra_client.main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
