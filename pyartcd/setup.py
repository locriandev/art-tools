# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import sys
if sys.version_info < (3, 8):
    sys.exit('Sorry, Python < 3.8 is not supported.')

with open('./requirements.txt') as f:
    INSTALL_REQUIRES = f.read().splitlines()

setup(
    name="pyartcd",
    author="AOS ART Team",
    author_email="aos-team-art@redhat.com",
    setup_requires=['setuptools>=65.5.1', 'setuptools_scm'],
    use_scm_version={
        "root": ".."
    },
    description="Python based pipeline library for managing and automating Red Hat OpenShift Container Platform releases",
    url="https://github.com/openshift-eng/art-tools/tree/main/pyartcd",
    license="Apache License, Version 2.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    entry_points={
        'console_scripts': [
            'artcd = pyartcd.__main__:main'
        ]
    },
    test_suite='tests',
    dependency_links=[],
    python_requires='>=3.8',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Environment :: Console",
        "Operating System :: POSIX",
        "License :: OSI Approved :: Apache Software License",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Natural Language :: English",
    ]
)
