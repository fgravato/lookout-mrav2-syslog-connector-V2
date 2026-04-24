"""
Setup script for mrav2-syslog-connector
"""
from setuptools import setup, find_packages


def _requires():
    with open("requirements.txt") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mrav2-syslog-connector",
    version="2.7.0",
    author="Lookout",
    description="Lookout Mobile Risk API v2 to Syslog Connector",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=_requires(),
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
