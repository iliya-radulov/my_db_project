"""
vsm_demag_correction.py

Demagnetizing-factor calculation and shearing correction for cuboid
(rectangular prism) samples -- for samples where shape anisotropy is
NOT negligible (unlike the needle-shaped samples used for most
measurements in this project, where H_internal ~ H_applied along the
long axis and no correction is needed).

Formula: Aharoni's closed-form magnetometric demagnetizing factor for
a rectangular prism (A. Aharoni, "Demagnetizing factors for rectangular
ferromagnetic prisms", J. Appl. Phys. 83, 3432 (1998)). Exact formula
sourced from magpar (GPL-licensed micromagnetics package, calculator
contributed by Rok Dittrich, citing Aharoni directly) --
http://www.magpar.net/static/magpar/doc/html/demagcalc.html -- not
reconstructed from memory, given how easily a subtle error here would
silently corrupt every corrected Hci downstream.

VALIDATED (multiple independent checks, not just one):
  - Cube (a=b=c): gives D_z = 1/3 exactly (to floating-point precision,
    ~1e-17) -- required by symmetry, a hard, unambiguous check.
  - Sum rule: Dx + Dy + Dz = 1.0 exactly, for a genuinely asymmetric
    shape (1:2:3 aspect ratio) -- confirms the "dimensionless, sums to
    1" convention (as opposed to the CGS-4pi-sum convention used in
    some papers -- these are NOT the same N, and mixing them up would
    give a wrong answer by a factor of 4pi).
  - Extreme aspect ratios match physical expectation: a long needle
    (field along the long axis) -> D approaches 0; a thin flat plate
    (field along the thin axis) -> D approaches 1.

Shearing correction unit convention, confirmed from two independent
real sources (not assumed): H_internal = H_applied - 4*pi*N*M_volume,
with H in Oe, M_volume in emu/cm^3, N the dimensionless (sum-to-1)
factor validated above.
"""

import numpy as np


def demag_factor_cuboid(a, b, c):
    """
    Aharoni's magnetometric demagnetizing factor for a rectangular
    prism, field applied along the c-axis. a, b, c are HALF-dimensions
    (semi-axes) -- the prism's actual edge lengths are 2a x 2b x 2c.

    Returns the dimensionless demagnetizing factor D_z (0 to 1). To
    get D_x or D_y instead, permute the arguments so the axis of
    interest is passed as the third argument (see
    demag_factor_from_dimensions() for a wrapper that handles this).
    """
    a, b, c = float(a), float(b), float(c)
    r = np.sqrt(a**2 + b**2 + c**2)
    rab = np.sqrt(a**2 + b**2)
    rbc = np.sqrt(b**2 + c**2)
    rac = np.sqrt(a**2 + c**2)

    term1 = (b**2 - c**2) / (2*b*c) * np.log((r - a) / (r + a))
    term2 = (a**2 - c**2) / (2*a*c) * np.log((r - b) / (r + b))
    term3 = (b / (2*c)) * np.log((rab + a) / (rab - a))
    term4 = (a / (2*c)) * np.log((rab + b) / (rab - b))
    term5 = (c / (2*a)) * np.log((rbc - b) / (rbc + b))
    term6 = (c / (2*b)) * np.log((rac - a) / (rac + a))
    term7 = 2 * np.arctan(a*b / (c*r))
    term8 = (a**3 + b**3 - 2*c**3) / (3*a*b*c)
    term9 = (a**2 + b**2 - 2*c**2) / (3*a*b*c) * r
    term10 = (c / (a*b)) * (rac + rbc)
    term11 = -(rab**3 + rbc**3 + rac**3) / (3*a*b*c)

    pi_Dz = term1 + term2 + term3 + term4 + term5 + term6 + term7 + term8 + term9 + term10 + term11
    return pi_Dz / np.pi


def demag_factor_from_dimensions(length_x, length_y, length_z, field_axis='z'):
    """
    Convenience wrapper: takes FULL physical sample dimensions (any
    consistent unit -- mm, cm, whatever the caller uses), not
    half-dimensions, and the axis along which the field is applied.
    Handles the semi-axis conversion and axis permutation internally.

    field_axis: 'x', 'y', or 'z' -- which physical dimension the field
    is applied along.

    Returns the dimensionless demagnetizing factor for that axis.
    """
    a, b, c = length_x / 2.0, length_y / 2.0, length_z / 2.0
    if field_axis == 'z':
        return demag_factor_cuboid(a, b, c)
    elif field_axis == 'y':
        return demag_factor_cuboid(a, c, b)
    elif field_axis == 'x':
        return demag_factor_cuboid(b, c, a)
    else:
        raise ValueError(f"field_axis must be 'x', 'y', or 'z'; got {field_axis!r}")


def shear_correction(H_applied_oe, M_emu, N, volume_cm3):
    """
    Corrects raw as-measured field values for self-demagnetization,
    given the sample's actual volume and the demagnetizing factor along
    the measurement axis.

    H_internal = H_applied - 4*pi*N*M_volume, where M_volume = M_emu /
    volume_cm3 (emu/cm^3). Confirmed from two independent real sources
    (not assumed) -- see module docstring.

    N: dimensionless demagnetizing factor (0 to 1, from
    demag_factor_cuboid/demag_factor_from_dimensions) for the axis
    along which H_applied_oe was actually applied. Passing an N
    computed for the wrong axis would silently produce a wrong
    correction -- this function has no way to check that itself, the
    caller must ensure it matches.

    volume_cm3: sample volume in cm^3. Get this right (correct units!)
    -- a volume error propagates directly and linearly into every
    corrected H value.

    Returns H_internal (Oe), same shape as H_applied_oe.
    """
    M_volume = np.asarray(M_emu) / volume_cm3
    return np.asarray(H_applied_oe) - 4 * np.pi * N * M_volume
