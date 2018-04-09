# -*- coding: utf-8 -*-
# Based on original implementation by Martin Alnes and Anders Logg
#
# Modified by Anders Logg 2015

__all__ = ["dolfin_tag", "stl_includes", "dolfin_includes", "snippets"]

dolfin_tag = "// DOLFIN wrappers"

stl_includes = """\
// Standard library includes
#include <string.h>
"""

dolfin_includes = """\
// DOLFIN includes
#include <dolfin/fem/Form.h>

namespace dolfin
{
namespace function
{
  class FunctionsSpace;
  class GenericFunction;
}
}
"""

snippets = {"shared_ptr_space":
            ("std::shared_ptr<const dolfin::function::FunctionSpace> %s",
             "    _function_spaces[%d] = %s;"),
            "shared_ptr_mesh":
            ("std::shared_ptr<const dolfin::mesh::Mesh> mesh",
             "    _mesh = mesh;"),
            "shared_ptr_coefficient":
            ("std::shared_ptr<const dolfin::function::GenericFunction> %s",
             "    this->%s = %s;"),
            "functionspace":
            ("TestSpace", "TrialSpace"),
            }
