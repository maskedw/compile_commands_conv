#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import with_statement
import argparse
import chardet
import copy
import errno
from itertools import groupby, chain
import jinja2
import json
import os
import os.path
from pkg_resources import resource_filename
from pathlib import Path
import shutil
import re
import sys
import six
import yaml

CONFIG_DIR = '~/.config/compile_commands_conv'
CONFIG_FNAME = 'compile_commands_conv.yml'
CONFIG_FILE = os.path.join(CONFIG_DIR, CONFIG_FNAME)
VALID_COMPILERS = ['gcc', 'g++']
verbose = False


def vlog(*args, **kwargs):
    if verbose:
        print(*args, **kwargs)


def set_verbose(value):
    global verbose
    verbose = value


def get_template(name):
    root = resource_filename(__name__, 'templates')
    template = jinja2.Environment(
        loader=jinja2.FileSystemLoader(root)
    ).get_template(name)

    return template


def get_config(config_file):
    targets = [
        os.path.expanduser(config_file),
        resource_filename(__name__, CONFIG_FNAME)]
    for t in targets:
        if not os.path.exists(t):
            continue
        with open(t, 'rb') as f:
            binary = f.read()
        yaml_str = binary.decode(chardet.detect(binary)['encoding'])
        config = yaml.load(six.StringIO(yaml_str))
        return config
    else:
        raise RuntimeError('Config file could not be found')


def mkdir_p(path):
    path = str(path)
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def filtered_langs(valid_langs, compile_commands_group):
    copied = copy.deepcopy(compile_commands_group)
    result = {
        k: v for k, v in six.iteritems(
            copied) if k in valid_langs}
    return result


class ScopedChDir(object):
    def __init__(self, path):
        self.old_dir = os.getcwd()
        self.new_dir = str(path)

    def __enter__(self):
        os.chdir(self.new_dir)

    def __exit__(self, *args):
        os.chdir(self.old_dir)


class CDTBuilder:
    LANG_MAP = {
        'c': 'C Source File',
        'cpp': 'C++ Source File',
    }

    def build(self, compile_commands_group, options):
        compile_commands_group = filtered_langs(
            CDTBuilder.LANG_MAP.keys(),
            compile_commands_group)

        def make_cdt_lang(c):
            lang = {}
            lang['name'] = CDTBuilder.LANG_MAP[c.lang]

            if options['builder']['cdt']['absolute']:
                lang['include_dirs'] = [
                    os.path.abspath(x) for x in c.include_dirs]
            else:
                lang['include_dirs'] = c.include_dirs

            definitions = []
            for d in c.definitions:
                kv = d.split('=')
                n = kv[0]
                v = kv[1] if len(kv) >= 2 else ''
                definitions.append({'name': n, 'value': v})
            lang['definitions'] = definitions
            return lang

        cdt_languages = []
        for lang, commands in six.iteritems(compile_commands_group):
            command = commands[0]
            cdt_languages.append(make_cdt_lang(command))
        result = {}
        result['cdt_languages'] = cdt_languages
        return result


class ALEBuilder:
    LINTER_MAP = {
        'g++': {
            'filetype': 'cpp',
            'name': 'g++',
            'vname': 'gcc'
        },
        'gcc': {
            'filetype': 'c',
            'name': 'gcc',
            'vname': 'gcc'
        },
    }

    def build(self, compile_commands_group, options):
        compile_commands_group = filtered_langs(
            ['c', 'cpp'], compile_commands_group)

        def make_linter(k, c, options):
            linter = copy.deepcopy(ALEBuilder.LINTER_MAP[k])
            linter['executable'] = c.compiler
            definitions = ['-D' + x for x in c.definitions]
            warning_opts = ['-W' + x for x in c.warning_opts]

            include_dir_list = c.include_dirs
            if options['builder']['ale']['absolute']:
                include_dir_list = [
                    os.path.abspath(x) for x in include_dir_list]
            include_dirs = ['-I' + x for x in include_dir_list]
            options = ' '.join(chain(
                c.machine_opts,
                warning_opts,
                definitions,
                include_dirs,))
            linter['options'] = options
            return linter

        ale_linters = []
        for lang, commands in six.iteritems(compile_commands_group):
            command = commands[0]
            for k in ALEBuilder.LINTER_MAP.keys():
                if command.compiler.endswith(k):
                    ale_linters.append(make_linter(k, command, options))
                    break
        result = {}
        result['ale_linters'] = ale_linters
        return result


class CompileCommand:
    LANG_MAP = {
        '.c': 'c',
        '.cxx': 'cpp',
        '.cpp': 'cpp',
        '.s': 'asm',
        '.S': 'asm',
    }

    def __init__(self, compile_command, options):
        self.file = Path(compile_command['file'])
        self.directory = Path(compile_command['directory'])
        self.lang = CompileCommand.LANG_MAP.get(self.file.suffix, 'unkown')

        command = [x.strip() for x in compile_command['command'].split(' ')]
        command = [x for x in command if x]
        begin_definitions = 0
        for i in range(len(command)):
            if command[i].startswith('-D'):
                begin_definitions = i
                break
        assert(begin_definitions != 0)
        self.compiler = command[0:begin_definitions][-1]
        command = command[begin_definitions:]

        def get_options(command, regstr):
            result = []
            regex = re.compile(regstr)
            for c in command:
                m = regex.match(c)
                if m:
                    result.append(m.group(1))
            return result

        self.definitions = get_options(command, '^-D(.*)')
        self.warning_opts = get_options(command, '^-W(.*)')
        self.machine_opts = get_options(command, '^(-m.*)')

        self.include_dirs = []
        with ScopedChDir(self.directory):
            for x in get_options(command, '^-I(.*)'):
                if not os.path.isabs(x):
                    x = os.path.abspath(x)
                    if not os.path.exists(x):
                        continue
                    x = os.path.relpath(x, start=options['odirectory'])
                self.include_dirs.append(x)


def main():
    argparser = argparse.ArgumentParser(
        description='Convert compile_commands.json output by CMake to another format', # NOQA
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    argparser.add_argument(
        '-d', '--directory',
        required=False,
        default='.',
        help='Directory where commpile_commands.json exists')
    argparser.add_argument(
        '-o', '--out',
        required=False,
        default='.',
        dest='odirectory',
        help='Destination directory')
    argparser.add_argument(
        '-c', '--config',
        required=False,
        default=CONFIG_FILE,
        help='Configuration file')
    argparser.add_argument(
        '-v', '--verbose',
        required=False,
        default=False,
        action='store_true',
        help='Verbose output')

    cmd_args = argparser.parse_args()
    set_verbose(cmd_args.verbose)
    default_config_path = Path(os.path.expanduser(CONFIG_FILE))
    if not default_config_path.exists():
        default_config_dir = default_config_path.parent
        mkdir_p(default_config_dir)
        shutil.copy(
            resource_filename(__name__, CONFIG_FNAME),
            str(default_config_dir))
    config = get_config(os.path.expanduser(cmd_args.config))
    config['odirectory'] = os.path.abspath(cmd_args.odirectory)

    directory = cmd_args.directory
    path = Path(directory, 'compile_commands.json')

    vlog('find compile_commands.json')
    if not path.exists():
        sys.exit('"{}" does not exist'.format(str(path)))

    with path.open() as f:
        raw_compile_commands = json.load(f)

    def is_valid(c):
        compiler = c.compiler
        for v in VALID_COMPILERS:
            if compiler.endswith(v):
                return True
        return False

    vlog('parse compile_commands.json ...')
    compile_commands = [
        CompileCommand(x, config) for x in raw_compile_commands]
    compile_commands = [x for x in compile_commands if is_valid(x)]
    compile_commands = sorted(compile_commands, key=lambda x: x.lang)
    compile_commands_group = {}
    for k, g in groupby(compile_commands, key=lambda x: x.lang):
        compile_commands_group[k] = list(g)

    BUILDER_MAP = {
        'ale': {
            'builder': ALEBuilder,
            'template': 'ale.vimrc',
        },
        'cdt': {
            'builder': CDTBuilder,
            'template': 'cdt.xml',
        }
    }

    for t in config['enabled']:
        x = BUILDER_MAP[t]
        builder = x['builder']()
        vlog('do build "{}"'.format(t))
        template_arg = builder.build(compile_commands_group, config)
        result = get_template(x['template']).render(template_arg)
        path = Path(config['odirectory'], config['builder'][t]['name'])
        with path.open('w') as f:
            vlog('create "{}"'.format(path))
            f.write(result)

    vlog('completed!!')


if __name__ == "__main__":
    main()
