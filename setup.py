#!/usr/bin/env python3

from setuptools import setup, find_packages

entry_point = '{0} ={0}.{0}:main'.format('compile_commands_conv')
print(entry_point)
desc = 'Convert compile_commands.json output by CMake to another format'

setup(
    name='compile_commands_conv',
    version='0.1.0',
    description=desc,
    long_description='',
    author='MaskedW',
    author_email='maskedw@gmail.com',
    url='',
    license='MIT License',
    packages=find_packages(exclude=('tests', 'docs')),
    package_data={'compile_commands_conv': ['templates/*']},
    entry_points={
        'console_scripts': [entry_point],
    },
    zip_safe=False,
    install_requires=['chardet', 'pathlib', 'jinja2', 'pyyaml', 'six']
)
