# compile_commands_conv

## Descriptions
Convert compile_commands.json output by CMake to another format

## Features
Convert compilie_commands.json to `=>`

+ [ALE](https://github.com/w0rp/ale) options
+ [Eclipse CDT](https://www.eclipse.org/cdt/) Path and Symbols

## Supprted OS
+ Windows
+ `*nix`

## Requirement
+ Python2.7 or Python3+

## Installation
```sh
$ pip install git+https://github.com/maskedw/compile_commands_conv
```

## Usage
```sh
$ compile_commands_conv -h
usage: compile_commands_conv [-h] [-d DIRECTORY] [-o ODIRECTORY] [-c CONFIG]
                             [-v]

Convert compile_commands.json output by CMake to another format

optional arguments:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Directory where commpile_commands.json exists
                        (default: .)
  -o ODIRECTORY, --out ODIRECTORY
                        Destination directory (default: .)
  -c CONFIG, --config CONFIG
                        Configuration file (default: ~/.config/compile_commands_conv/compile_commands_conv.yml)
  -v, --verbose         Verbose output (default: False)
```
