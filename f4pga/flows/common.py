#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 F4PGA Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from os import environ, listdir as os_listdir
from sys import argv as sys_argv
from argparse import Namespace
from shutil import move as sh_mv
from subprocess import run
from re import match as re_match, finditer as re_finditer

from f4pga.context import FPGA_FAM, F4PGA_SHARE_DIR


bin_dir_path = str(Path(sys_argv[0]).resolve().parent.parent)
share_dir_path = str(F4PGA_SHARE_DIR)


class F4PGAException(Exception):
    def __init__(self, message="unknown exception"):
        self.message = message

    def __repr__(self):
        return f"F4PGAException(message = '{self.message}')"

    def __str__(self):
        return self.message


def decompose_depname(name: str):
    spec = "req"
    specchar = name[len(name) - 1]
    if specchar == "?":
        spec = "maybe"
    elif specchar == "!":
        spec = "demand"
    if spec != "req":
        name = name[: len(name) - 1]
    return name, spec


def with_qualifier(name: str, q: str) -> str:
    if q == "req":
        return decompose_depname(name)[0]
    if q == "maybe":
        return decompose_depname(name)[0] + "?"
    if q == "demand":
        return decompose_depname(name)[0] + "!"


def resolve_modstr(modstr: str):
    """
    Resolves module location given its name.
    """
    modpath = Path(__file__).resolve().parent / f"modules/{modstr}.py"
    if not modpath.exists():
        raise Exception(f"Unknown module <{modstr}>!")
    return str(modpath)


def deep(fun, allow_none=False):
    """
    Create a recursive string transform function for 'str | list | dict', i.e a dependency.
    """

    def d(paths, *args, **kwargs):
        nonlocal allow_none
        if type(paths) is str:
            return fun(paths, *args, **kwargs)
        elif type(paths) is list:
            return [d(p, *args, **kwargs) for p in paths]
        elif type(paths) is dict:
            return dict([(k, d(p, *args, **kwargs)) for k, p in paths.items()])
        elif allow_none and (paths is None):
            return paths
        else:
            raise RuntimeError(f"paths is of type {type(paths)}")

    return d


class SubprocessException(Exception):
    return_code: int


def sub(*args, env=None, cwd=None, print_stdout_on_fail=False):
    """
    Execute subroutine.
    """

    out = run(args, capture_output=True, env=env, cwd=cwd)
    if out.returncode != 0:
        print(f"[ERROR]: {args[0]} non-zero return code.\n")
        if print_stdout_on_fail:
            print(f"stdout:\n{out.stdout.decode()}\n\n")
        print(f"stderr:\n{out.stderr.decode()}\n\n")
        exit(out.returncode)
    return out.stdout


def options_dict_to_list(opt_dict: dict):
    """
    Converts a dictionary of named options for CLI program to a list.
    Example: { "option_name": "value" } -> [ "--option_name", "value" ]
    """

    opts = []
    for key, val in opt_dict.items():
        opts.append(f"--{key}")
        if not (type(val) is list and val == []):
            opts.append(str(val))
    return opts


def noisy_warnings(device):
    """
    Emit some noisy warnings.
    """
    environ["OUR_NOISY_WARNINGS"] = f"noisy_warnings-{device}_pack.log"


def fatal(code, message):
    """
    Print a message informing about an error that has occured and terminate program with a given return code.
    """
    raise (Exception(f"[FATAL ERROR]: {message}"))
    exit(code)


class ResolutionEnv:
    """
    ResolutionEnv is used to hold onto mappings for variables used in flow and perform text substitutions using those
    variables.
    Variables can be referred in any "resolvable" string using the following syntax: 'Some static text ${variable_name}'.
    The '${variable_name}' part will be replaced by the value associated with name 'variable_name', is such mapping
    exists.

    values: dict
    """

    def __init__(self, values={}):
        self.values = values

    def __copy__(self):
        return ResolutionEnv(self.values.copy())

    def resolve(self, s, final=False):
        """
        Perform resolution on `s`.
        `s` can be a `str`, a `dict` with arbitrary keys and resolvable values, or a `list` of resolvable values.
        final=True - resolve any unknown variables into ''
        This is a hack and probably should be removed in the future
        """

        if type(s) is str:
            match_list = list(re_finditer("\$\{([^${}]*)\}", s))
            # Assumption: re_finditer finds matches in a left-to-right order
            match_list.reverse()
            for match in match_list:
                match_str = match.group(1)
                match_str = match_str.replace("?", "")
                v = self.values.get(match_str)
                if not v:
                    if final:
                        v = ""
                    else:
                        continue
                span = match.span()
                if type(v) is str:
                    s = s[: span[0]] + v + s[span[1] :]
                elif type(v) is list:  # Assume it's a list of strings
                    ns = list([s[: span[0]] + ve + s[span[1] :] for ve in v])
                    s = ns

        elif type(s) is list:
            s = list(map(self.resolve, s))
        elif type(s) is dict:
            s = dict([(k, self.resolve(v)) for k, v in s.items()])
        return s

    def add_values(self, values: dict):
        """
        Add mappings from `values`.
        """
        for k, v in values.items():
            if k in self.values and isinstance(self.values[k], dict):
                self.values[k].update(self.resolve(v))
            else:
                self.values[k] = self.resolve(v)


verbosity_level = 0


def sfprint(verbosity: int, *args):
    """
    Print with regards to currently set verbosity level.
    """
    global verbosity_level
    if verbosity <= verbosity_level:
        print(*args)


def set_verbosity_level(level: int):
    global verbosity_level
    verbosity_level = level


def get_verbosity_level() -> int:
    global verbosity_level
    return verbosity_level
