# -*- coding:utf-8 -*-

from setuptools import find_packages, setup

version = '0.1.8'

setup(
    name='torstomp',
    version=version,
    description='Simple Stomp 1.1 client for tornado applications',
    long_description='',
    classifiers=[],
    keywords='stomp',
    author='Wilson Júnior',
    author_email='wilsonpjunior@gmail.com',
    url='https://github.com/wpjunior/torstomp.git',
    license='MIT',
    include_package_data=True,
    packages=find_packages(exclude=["tests", "tests.*"]),
    platforms=['any'],
    install_requires=[
        'six',
        'tornado'
    ],
    extras_require={
        'tests': [
            'mock',
            'nose',
            'coverage',
            "yanc",
            "nose_focus",
            "flake8",
        ]
    }
)
