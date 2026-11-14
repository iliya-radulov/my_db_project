"""
niitsu2012.py

Loader, validators and ESPEI export for the data transcribed from
K. Niitsu, R. Kainuma, "Phase equilibria in the Fe-La-Si ternary system",
Intermetallics 20 (2012) 160-169, doi:10.1016/j.intermet.2011.06.005.

The CSVs in data_niitsu2012/ are transcribed AS PRINTED (from the PDF's
embedded text layer; ambiguous glyphs resolved from high-resolution crops
and documented in phase_registry.csv and WORKLOG.md). Nothing is corrected
silently: rows that fail a check are flagged and discussed in the worklog.

Validators (run with `python niitsu2012.py`):
  1. row counts per table equal the paper (T2: 29, T3: 29, T4: 9, T7: 4;
     DSC: 17 entries for 12 alloys);
  2. every composition in [0, 100] and La + Si <= 100;
  3. tau1/tau2 contain La = 7.14 +/- 0.6 at.% (1/14 of the 1:13 sites);
  4. DSC table: Si(at.%) = 100*13x/14 within 0.15 (x and Si printed
     independently in the paper);
  5. mass balance: the nominal composition lies on/in the measured
     two-phase segment or three-phase triangle (tolerance 2.0 at.%);
     failures are reported, not dropped;
  6. the tau1/tau2 x ranges spanned by the tie-line endpoints lie inside
     the ranges stated in the paper's text (+/- 0.02; the stated ranges
     also use phase-boundary extrapolations, so they may be wider).

Export: `python niitsu2012.py --espei` writes one ESPEI ZPF dataset per
temperature group into espei_datasets/ (phase names from
phase_registry.csv's espei_name column, placeholders until a TDB is
chosen; 'n.d.' phases excluded; mass-balance flags copied into the
dataset comment).
"""
import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data_niitsu2012'
EXPECTED_ROWS = {'2': 29, '3': 29, '4': 9, '7': 4}
EXPECTED_DSC = 17
TAU_LA = 100.0 / 14.0                 # La site fraction of La(Fe,Si)13
BALANCE_TOL = 2.0                     # at.%
REFERENCE = ('K. Niitsu, R. Kainuma, Intermetallics 20 (2012) 160-169, '
             'doi:10.1016/j.intermet.2011.06.005')


def read_csv(name):
    with open(DATA / name, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_tielines():
    """Rows with floats parsed; each row gets a 'phases' list of
    (label, La, Si) with La/Si None where not determined."""
    rows = read_csv('tielines.csv')
    for r in rows:
        for k in ('T_K', 'nominal_La', 'nominal_Si', 'anneal_days'):
            r[k] = float(r[k])
        r['phases'] = []
        for i in '123':
            label = r[f'phase{i}'].strip()
            if not label:
                continue
            la, si = r[f'La{i}'].strip(), r[f'Si{i}'].strip()
            r['phases'].append((label,
                                float(la) if la else None,
                                float(si) if si else None))
    return rows


def load_registry():
    return {r['label']: r for r in read_csv('phase_registry.csv')}


def x_site(la, si):
    """Si site fraction x in La(Fe1-xSix)13 from at.% (Si over Fe+Si)."""
    return si / (100.0 - la)


# ---------------------------------------------------------------------------
# geometry for the mass-balance check, in the (La, Si) at.% plane
# ---------------------------------------------------------------------------
def _dist_point_segment(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    vx, vy = bx - ax, by - ay
    denom = vx * vx + vy * vy
    t = 0.0 if denom == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / denom))
    dx, dy = px - (ax + t * vx), py - (ay + t * vy)
    return (dx * dx + dy * dy) ** 0.5


def _dist_point_triangle(p, a, b, c):
    def cross(o, u, v):
        return (u[0] - o[0]) * (v[1] - o[1]) - (u[1] - o[1]) * (v[0] - o[0])
    s1, s2, s3 = cross(a, b, p), cross(b, c, p), cross(c, a, p)
    if (s1 >= 0 and s2 >= 0 and s3 >= 0) or (s1 <= 0 and s2 <= 0 and s3 <= 0):
        return 0.0
    return min(_dist_point_segment(p, a, b), _dist_point_segment(p, b, c),
               _dist_point_segment(p, c, a))


def balance_distance(row):
    """Distance (at.%) from the nominal composition to the measured
    phase simplex; None where a phase composition is missing."""
    pts = [(la, si) for _, la, si in row['phases']]
    if any(v is None for pt in pts for v in pt):
        return None
    p = (row['nominal_La'], row['nominal_Si'])
    if len(pts) == 2:
        return _dist_point_segment(p, *pts)
    if len(pts) == 3:
        return _dist_point_triangle(p, *pts)
    return None


# ---------------------------------------------------------------------------
# validators
# ---------------------------------------------------------------------------
def validate(verbose=True):
    rows = load_tielines()
    dsc = read_csv('dsc_reactions.csv')
    registry = load_registry()
    facts = {r['fact']: r['value'] for r in read_csv('text_facts.csv')}
    problems, flagged = [], []

    counts = {}
    for r in rows:
        counts[r['table']] = counts.get(r['table'], 0) + 1
    for t, n in EXPECTED_ROWS.items():
        if counts.get(t) != n:
            problems.append(f'table {t}: {counts.get(t)} rows, expected {n}')
    if len(dsc) != EXPECTED_DSC:
        problems.append(f'DSC: {len(dsc)} entries, expected {EXPECTED_DSC}')

    for r in rows:
        where = f"T{r['table']} {r['nominal_La']:.1f}/{r['nominal_Si']:.1f}"
        for label, la, si in r['phases']:
            if label not in registry:
                problems.append(f'{where}: unknown phase label {label!r}')
            if la is None:
                continue
            if not (0 <= la <= 100 and 0 <= si <= 100 and la + si <= 100.0 + 1e-9):
                problems.append(f'{where}: impossible composition {label} {la}/{si}')
            if label in ('tau1', 'tau2') and abs(la - TAU_LA) > 0.6:
                problems.append(f'{where}: {label} La = {la} (expected ~{TAU_LA:.2f})')

    for r in dsc:
        si_from_x = 100.0 * 13.0 * float(r['x']) / 14.0
        if abs(si_from_x - float(r['Si_at_pct'])) > 0.15:
            problems.append(f"DSC x={r['x']}: Si {r['Si_at_pct']} but 13x/14 = {si_from_x:.2f}")

    for r in rows:
        d = balance_distance(r)
        if d is not None and d > BALANCE_TOL:
            flagged.append((f"T{r['table']} {r['nominal_La']:.1f}/{r['nominal_Si']:.1f} "
                            f"{'/'.join(p[0] for p in r['phases'])}", round(d, 1)))

    for tau in ('tau1', 'tau2'):
        for t_k, key in ((1173, '1173K'), (1373, '1373K'), (1573, '1573K')):
            stated = facts[f'{tau}_x_range_{key}']
            lo, hi = (float(v) for v in stated.split('-'))
            xs = [x_site(la, si) for r in rows if r['T_K'] == t_k
                  for label, la, si in r['phases'] if label == tau]
            if xs and not (lo - 0.02 <= min(xs) and max(xs) <= hi + 0.02):
                problems.append(f'{tau} at {t_k} K: tie-line x range '
                                f'{min(xs):.3f}-{max(xs):.3f} outside stated {stated}')

    if verbose:
        n_eq = sum(len(r['phases']) - (1 if r['phases'][-1][0] == 'n.d.' else 0) for r in rows)
        print(f"{len(rows)} tie-line rows ({n_eq} phase compositions), "
              f"{len(dsc)} DSC entries, {len(registry)} phase labels")
        print(f"hard checks: {'all passed' if not problems else f'{len(problems)} PROBLEMS'}")
        for p in problems:
            print('  PROBLEM:', p)
        print(f"mass balance (> {BALANCE_TOL} at.% off): {len(flagged)} rows flagged "
              '(transcribed as printed; see WORKLOG section 3)')
        for f_, d in flagged:
            print(f'  flagged: {f_}  ({d} at.% outside)')
    return problems, flagged


# ---------------------------------------------------------------------------
# ESPEI export
# ---------------------------------------------------------------------------
def export_espei(out_dir=HERE / 'espei_datasets'):
    rows = load_tielines()
    registry = load_registry()
    out_dir.mkdir(exist_ok=True)
    _, flagged = validate(verbose=False)
    flag_text = '; '.join(f for f, _ in flagged)
    groups = {'2': ('ZPF-1173K', [1173]), '3': ('ZPF-1373K', [1373]),
              '4': ('ZPF-1573K', [1573]), '7': ('ZPF-1273-1523K', None)}
    written = []
    for table, (tag, temps) in groups.items():
        sub = [r for r in rows if r['table'] == table]
        values, ts = [], []
        for r in sub:
            if any(label == 'n.d.' for label, _, _ in r['phases']):
                continue                       # phase not determined: no ZPF statement
            entry = []
            for label, la, si in r['phases']:
                name = registry[label]['espei_name']
                entry.append([name, ['LA', 'SI'], [round(la / 100, 4), round(si / 100, 4)]])
            values.append(entry)
            ts.append(r['T_K'])
        dataset = {
            'components': ['FE', 'LA', 'SI', 'VA'],
            'phases': sorted({e[0] for v in values for e in v}),
            'conditions': {'P': 101325,
                           'T': temps[0] if temps and len(set(ts)) == 1 else ts},
            'output': 'ZPF',
            'values': values,
            'reference': 'niitsu2012',
            'bibtex': REFERENCE,
            'comment': (f'Transcribed from Table {table}; phase names are placeholders '
                        'mapped in data_niitsu2012/phase_registry.csv. Equilibria whose '
                        f'nominal composition misses the measured simplex by >{BALANCE_TOL} '
                        f'at.% (kept as printed): {flag_text}'),
        }
        path = out_dir / f'niitsu2012-{tag}.json'
        path.write_text(json.dumps(dataset, indent=1))
        written.append((path.name, len(values)))
    for name, n in written:
        print(f'{name}: {n} equilibria')
    return written


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('Validators')[0])
    ap.add_argument('--espei', action='store_true', help='write ESPEI ZPF datasets')
    args = ap.parse_args()
    problems, _ = validate()
    if args.espei:
        print()
        export_espei()
    raise SystemExit(1 if problems else 0)
