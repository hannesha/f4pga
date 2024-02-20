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

from os import environ
from pathlib import Path

from f4pga.context import FPGA_FAM
from f4pga.flows.common import decompose_depname, get_verbosity_level, sub as common_sub
from f4pga.flows.module import Module, ModuleContext
from f4pga.wrappers.tcl import get_script_path as get_tcl_wrapper_path


class YosysModule(Module):
    extra_products: "list[str]"

    def map_io(self, ctx: ModuleContext):
        top = Path(ctx.takes.build_dir) / ctx.values.top if ctx.takes.build_dir else Path(ctx.values.top)

        mapping = {
            "eblif": f"{top!s}.eblif",
            "fasm_extra": f"{top!s}_fasm_extra.fasm",
            "json": f"{top!s}.json",
            "synth_json": f"{top!s}_io.json",
        }

        for extra in self.extra_products:
            name, spec = decompose_depname(extra)
            if spec == "maybe":
                raise ModuleRuntimeException(
                    f"Yosys synth extra products can't use 'maybe\ "
                    f"(?) specifier. Product causing this error: `{extra}`."
                )
            elif spec == "req":
                mapping[name] = str(top.parent / f"{ctx.values.device}_{name}.{name}")

        return mapping

    def execute(self, ctx: ModuleContext):
        yield f"Synthesizing sources{f': {ctx.takes.sources}...' if get_verbosity_level() >= 2 else f'...'}"

        # Set up environment for TCL weirdness
        env = environ.copy()
        env.update(
            (
                {
                    key: (" ".join(val) if type(val) is list else val)
                    for key, val in ctx.values.yosys_tcl_env.items()
                    if val is not None
                }
                if ctx.values.yosys_tcl_env
                else {}
            )
        )

        # Execute YOSYS command
        args_str = "" if ctx.values.read_verilog_args is None else " ".join(ctx.values.read_verilog_args)

        extra_args = ["-l", ctx.outputs.synth_log] if ctx.outputs.synth_log else []
        if ctx.values.extra_args is not None:
            extra_args.extend(ctx.values.extra_args)

        source_paths = [Path(f) for f in ctx.takes.sources]

        def is_verilog(f: Path):
            ext = f.suffix.lower()
            verilog_extensions = [".v", ".sv"]
            return ext in verilog_extensions

        verilog_files = filter(is_verilog, source_paths)

        def is_rtlil(f: Path):
            ext = f.suffix.lower()
            rtlil_extensions = [".il", ".rtlil"]
            return ext in rtlil_extensions

        rtlil_files = filter(is_rtlil, source_paths)

        common_sub(
            *(
                ["yosys"]
                + extra_args
                + [
                    "-p",
                    (
                        " ".join([f"read_verilog {args_str} {vfile}; " for vfile in verilog_files])
                        + " ".join([f"read_rtlil {file}; " for file in rtlil_files])
                        + f" tcl {str(get_tcl_wrapper_path(pnrtool=self.pnrtool))}"
                    ),
                ]
            ),
            env=env,
        )

        if self.pnrtool == "vpr":
            if not Path(ctx.produces.fasm_extra).is_file():
                with Path(ctx.produces.fasm_extra).open("w") as wfptr:
                    wfptr.write("")

    def __init__(self, params):
        self.name = "yosys"
        self.no_of_phases = 3

        self.pnrtool = "nextpnr" if FPGA_FAM == "ice40" else "vpr"

        self.takes = ["sources", "build_dir?"]
        # Extra takes for use with TCL scripts
        extra_takes = params.get("takes")
        if extra_takes:
            self.takes += extra_takes

        self.produces = ["json", "synth_log!"]
        if self.pnrtool == "vpr":
            self.produces.extend(
                [
                    "eblif",
                    "fasm_extra",
                    "synth_json",
                ]
            )
        # Extra products for use with TCL scripts
        extra_products = params.get("produces")
        if extra_products:
            self.produces += extra_products
            self.extra_products = extra_products
        else:
            self.extra_products = []

        self.values = [
            "top",
            "device",
            "tcl_scripts?",
            "extra_args?",
            "yosys_tcl_env?",
            "read_verilog_args?",
        ]
        self.prod_meta = {
            "eblif": "Extended BLIF hierarchical sequential designs file\n" "generated by YOSYS",
            "json": "JSON file containing a design generated by YOSYS",
            "synth_log": "YOSYS synthesis log",
            "fasm_extra": "Extra FASM generated during sythesis stage. Needed in "
            "some designs.\nIn case it's not necessary, the file "
            "will be empty.",
        }
        extra_meta = params.get("prod_meta")
        if extra_meta:
            self.prod_meta.update(extra_meta)


ModuleClass = YosysModule
