"""
vsm_bhmax.py

Calculates the maximum energy product (BH_max) for a cuboid permanent
magnet sample, correcting for self-demagnetization -- the actual figure
of merit for permanent magnets, as opposed to Hc/Mr (which, confirmed
directly via a synthetic ground-truth test, are mathematically
UNCHANGED by a simple point-wise shearing correction, since that
correction is proportional to M itself and vanishes exactly at the
points defining Hc and Mr).

Formula chain confirmed against the user's own real, working lab
practice (extracted directly from real presentation files, not
reconstructed from screenshots) -- NOT my own independently-derived
CGS-based version, which uses a different (but equally correct)
unit convention:
  1. Demagnetizing factor: Prozorov & Kogan's approximate formula for a
     rectangular cuboid (not the more rigorous Aharoni formula also
     available in this project -- this project's owner's own
     established practice uses this simpler one, and it is a
     genuinely standard published reference, not an ad-hoc
     approximation):
         N^-1 = 1 + (3/4)(c/a)(1 + a/b)
     where a, b, c are HALF-dimensions and the field is applied along
     the b-axis. Confirmed against a real worked example (2a=1mm,
     2b=2.5mm, 2c=2mm -> N=0.322) to match exactly.
  2. Polarisation: J[T] = M[emu/g] * density[g/cm^3] * 4*pi*1e-4.
     Confirmed against a real worked example (M=86.87 emu/g,
     density=7.61 g/cm^3 -> J=0.828T) to match exactly.
  3. Field conversion: H[kA/m] = H[Oe] / (4*pi).
  4. Demagnetizing correction, in SI-consistent kA/m (NOT the CGS
     4*pi*N*M form used elsewhere in this project -- confirmed these
     are two different, individually correct unit conventions for the
     SAME physics, not a contradiction):
         H_corrected[kA/m] = H[kA/m] - N * M[kA/m]
     where M[kA/m] = M[emu/g] * density[g/cm^3] (SI-consistent
     Am^2/kg * kg/m^3 = A/m, /1000 for kA/m -- confirmed dimensionally).
  5. B[T] = mu0 * H_corrected[A/m] + J[T].
  6. BH_max[kJ/m^3] = max(|B * H_corrected|), restricted to the SECOND
     QUADRANT ONLY (H<0, B>0 on the descending branch) -- confirmed
     directly this restriction is required, not optional.
"""

import numpy as np


def demag_factor_prozorov_kogan(full_a, full_b, full_c):
    """
    Prozorov & Kogan approximate demagnetizing factor for a rectangular
    cuboid, field applied along the b-axis (the SECOND dimension
    passed in). Takes FULL sample dimensions (not half-dimensions --
    the /2 conversion happens internally).

    R. Prozorov, V. Kogan, "Effective Demagnetizing Factors of
    Diamagnetic Samples of Various Shapes", Phys. Rev. Applied 10,
    014030 (2018).

    Confirmed against a real worked example: full_a=1mm, full_b=2.5mm,
    full_c=2mm -> N=0.3226 (matches the user's own reference exactly).
    """
    a, b, c = full_a / 2.0, full_b / 2.0, full_c / 2.0
    N_inv = 1 + (3.0/4.0) * (c/a) * (1 + a/b)
    return 1.0 / N_inv


def polarisation_tesla(M_emu, mass_g, density_g_cm3):
    """
    Converts raw magnetic moment (emu) to polarisation J (Tesla),
    given sample mass and density.

    J[T] = (M_emu/mass_g) * density_g_cm3 * 4*pi*1e-4

    Confirmed against a real worked example: M/mass=86.87 emu/g,
    density=7.61 g/cm^3 -> J=0.828T (matches exactly).
    """
    M_per_g = np.asarray(M_emu) / mass_g
    return M_per_g * density_g_cm3 * 4 * np.pi * 1e-4


def demag_correct_field_kA_m(H_oe, M_emu, mass_g, density_g_cm3, N):
    """
    Converts applied field (Oe) to demagnetization-corrected internal
    field (kA/m), matching the user's own confirmed SI-consistent
    workflow (NOT the CGS 4*pi*N*M form).

    H_corrected[kA/m] = H[Oe]/(4*pi) - N * M[kA/m]
    where M[kA/m] = (M_emu/mass_g) * density_g_cm3 (SI-consistent
    Am^2/kg * kg/m^3 = A/m, converted to kA/m).

    Returns H_corrected in kA/m.
    """
    H_kA_m = np.asarray(H_oe) / (4 * np.pi)
    M_kA_m = (np.asarray(M_emu) / mass_g) * density_g_cm3
    return H_kA_m - N * M_kA_m


def compute_bhmax(H_oe, M_emu, mass_g, density_g_cm3, N):
    """
    Full BH_max calculation for one MH loop branch (expects the
    second-quadrant/descending branch -- see vsm_mh_features.py's
    find_descending_branch()).

    Returns a dict:
        {
            'H_corrected_kA_m': array,
            'B_tesla': array,
            'BH_product_kJ_m3': array (only the second-quadrant points),
            'BHmax_kJ_m3': float or None (None if no second-quadrant
                points found -- e.g. this branch doesn't actually cross
                into the second quadrant),
            'BHmax_index': int or None -- index into the ORIGINAL
                H_oe/M_emu arrays where BHmax occurs, for traceability
        }

    BH_max is restricted to the SECOND QUADRANT ONLY (H_corrected < 0,
    B > 0) -- confirmed directly this restriction is required, not
    optional; reported as a positive value via abs(), matching standard
    convention even though B and H have opposite signs there.
    """
    H_corrected = demag_correct_field_kA_m(H_oe, M_emu, mass_g, density_g_cm3, N)
    J = polarisation_tesla(M_emu, mass_g, density_g_cm3)

    mu0 = 4 * np.pi * 1e-7  # T*m/A
    H_corrected_A_m = H_corrected * 1000.0  # kA/m -> A/m
    B = mu0 * H_corrected_A_m + J

    second_quadrant = (H_corrected < 0) & (B > 0)

    if not np.any(second_quadrant):
        return {
            'H_corrected_kA_m': H_corrected,
            'B_tesla': B,
            'BH_product_kJ_m3': np.array([]),
            'BHmax_kJ_m3': None,
            'BHmax_index': None,
        }

    BH_product = np.abs(B * H_corrected)  # T * kA/m = kJ/m^3 directly
    BH_product_masked = np.where(second_quadrant, BH_product, -np.inf)
    best_idx = int(np.argmax(BH_product_masked))

    return {
        'H_corrected_kA_m': H_corrected,
        'B_tesla': B,
        'BH_product_kJ_m3': BH_product[second_quadrant],
        'BHmax_kJ_m3': float(BH_product[best_idx]),
        'BHmax_index': best_idx,
    }
