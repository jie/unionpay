# !/usr/bin/env python
# encoding: utf-8
# @author: ZhouYang


from upacp import __version__
from setuptools import setup, find_packages


setup(
    name="unionpay",
    version=__version__,
    description="unionpay",
    author="zhouyang",
    author_email="zhouyang@zhouyang.me",
    url="https://zhouyang.me",
    include_package_data=True,
    packages=find_packages(exclude=[
        "_sql/*",
        "_sql",
        "_bin/*",
        "_bin",
        "logs/*",
        "logs",
        "sdklog/*",
        "sdklog",
        ".gitignore",
        "*.pyc"
    ]),
    package_dir={'unionpay': 'unionpay'},
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'unionpay_notify = unionpay.server:main',
        ]
    },
)
