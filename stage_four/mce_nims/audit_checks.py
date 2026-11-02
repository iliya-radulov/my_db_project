"""
audit_checks.py

The data checks behind the decisions in WORKLOG.md, as one script, so
every number quoted there can be reproduced:

  1. what the file contains (rows, papers, families, interstitials)
  2. which of the hand-extracted Stage 4 literature records are already
     in NIMS (by DOI) -- those cannot serve as an independent test set
  3. the Ni and Cr test series as stored in NIMS, against the original
     values from the TU Darmstadt stay reports (read with
     origin_from_pptx.py) and against the earlier power-law estimates
  4. how many unhydrided high-Mn samples (x > ~0.5) NIMS has

Usage:  python audit_checks.py [--data path/to/1-13_dataset.xlsx]
"""
import argparse

import pandas as pd

from nims_dataset import DEFAULT_PATH, load_nims, restore_T_tr

# Papers behind the 34 hand-extracted records (data_extraction_notes.md).
EXTRACTION_SOURCES = {
    'Moreno-Ramírez 2019, Cr (7 records)': '10.1016/j.actamat.2019.06.022',
    'Moreno-Ramírez 2018, Ni (5 records)': '10.1016/j.actamat.2018.08.054',
    'Krautz 2014, Mn (10 records)': '10.1016/j.jallcom.2014.02.015',
    'Gottschall 2019, materials library (2 records)': '10.1002/aenm.201901322',
}

# Original values from the stay reports (Origin graphs, read with origin_from_pptx.py):
# Ni: first stay, slides 17 (T_tr), 19 (|ΔS| at 1.9 T); Cr: second stay, slide 21
# (peak of each ΔS(T) curve at 1.9 T). Earlier estimates: data_extraction_notes.md.
NI_ORIGINAL = {'x': [0.0, 0.1, 0.2, 0.3, 0.4],
               'T_tr': [193.94, 193.77, 197.27, 204.49, 214.25],
               'dS': [19.8, 18.98, 12.08, 8.48, 4.3]}
NI_ESTIMATED = {'T_tr': [193, 201, 210, 224, 251], 'dS': [22.1, 16.3, 15.1, 14.4, 13.7]}
CR_ORIGINAL_DS_PEAKS = [22.43, 21.52, 21.18, 17.32, 14.97, 11.53, 6.65]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=str(DEFAULT_PATH))
    args = ap.parse_args()
    pd.set_option('display.width', 200)

    df = restore_T_tr(load_nims(args.data))
    doi = df['doi'].str.lower()

    print("1. Contents")
    print(f"   {len(df)} samples, {doi.nunique()} papers (by DOI), "
          f"{int(df['composition_text'].notna().sum())} with a formula string, "
          f"{int(df['has_interstitial'].sum())} with H/C/N/B")
    print(f"   T_tr: {df['T_tr_source'].value_counts().to_dict()}")
    print(f"   largest families: {df['family'].value_counts().head(8).to_dict()}")

    print("\n2. Hand-extracted sources already in NIMS")
    for label, d in EXTRACTION_SOURCES.items():
        print(f"   {label:52s} {int(doi.str.contains(d, regex=False).sum()):3d} NIMS rows")

    print("\n3. Test series: NIMS vs original values vs earlier estimates")
    ni = df[doi.str.contains('10.1016/j.actamat.2018.08.054', regex=False)]
    ni_ds = [v[0] if v else None for v in ni['dS_max']]
    print(pd.DataFrame({'x (nominal)': NI_ORIGINAL['x'],
                        'T_tr NIMS': ni['T_tr_K'].to_list(), 'T_tr original': NI_ORIGINAL['T_tr'],
                        'T_tr estimated': NI_ESTIMATED['T_tr'],
                        'dS NIMS': ni_ds, 'dS original': NI_ORIGINAL['dS'],
                        'dS estimated': NI_ESTIMATED['dS']}).to_string(index=False))
    cr = df[doi.str.contains('10.1016/j.actamat.2019.06.022', regex=False)]
    print(pd.DataFrame({'x (measured)': cr['composition_details'].str.replace('x = ', '').to_list(),
                        'dS NIMS': [v[0] if v else None for v in cr['dS_max']],
                        'dS original (curve peaks, sorted)': sorted(CR_ORIGINAL_DS_PEAKS, reverse=True),
                        'anneal T NIMS (K)': cr['anneal_temp_K'].to_list()}).to_string(index=False))

    print("\n4. Unhydrided high-Mn samples in NIMS (Mn > 3.5 at.%, i.e. x > ~0.5)")
    hm = df[(df['Mn'] > 3.5) & (df['H'] == 0)]
    print(f"   {len(hm)} rows: " + ', '.join(f"ID {i} (x = {r.Mn / 100 * 14:.2f}, {r.doi})" for i, r in hm.iterrows()))


if __name__ == '__main__':
    main()
