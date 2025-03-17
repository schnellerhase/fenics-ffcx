# Copyright (C) 2021 Matthew Scroggs
#
# This file is part of FFCx.(https://www.fenicsproject.org)
#
# SPDX-License-Identifier:    LGPL-3.0-or-later
"""Geometry."""

import basix
import numpy as np

import ffcx.codegeneration.lnodes as L


def write_table(tablename, cellname):
    """Write a table."""
    if tablename == "facet_edge_vertices":
        return facet_edge_vertices(tablename, cellname)
    if tablename == "cell_facet_jacobian":
        return cell_facet_jacobian(tablename, cellname)
    if tablename == "reference_cell_volume":
        return reference_cell_volume(tablename, cellname)
    if tablename == "reference_facet_volume":
        return reference_facet_volume(tablename, cellname)
    if tablename == "reference_cell_edge_vectors":
        return reference_cell_edge_vectors(tablename, cellname)
    if tablename == "reference_facet_edge_vectors":
        return reference_facet_edge_vectors(tablename, cellname)
    if tablename == "reference_normals":
        return reference_normals(tablename, cellname)
    if tablename == "facet_orientation":
        return facet_orientation(tablename, cellname)
    raise ValueError(f"Unknown geometry table name: {tablename}")


def facet_edge_vertices(tablename, cellname):
    """Write facet edge vertices."""
    celltype = getattr(basix.CellType, cellname)
    topology = basix.topology(celltype)
    triangle_edges = basix.topology(basix.CellType.triangle)[1]
    quadrilateral_edges = basix.topology(basix.CellType.quadrilateral)[1]

    if len(topology) != 4:
        raise ValueError("Can only get facet edges for 3D cells.")

    edge_vertices = []
    for facet in topology[-2]:
        if len(facet) == 3:
            edge_vertices += [[[facet[i] for i in edge] for edge in triangle_edges]]
        elif len(facet) == 4:
            edge_vertices += [[[facet[i] for i in edge] for edge in quadrilateral_edges]]
        else:
            raise ValueError("Only triangular and quadrilateral faces supported.")

    out = np.array(edge_vertices, dtype=int)
    symbol = L.Symbol(f"{cellname}_{tablename}", dtype=L.DataType.INT)
    return L.ArrayDecl(symbol, values=out, const=True)


def cell_facet_jacobian(tablename, cellname):
    """Write a reference facet jacobian."""
    celltype = getattr(basix.CellType, cellname)
    out = basix.cell.facet_jacobians(celltype)
    symbol = L.Symbol(f"{cellname}_{tablename}", dtype=L.DataType.REAL)
    return L.ArrayDecl(symbol, values=out, const=True)


def reference_cell_volume(tablename, cellname):
    """Write a reference cell volume."""
    celltype = getattr(basix.CellType, cellname)
    out = basix.cell.volume(celltype)
    symbol = L.Symbol(f"{cellname}_{tablename}", dtype=L.DataType.REAL)
    return L.VariableDecl(symbol, out)


def reference_facet_volume(tablename, cellname):
    """Write a reference facet volume."""
    celltype = getattr(basix.CellType, cellname)
    volumes = basix.cell.facet_reference_volumes(celltype)
    for i in volumes[1:]:  # type: ignore
        if not np.isclose(i, volumes[0]):  # type: ignore
            raise ValueError("Reference facet volume not supported for this cell type.")
    symbol = L.Symbol(f"{cellname}_{tablename}", dtype=L.DataType.REAL)
    return L.VariableDecl(symbol, volumes[0])  # type: ignore


def reference_cell_edge_vectors(tablename, cellname):
    """Write reference edge vectors."""
    celltype = getattr(basix.CellType, cellname)
    topology = basix.topology(celltype)
    geometry = basix.geometry(celltype)
    edge_vectors = [geometry[j] - geometry[i] for i, j in topology[1]]  # type: ignore
    out = np.array(edge_vectors)
    symbol = L.Symbol(f"{cellname}_{tablename}", dtype=L.DataType.REAL)
    return L.ArrayDecl(symbol, values=out, const=True)


def reference_facet_edge_vectors(tablename, cellname):
    """Write facet reference edge vectors."""
    celltype = getattr(basix.CellType, cellname)
    topology = basix.topology(celltype)
    geometry = basix.geometry(celltype)
    triangle_edges = basix.topology(basix.CellType.triangle)[1]
    quadrilateral_edges = basix.topology(basix.CellType.quadrilateral)[1]

    if len(topology) != 4:
        raise ValueError("Can only get facet edges for 3D cells.")

    edge_vectors = []
    for facet in topology[-2]:
        if len(facet) == 3:
            edge_vectors += [geometry[facet[j]] - geometry[facet[i]] for i, j in triangle_edges]  # type: ignore
        elif len(facet) == 4:
            edge_vectors += [
                geometry[facet[j]] - geometry[facet[i]]
                for i, j in quadrilateral_edges  # type: ignore
            ]
        else:
            raise ValueError("Only triangular and quadrilateral faces supported.")

    out = np.array(edge_vectors)
    symbol = L.Symbol(f"{cellname}_{tablename}", dtype=L.DataType.REAL)
    return L.ArrayDecl(symbol, values=out, const=True)


def reference_normals(tablename, cellname):
    """Write reference facet normals."""
    celltype = getattr(basix.CellType, cellname)
    out = basix.cell.facet_outward_normals(celltype)
    symbol = L.Symbol(f"{cellname}_{tablename}", dtype=L.DataType.REAL)
    return L.ArrayDecl(symbol, values=out, const=True)


def facet_orientation(tablename, cellname):
    """Write facet orientations."""
    celltype = getattr(basix.CellType, cellname)
    out = basix.cell.facet_orientations(celltype)
    symbol = L.Symbol(f"{cellname}_{tablename}", dtype=L.DataType.REAL)
    return L.ArrayDecl(symbol, values=np.asarray(out), const=True)
