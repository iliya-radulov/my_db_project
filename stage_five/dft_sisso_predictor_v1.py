'''
Queries Materials Project for the target composition (or polymorphs/subsystems),
wraps the ComputedStructureEntry objects in 
`pymatgen.entries.computed_entries.GibbsComputedStructureEntry`, 
and evaluates \(\Delta G_f(T)\) across your temperature grid:
'''

from mp_api.client import MPRester
from pymatgen.entries.computed_entries import GibbsComputedStructureEntry
from pymatgen.core import Composition

EV_TO_KJ_MOL = 96.48533212331002

def get_sisso_gibbs_curve(formula: str, temperatures: list[float], api_key: str) -> list[dict]:
    """
    Fetch MP entries matching `formula` and compute finite-T formation Gibbs energy
    (kJ/mol-atom) via Bartel et al. (2018) SISSO descriptor in pymatgen.
    """
    comp = Composition(formula)
    elements = [str(el) for el in comp.elements]
    
    with MPRester(api_key) as mpr:
        # Fetch ComputedStructureEntries for the chemical system (needed for elemental refs)
        entries = mpr.get_entries_in_chemsys(elements, additional_criteria={"thermo_types": ["GGA_GGA+U"]})
    
    # Filter to exact reduced formula matches
    target_entries = [e for e in entries if e.composition.reduced_composition == comp.reduced_composition]
    if not target_entries:
        return []

    results = []
    for entry in target_entries:
        curve = {}
        for T in temperatures:
            # GibbsComputedStructureEntry requires 300 <= T <= 2000 K
            if not (300 <= T <= 2000):
                curve[T] = None
                continue
            g_entry = GibbsComputedStructureEntry.from_entries(entries, T)[entries.index(entry)]
            # Formation energy per atom in kJ/mol-atom
            e_form_ev = g_entry.formation_energy_per_atom
            curve[T] = round(e_form_ev * EV_TO_KJ_MOL, 4)
        results.append({
            "material_id": str(entry.entry_id),
            "formula": entry.composition.reduced_formula,
            "energy_above_hull_0K_eV": round(getattr(entry, "e_above_hull", float("nan")), 4),
            "dGf_sisso_kJ_mol_atom": curve,
        })
    return results
