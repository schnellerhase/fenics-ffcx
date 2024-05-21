/// This is UFCx
/// This software is released under the terms of the unlicense (see the file
/// UNLICENSE).
///
/// The FEniCS Project (http://www.fenicsproject.org/) 2006-2021.
///
/// UFCx defines the interface between code generated by FFCx and the
/// DOLFINx C++ library. Changes here must be reflected both in the FFCx
/// code generation and in the DOLFINx library calls.

#pragma once

#define UFCX_VERSION_MAJOR 0
#define UFCX_VERSION_MINOR 9
#define UFCX_VERSION_MAINTENANCE 0
#define UFCX_VERSION_RELEASE 0

#if UFCX_VERSION_RELEASE
#define UFCX_VERSION                                                            \
  UFCX_VERSION_MAJOR "." UFCX_VERSION_MINOR "." UFCX_VERSION_MAINTENANCE
#else
#define UFCX_VERSION                                                            \
  UFCX_VERSION_MAJOR "." UFCX_VERSION_MINOR "." UFCX_VERSION_MAINTENANCE ".dev0"
#endif

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C"
{

#if defined(__clang__)
#define restrict
#elif defined(__GNUC__) || defined(__GNUG__)
#define restrict __restrict__
#else
#define restrict
#endif // restrict
#endif // __cplusplus

  // <HEADER_DECL>

  typedef enum
  {
    cell = 0,
    exterior_facet = 1,
    interior_facet = 2
  } ufcx_integral_type;

  // </HEADER_DECL>

  /// Tabulate integral into tensor A with compiled quadrature rule
  ///
  /// @param[out] A
  /// @param[in] w Coefficients attached to the form to which the
  /// tabulated integral belongs.
  ///
  /// Dimensions: w[coefficient][restriction][dof].
  ///
  /// Restriction dimension
  /// applies to interior facet integrals, where coefficients restricted
  /// to both cells sharing the facet must be provided.
  /// @param[in] c Constants attached to the form to which the tabulated
  /// integral belongs. Dimensions: c[constant][dim].
  /// @param[in] coordinate_dofs Values of degrees of freedom of
  /// coordinate element. Defines the geometry of the cell. Dimensions:
  /// coordinate_dofs[restriction][num_dofs][3]. Restriction
  /// dimension applies to interior facet integrals, where cell
  /// geometries for both cells sharing the facet must be provided.
  /// @param[in] entity_local_index Local index of mesh entity on which
  /// to tabulate. This applies to facet integrals.
  /// @param[in] quadrature_permutation For facet integrals, numbers to
  /// indicate the permutation to be applied to each side of the facet
  /// to make the orientations of the faces matched up should be passed
  /// in. If an integer of value N is passed in, then:
  ///
  ///  - floor(N / 2) gives the number of rotations to apply to the
  ///  facet
  ///  - N % 2 gives the number of reflections to apply to the facet
  ///
  /// For integrals not on interior facets, this argument has no effect and a
  /// null pointer can be passed. For interior facets the array will have size 2
  /// (one permutation for each cell adjacent to the facet).
  typedef void(ufcx_tabulate_tensor_float32)(
      float* restrict A, const float* restrict w,
      const float* restrict c, const float* restrict coordinate_dofs,
      const int* restrict entity_local_index,
      const uint8_t* restrict quadrature_permutation);

  /// Tabulate integral into tensor A with compiled
  /// quadrature rule and double precision
  ///
  /// @see ufcx_tabulate_tensor_single
  typedef void(ufcx_tabulate_tensor_float64)(
      double* restrict A, const double* restrict w,
      const double* restrict c, const double* restrict coordinate_dofs,
      const int* restrict entity_local_index,
      const uint8_t* restrict quadrature_permutation);

  /// Tabulate integral into tensor A with compiled
  /// quadrature rule and complex single precision
  ///
  /// @see ufcx_tabulate_tensor_single
  typedef void(ufcx_tabulate_tensor_complex64)(
      float _Complex* restrict A, const float _Complex* restrict w,
      const float _Complex* restrict c, const float* restrict coordinate_dofs,
      const int* restrict entity_local_index,
      const uint8_t* restrict quadrature_permutation);

  /// Tabulate integral into tensor A with compiled
  /// quadrature rule and complex double precision
  ///
  /// @see ufcx_tabulate_tensor_single
  typedef void(ufcx_tabulate_tensor_complex128)(
      double _Complex* restrict A, const double _Complex* restrict w,
      const double _Complex* restrict c, const double* restrict coordinate_dofs,
      const int* restrict entity_local_index,
      const uint8_t* restrict quadrature_permutation);

  typedef struct ufcx_integral
  {
    const bool* enabled_coefficients;
    ufcx_tabulate_tensor_float32* tabulate_tensor_float32;
    ufcx_tabulate_tensor_float64* tabulate_tensor_float64;
    ufcx_tabulate_tensor_complex64* tabulate_tensor_complex64;
    ufcx_tabulate_tensor_complex128* tabulate_tensor_complex128;
    bool needs_facet_permutations;

    /// Get the hash of the coordinate element associated with the geometry of the mesh.
    uint64_t coordinate_element_hash;
  } ufcx_integral;

  typedef struct ufcx_expression
  {
    /// Evaluate expression into tensor A with compiled evaluation points
    ///
    /// @param[out] A
    ///         Dimensions: A[num_points][num_components][num_argument_dofs]
    ///
    /// @see ufcx_tabulate_tensor
    ///
    ufcx_tabulate_tensor_float32* tabulate_tensor_float32;
    ufcx_tabulate_tensor_float64* tabulate_tensor_float64;
    ufcx_tabulate_tensor_complex64* tabulate_tensor_complex64;
    ufcx_tabulate_tensor_complex128* tabulate_tensor_complex128;

    /// Number of coefficients
    int num_coefficients;

    /// Number of constants
    int num_constants;

    /// Original coefficient position for each coefficient
    const int* original_coefficient_positions;

    /// List of names of coefficients
    const char** coefficient_names;

    /// List of names of constants
    const char** constant_names;

    /// Number of evaluation points
    int num_points;

    /// Dimension of evaluation point
    int entity_dimension;

    /// Coordinates of evaluations points. Dimensions:
    /// points[num_points][entity_dimension]
    const double* points;

    /// Shape of expression. Dimension: value_shape[num_components]
    const int* value_shape;

    /// Number of components of return_shape
    int num_components;

    /// Rank, i.e. number of arguments
    int rank;

  } ufcx_expression;

  /// This class defines the interface for the assembly of the global
  /// tensor corresponding to a form with r + n arguments, that is, a
  /// mapping
  ///
  ///     a : V1 x V2 x ... Vr x W1 x W2 x ... x Wn -> R
  ///
  /// with arguments v1, v2, ..., vr, w1, w2, ..., wn. The rank r
  /// global tensor A is defined by
  ///
  ///     A = a(V1, V2, ..., Vr, w1, w2, ..., wn),
  ///
  /// where each argument Vj represents the application to the
  /// sequence of basis functions of Vj and w1, w2, ..., wn are given
  /// fixed functions (coefficients).
  typedef struct ufcx_form
  {
    /// String identifying the form
    const char* signature;

    /// Rank of the global tensor (r)
    int rank;

    /// Number of coefficients (n)
    int num_coefficients;

    /// Number of constants
    int num_constants;

    /// Original coefficient position for each coefficient
    int* original_coefficient_positions;

    /// List of names of coefficients
    const char** coefficient_name_map;

    /// List of names of constants
    const char** constant_name_map;

    /// Get the hash of the finite element for the i-th argument function, where 0 <=
    /// i < r + n.
    ///
    /// @param i Argument number if 0 <= i < r Coefficient number j = i
    /// - r if r + j <= i < r + n
    uint64_t* finite_element_hashes;

    /// List of cell, interior facet and exterior facet integrals
    ufcx_integral** form_integrals;

    /// IDs for each integral in form_integrals list
    int* form_integral_ids;

    /// Offsets for cell, interior facet and exterior facet integrals in form_integrals list
    int* form_integral_offsets;

  } ufcx_form;

#ifdef __cplusplus
#undef restrict
}
#endif
