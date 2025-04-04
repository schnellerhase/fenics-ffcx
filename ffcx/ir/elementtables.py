# Copyright (C) 2013-2017 Martin Sandve Alnæs
#
# This file is part of FFCx. (https://www.fenicsproject.org)
#
# SPDX-License-Identifier:    LGPL-3.0-or-later
"""Tools for precomputed tables of terminal values."""

import logging
import typing

import basix.ufl
import numpy as np
import numpy.typing as npt
import ufl

from ffcx.definitions import entity_types
from ffcx.element_interface import basix_index
from ffcx.ir.analysis.modified_terminals import ModifiedTerminal
from ffcx.ir.representationutils import (
    QuadratureRule,
    create_quadrature_points_and_weights,
    integral_type_to_entity_dim,
    map_integral_points,
)

logger = logging.getLogger("ffcx")

# Using same defaults as np.allclose
default_rtol = 1e-6
default_atol = 1e-9

piecewise_ttypes = ("piecewise", "fixed", "ones", "zeros")
uniform_ttypes = ("fixed", "ones", "zeros", "uniform")


class ModifiedTerminalElement(typing.NamedTuple):
    """Modified terminal element."""

    element: basix.ufl._ElementBase
    averaged: str
    local_derivatives: tuple[int, ...]
    fc: int


class UniqueTableReferenceT(typing.NamedTuple):
    """Unique table reference."""

    name: str
    values: npt.NDArray[np.float64]
    offset: typing.Optional[int]
    block_size: typing.Optional[int]
    ttype: typing.Optional[str]
    is_piecewise: bool
    is_uniform: bool
    is_permuted: bool
    has_tensor_factorisation: bool
    tensor_factors: typing.Optional[list[typing.Any]]
    tensor_permutation: typing.Optional[np.typing.NDArray[np.int32]]


def equal_tables(a, b, rtol=default_rtol, atol=default_atol):
    """Check if two tables are equal."""
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape:
        return False
    else:
        return np.allclose(a, b, rtol=rtol, atol=atol)


def clamp_table_small_numbers(
    table, rtol=default_rtol, atol=default_atol, numbers=(-1.0, 0.0, 1.0)
):
    """Clamp almost 0,1,-1 values to integers. Returns new table."""
    # Get shape of table and number of columns, defined as the last axis
    table = np.asarray(table)
    for n in numbers:
        table[np.where(np.isclose(table, n, rtol=rtol, atol=atol))] = n
    return table


def get_ffcx_table_values(
    points,
    cell,
    integral_type,
    element,
    avg,
    entity_type: entity_types,
    derivative_counts,
    flat_component,
    codim,
):
    """Extract values from FFCx element table.

    Returns a 3D numpy array with axes
    (entity number, quadrature point number, dof number)
    """
    deriv_order = sum(derivative_counts)

    if integral_type in ufl.custom_integral_types:
        # Use quadrature points on cell for analysis in custom integral types
        integral_type = "cell"
        assert not avg

    if integral_type == "expression":
        # FFCx tables for expression are generated as either interior cell points
        # or points on a facet
        if entity_type == "cell":
            integral_type = "cell"
        else:
            integral_type = "exterior_facet"

    if avg in ("cell", "facet"):
        # Redefine points to compute average tables

        # Make sure this is not called with points, that doesn't make sense
        # assert points is None

        # Not expecting derivatives of averages
        assert not any(derivative_counts)
        assert deriv_order == 0

        # Doesn't matter if it's exterior or interior facet integral,
        # just need a valid integral type to create quadrature rule
        if avg == "cell":
            integral_type = "cell"
        elif avg == "facet":
            integral_type = "exterior_facet"

        if isinstance(element, basix.ufl._QuadratureElement):
            points = element._points
            weights = element._weights
        else:
            # Make quadrature rule and get points and weights
            points, weights = create_quadrature_points_and_weights(
                integral_type, cell, element.embedded_superdegree(), "default", [element]
            )

    # Tabulate table of basis functions and derivatives in points for each entity
    tdim = cell.topological_dimension()
    entity_dim = integral_type_to_entity_dim(integral_type, tdim)
    num_entities = cell.num_sub_entities(entity_dim)

    # Extract arrays for the right scalar component
    component_tables = []
    component_element, offset, stride = element.get_component_element(flat_component)

    for entity in range(num_entities):
        if codim == 0:
            entity_points = map_integral_points(points, integral_type, cell, entity)
        elif codim == 1:
            entity_points = points
        else:
            raise RuntimeError("Codimension > 1 isn't supported.")
        tbl = component_element.tabulate(deriv_order, entity_points)
        tbl = tbl[basix_index(derivative_counts)]
        component_tables.append(tbl)

    if avg in ("cell", "facet"):
        # Compute numeric integral of the each component table
        wsum = sum(weights)
        for entity, tbl in enumerate(component_tables):
            num_dofs = tbl.shape[1]
            tbl = np.dot(tbl, weights) / wsum
            tbl = np.reshape(tbl, (1, num_dofs))
            component_tables[entity] = tbl

    # Loop over entities and fill table blockwise (each block = points x dofs)
    # Reorder axes as (points, dofs) instead of (dofs, points)
    assert len(component_tables) == num_entities
    num_points, num_dofs = component_tables[0].shape
    shape = (1, num_entities, num_points, num_dofs)
    res = np.zeros(shape)
    for entity in range(num_entities):
        res[:, entity, :, :] = component_tables[entity]

    return {"array": res, "offset": offset, "stride": stride}


def generate_psi_table_name(
    quadrature_rule: QuadratureRule,
    element_counter,
    averaged: str,
    entity_type: entity_types,
    derivative_counts,
    flat_component,
):
    """Generate a name for the psi table.

    Format:
        FE#_C#_D###[_AC|_AF|][_F|V][_Q#], where '#' will be an integer value and:
        - FE is a simple counter to distinguish the various bases, it will be
          assigned in an arbitrary fashion.
        - C is the component number if any (this does not yet take into account
          tensor valued functions)
        - D is the number of derivatives in each spatial direction if any.
          If the element is defined in 3D, then D012 means d^3(*)/dydz^2.
        - AC marks that the element values are averaged over the cell
        - AF marks that the element values are averaged over the facet
        - F marks that the first array dimension enumerates facets on the cell
        - V marks that the first array dimension enumerates vertices on the cell
        - Q unique ID of quadrature rule, to distinguish between tables
          in a mixed quadrature rule setting
    """
    name = f"FE{element_counter:d}"
    if flat_component is not None:
        name += f"_C{flat_component:d}"
    if any(derivative_counts):
        name += "_D" + "".join(str(d) for d in derivative_counts)
    name += {None: "", "cell": "_AC", "facet": "_AF"}[averaged]
    name += {"cell": "", "facet": "_F", "vertex": "_V"}[entity_type]
    name += f"_Q{quadrature_rule.id()}"
    return name


def get_modified_terminal_element(mt) -> typing.Optional[ModifiedTerminalElement]:
    """Get modified terminal element."""
    gd = mt.global_derivatives
    ld = mt.local_derivatives
    domain = ufl.domain.extract_unique_domain(mt.terminal)
    # Extract element from FormArguments and relevant GeometricQuantities
    if isinstance(mt.terminal, ufl.classes.FormArgument):
        if gd and mt.reference_value:
            raise RuntimeError("Global derivatives of reference values not defined.")
        elif ld and not mt.reference_value:
            raise RuntimeError("Local derivatives of global values not defined.")
        element = mt.terminal.ufl_function_space().ufl_element()
        fc = mt.flat_component
    elif isinstance(mt.terminal, ufl.classes.SpatialCoordinate):
        if mt.reference_value:
            raise RuntimeError("Not expecting reference value of x.")
        if gd:
            raise RuntimeError("Not expecting global derivatives of x.")
        element = domain.ufl_coordinate_element()
        if not ld:
            fc = mt.flat_component
        else:
            # Actually the Jacobian expressed as reference_grad(x)
            fc = mt.flat_component  # x-component
            assert len(mt.component) == 1
            assert mt.component[0] == mt.flat_component
    elif isinstance(mt.terminal, ufl.classes.Jacobian):
        if mt.reference_value:
            raise RuntimeError("Not expecting reference value of J.")
        if gd:
            raise RuntimeError("Not expecting global derivatives of J.")
        element = domain.ufl_coordinate_element()
        assert len(mt.component) == 2
        # Translate component J[i,d] to x element context rgrad(x[i])[d]
        fc, d = mt.component  # x-component, derivative
        ld = tuple(sorted((d,) + ld))
    else:
        return None

    assert (mt.averaged is None) or not (ld or gd)
    # Change derivatives format for table lookup
    tdim = domain.topological_dimension()
    local_derivatives: tuple[int, ...] = tuple(ld.count(i) for i in range(tdim))

    return ModifiedTerminalElement(element, mt.averaged, local_derivatives, fc)


def permute_quadrature_interval(points, reflections=0):
    """Permute quadrature points for an interval."""
    output = points.copy()
    for p in output:
        assert len(p) < 2 or np.isclose(p[1], 0)
        assert len(p) < 3 or np.isclose(p[2], 0)
    for _ in range(reflections):
        for n, p in enumerate(output):
            output[n] = [1 - p[0]]
    return output


def permute_quadrature_triangle(points, reflections=0, rotations=0):
    """Permute quadrature points for a triangle."""
    output = points.copy()
    for p in output:
        assert len(p) < 3 or np.isclose(p[2], 0)
    for _ in range(rotations):
        for n, p in enumerate(output):
            output[n] = [p[1], 1 - p[0] - p[1]]
    for _ in range(reflections):
        for n, p in enumerate(output):
            output[n] = [p[1], p[0]]
    return output


def permute_quadrature_quadrilateral(points, reflections=0, rotations=0):
    """Permute quadrature points for a quadrilateral."""
    output = points.copy()
    for p in output:
        assert len(p) < 3 or np.isclose(p[2], 0)
    for _ in range(rotations):
        for n, p in enumerate(output):
            output[n] = [p[1], 1 - p[0]]
    for _ in range(reflections):
        for n, p in enumerate(output):
            output[n] = [p[1], p[0]]
    return output


def build_optimized_tables(
    quadrature_rule: QuadratureRule,
    cell: ufl.Cell,
    integral_type: str,
    entity_type: entity_types,
    modified_terminals: typing.Iterable[ModifiedTerminal],
    existing_tables: dict[str, np.ndarray],
    use_sum_factorization: bool,
    is_mixed_dim: bool,
    rtol: float = default_rtol,
    atol: float = default_atol,
) -> dict[typing.Union[ModifiedTerminal, str], UniqueTableReferenceT]:
    """Build the element tables needed for a list of modified terminals.

    Args:
        quadrature_rule: The quadrature rule relating to the tables.
        cell: The cell type of the domain the tables will be used with.
        entity_type: The entity type (vertex,edge,facet,cell) that the tables are evaluated for.
        integral_type: The type of integral the tables are used for.
        modified_terminals: Ordered sequence of unique modified terminals
        existing_tables: Register of tables that already exist and reused.
        use_sum_factorization: Use sum factorization for tensor product elements.
        is_mixed_dim: Mixed dimensionality of the domain.
        rtol: Relative tolerance for comparing tables.
        atol: Absolute tolerance for comparing tables.

    Returns:
      mt_tables:
        Dictionary mapping each modified terminal to the a unique table reference.
        If ``use_sum_factorization`` is turned on, the map also contains the map
        from the unique table reference for the tensor product factorization
        to the name of the modified terminal.

    """
    # Add to element tables
    analysis = {}
    for mt in modified_terminals:
        res = get_modified_terminal_element(mt)
        if res:
            analysis[mt] = res

    # Build element numbering using topological ordering so subelements
    # get priority
    all_elements = [res[0] for res in analysis.values()]
    unique_elements = ufl.algorithms.sort_elements(
        set(ufl.algorithms.analysis.extract_sub_elements(all_elements))
    )
    element_numbers = {element: i for i, element in enumerate(unique_elements)}
    mt_tables: dict[typing.Union[ModifiedTerminal, str], UniqueTableReferenceT] = {}

    _existing_tables = existing_tables.copy()

    all_tensor_factors: list[UniqueTableReferenceT] = []
    tensor_n = 0

    for mt in modified_terminals:
        res = analysis.get(mt)
        if not res:
            continue
        element, avg, local_derivatives, flat_component = res

        # Generate table and store table name with modified terminal

        # Build name for this particular table
        element_number = element_numbers[element]
        name = generate_psi_table_name(
            quadrature_rule, element_number, avg, entity_type, local_derivatives, flat_component
        )

        # FIXME - currently just recalculate the tables every time,
        # only reusing them if they match numerically.
        # It should be possible to reuse the cached tables by name, but
        # the dofmap offset may differ due to restriction.

        tdim = cell.topological_dimension()
        codim = tdim - element.cell.topological_dimension()
        assert codim >= 0
        if codim > 1:
            raise RuntimeError("Codimension > 1 isn't supported.")

        # Only permute quadrature rules for interior facets integrals and for
        # the codim zero element in mixed-dimensional integrals. The latter is
        # needed because a cell may see its sub-entities as being oriented
        # differently to their global orientation
        if integral_type == "interior_facet" or (is_mixed_dim and codim == 0):
            if tdim == 1 or codim == 1:
                # Do not add permutations if codim-1 as facets have already gotten a global
                # orientation in DOLFINx
                t = get_ffcx_table_values(
                    quadrature_rule.points,
                    cell,
                    integral_type,
                    element,
                    avg,
                    entity_type,
                    local_derivatives,
                    flat_component,
                    codim,
                )
            elif tdim == 2:
                new_table = []
                for ref in range(2):
                    new_table.append(
                        get_ffcx_table_values(
                            permute_quadrature_interval(quadrature_rule.points, ref),
                            cell,
                            integral_type,
                            element,
                            avg,
                            entity_type,
                            local_derivatives,
                            flat_component,
                            codim,
                        )
                    )

                t = new_table[0]
                t["array"] = np.vstack([td["array"] for td in new_table])
            elif tdim == 3:
                cell_type = cell.cellname()
                if cell_type == "tetrahedron":
                    new_table = []
                    for rot in range(3):
                        for ref in range(2):
                            new_table.append(
                                get_ffcx_table_values(
                                    permute_quadrature_triangle(quadrature_rule.points, ref, rot),
                                    cell,
                                    integral_type,
                                    element,
                                    avg,
                                    entity_type,
                                    local_derivatives,
                                    flat_component,
                                    codim,
                                )
                            )
                    t = new_table[0]
                    t["array"] = np.vstack([td["array"] for td in new_table])
                elif cell_type == "hexahedron":
                    new_table = []
                    for rot in range(4):
                        for ref in range(2):
                            new_table.append(
                                get_ffcx_table_values(
                                    permute_quadrature_quadrilateral(
                                        quadrature_rule.points, ref, rot
                                    ),
                                    cell,
                                    integral_type,
                                    element,
                                    avg,
                                    entity_type,
                                    local_derivatives,
                                    flat_component,
                                    codim,
                                )
                            )
                    t = new_table[0]
                    t["array"] = np.vstack([td["array"] for td in new_table])
        else:
            t = get_ffcx_table_values(
                quadrature_rule.points,
                cell,
                integral_type,
                element,
                avg,
                entity_type,
                local_derivatives,
                flat_component,
                codim,
            )
        # Clean up table
        tbl = clamp_table_small_numbers(t["array"], rtol=rtol, atol=atol)
        tabletype = analyse_table_type(tbl)

        if tabletype in piecewise_ttypes:
            # Reduce table to dimension 1 along num_points axis in generated code
            tbl = tbl[:, :, :1, :]
        if tabletype in uniform_ttypes:
            # Reduce table to dimension 1 along num_entities axis in generated code
            tbl = tbl[:, :1, :, :]
        is_permuted = is_permuted_table(tbl)
        if not is_permuted:
            # Reduce table along num_perms axis
            tbl = tbl[:1, :, :, :]

        # Check for existing identical table
        is_new_table = True
        for table_name in _existing_tables:
            if equal_tables(tbl, _existing_tables[table_name]):
                name = table_name
                tbl = _existing_tables[name]
                is_new_table = False
                break

        if is_new_table:
            _existing_tables[name] = tbl

        cell_offset = 0

        if use_sum_factorization and (not quadrature_rule.has_tensor_factors):
            raise RuntimeError("Sum factorization not available for this quadrature rule.")

        tensor_factors: typing.Optional[list[UniqueTableReferenceT]] = None
        tensor_perm = None
        if (
            use_sum_factorization
            and element.has_tensor_product_factorisation
            and len(element.get_tensor_product_representation()) == 1
            and quadrature_rule.has_tensor_factors
        ):
            factors = element.get_tensor_product_representation()

            tensor_factors = []
            for i, j in enumerate(factors[0]):
                pts = quadrature_rule.tensor_factors[i][0]
                d = local_derivatives[i]
                sub_tbl = j.tabulate(d, pts)[d]
                sub_tbl = sub_tbl.reshape(1, 1, sub_tbl.shape[0], sub_tbl.shape[1])
                for tensor_factor in all_tensor_factors:
                    if tensor_factor.values.shape == sub_tbl.shape and np.allclose(
                        tensor_factor.values, sub_tbl
                    ):
                        tensor_factors.append(tensor_factor)
                        break
                else:
                    ut = UniqueTableReferenceT(
                        f"FE_TF{tensor_n}",
                        sub_tbl,
                        None,
                        None,
                        None,
                        False,
                        False,
                        False,
                        False,
                        None,
                        None,
                    )
                    all_tensor_factors.append(ut)
                    tensor_factors.append(ut)
                    mt_tables[ut.name] = ut
                    tensor_n += 1

            tensor_perm = factors[0][1]

        if mt.restriction == "-" and isinstance(mt.terminal, ufl.classes.FormArgument):
            # offset = 0 or number of element dofs, if restricted to "-"
            cell_offset = element.dim

        offset = cell_offset + t["offset"]
        block_size = t["stride"]

        # tables is just np.arrays, mt_tables hold metadata too
        mt_tables[mt] = UniqueTableReferenceT(
            name,
            tbl,
            offset,
            block_size,
            tabletype,
            tabletype in piecewise_ttypes,
            tabletype in uniform_ttypes,
            is_permuted,
            tensor_factors is not None,
            tensor_factors,
            tensor_perm,
        )

    return mt_tables


def is_zeros_table(table, rtol=default_rtol, atol=default_atol):
    """Check if table values are all zero."""
    return np.prod(table.shape) == 0 or np.allclose(
        table, np.zeros(table.shape), rtol=rtol, atol=atol
    )


def is_ones_table(table, rtol=default_rtol, atol=default_atol):
    """Check if table values are all one."""
    return np.allclose(table, np.ones(table.shape), rtol=rtol, atol=atol)


def is_quadrature_table(table, rtol=default_rtol, atol=default_atol):
    """Check if table is a quadrature table."""
    _, num_entities, num_points, num_dofs = table.shape
    Id = np.eye(num_points)
    return num_points == num_dofs and all(
        np.allclose(table[0, i, :, :], Id, rtol=rtol, atol=atol) for i in range(num_entities)
    )


def is_permuted_table(table, rtol=default_rtol, atol=default_atol):
    """Check if table is permuted."""
    return not all(
        np.allclose(table[0, :, :, :], table[i, :, :, :], rtol=rtol, atol=atol)
        for i in range(1, table.shape[0])
    )


def is_piecewise_table(table, rtol=default_rtol, atol=default_atol):
    """Check if table is piecewise."""
    return all(
        np.allclose(table[0, :, 0, :], table[0, :, i, :], rtol=rtol, atol=atol)
        for i in range(1, table.shape[2])
    )


def is_uniform_table(table, rtol=default_rtol, atol=default_atol):
    """Check if table is uniform."""
    return all(
        np.allclose(table[0, 0, :, :], table[0, i, :, :], rtol=rtol, atol=atol)
        for i in range(1, table.shape[1])
    )


def analyse_table_type(table, rtol=default_rtol, atol=default_atol):
    """Analyse table type."""
    if is_zeros_table(table, rtol=rtol, atol=atol):
        # Table is empty or all values are 0.0
        ttype = "zeros"
    elif is_ones_table(table, rtol=rtol, atol=atol):
        # All values are 1.0
        ttype = "ones"
    elif is_quadrature_table(table, rtol=rtol, atol=atol):
        # Identity matrix mapping points to dofs (separately on each entity)
        ttype = "quadrature"
    else:
        # Equal for all points on a given entity
        piecewise = is_piecewise_table(table, rtol=rtol, atol=atol)
        uniform = is_uniform_table(table, rtol=rtol, atol=atol)

        if piecewise and uniform:
            # Constant for all points and all entities
            ttype = "fixed"
        elif piecewise:
            # Constant for all points on each entity separately
            ttype = "piecewise"
        elif uniform:
            # Equal on all entities
            ttype = "uniform"
        else:
            # Varying over points and entities
            ttype = "varying"
    return ttype
