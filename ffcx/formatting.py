# Copyright (C) 2009-2018 Anders Logg and Garth N. Wells
#
# This file is part of FFCx. (https://www.fenicsproject.org)
#
# SPDX-License-Identifier:    LGPL-3.0-or-later
"""Compiler stage 5: Code formatting.

This module implements the formatting of UFC code from a given
dictionary of generated C++ code for the body of each UFC function.

It relies on templates for UFC code available as part of the module
ufcx_utils.

"""

from __future__ import annotations

import logging
import os

from ffcx.codegeneration.codegeneration import CodeBlocks

logger = logging.getLogger("ffcx")


def format_code(code: CodeBlocks) -> tuple[str, str]:
    """Format given code in UFC format. Returns two strings with header and source file contents."""
    logger.info(79 * "*")
    logger.info("Compiler stage 5: Formatting code")
    logger.info(79 * "*")

    code_c = ""
    code_h = ""
    for parts_code in code:
        code_h += "".join([c[0] for c in parts_code])
        code_c += "".join([c[1] for c in parts_code])

    return code_h, code_c


def write_code(code_h: str, code_c: str, prefix: str, output_dir: str) -> None:
    """Write code to files."""
    _write_file(code_h, prefix, ".h", output_dir)
    _write_file(code_c, prefix, ".c", output_dir)


def _write_file(output: str, prefix: str, postfix: str, output_dir: str) -> None:
    """Write generated code to file."""
    filename = os.path.join(output_dir, prefix + postfix)
    with open(filename, "w") as hfile:
        hfile.write(output)
