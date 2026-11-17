"""
import_franco_s6.py   (WP7, dry run only: this version never touches the database)

Reads Table S6 (Heusler alloys) from the supplementary material of
Franco et al., Prog. Mater. Sci. 93 (2018) 112, doi:10.1016/j.pmatsci.2017.10.005
(docx table 6, 309 data rows; identical in content to the official mmc1.pdf)
and builds the rows that would go into mce_literature_records / _points.

Rules: claude/WP7_Freeze_Proposal_20261117.md (F1-F12, A1-A6) plus the row-
structure rules R1-R5 below, which were written after looking at the line
counts of the multi-line cells (not at any value) and are listed there as A7.

R1  A cell may hold several lines. The 'Type' cell lines are the transition
    types of the row. >1 type line -> one record per type line
    (external_id gets -1, -2); T line k belongs to type line k.
R2  With >1 type line: field and mode cells with one line are shared by all
    records; dS / dT cells with as many lines as types go line by line;
    a single non-blank dS / dT / T line cannot be assigned -> review.
    A single hysteresis line goes to the FOPT record if there is exactly one
    FOPT line (Af-Ms exists for the first-order transition only), noted.
R3  One type line, several lines in field/dS/dT/mode = measurement lines:
    field line k pairs with dS line k and dT line k; dS has to have as many
    lines as the field cell; dT as many lines, or be blank. Else review.
R4  Inside a line, values separated by '/' are paired in order with the
    field values of that line; counts must be equal. Values must be plain
    numbers (optional leading '~' = approximate, optional sign); anything
    else (annotations like (r), CH, N-CH, ranges, '<2') is not parsed:
    the value is left out and the row goes to the review table.
R5  Nothing is guessed: a quantity that cannot be paired is not loaded and
    the raw cell text is kept in the review table and in the record's
    comments (pairing_ambiguous).
"""
import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

import docx

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))      # repo root, as in import_nims.py
from composition_key import ELEMENTS, INTERSTITIALS, composition_key, split_composition  # noqa: E402
from mcedb_dataset import FormulaError, parse_formula  # noqa: E402

SOURCE = 'franco2018_s6_heusler'
QUALITY_FLAG = 'experimental_literature'
LICENCE = ('Supplementary data (Table S6) of Franco et al., Prog. Mater. Sci. 93 (2018) 112, '
           'doi:10.1016/j.pmatsci.2017.10.005; reuse with citation, permission from V. Franco')
SUM_FLAG_TOL = 0.5          # F6
NUM = r'\d+(?:\.\d+)?'
RE_T = re.compile(rf'^(~)?({NUM})$')
RE_FIELD = re.compile(rf'^({NUM})$')
RE_VAL = re.compile(rf'^(~)?([+-]?{NUM})$')
RE_HYS = RE_T
T_SOURCE = {'FOPT': 'S6 martensite start (FOPT)', 'SOPT': 'S6 Curie temperature (SOPT)'}


def lines(cell):
    return [x.strip() for x in cell.split('\n')]


def nonblank(ls):
    return [x for x in ls if x]


def split_vals(line):
    return [x.strip() for x in line.split('/')] if line else []


def parse_name(name):
    """-> (composition dict from parse_formula, single_crystal flag)."""
    s = name.strip()
    star = s.endswith('*')
    return parse_formula(s.rstrip('*').strip()), star


def raw_sums(comp):
    metal = sum(v for e, v in comp.items() if e not in INTERSTITIALS)
    return metal, sum(comp.values())


def load_rows(path):
    t = docx.Document(path).tables[5]
    sub, out = None, []
    for i, r in enumerate(t.rows):
        c = [x.text for x in r.cells]
        if c[1].strip() == 'Type':
            sub = c[0].strip()
            continue
        out.append(dict(table_row=i, sub=sub, comp=c[0].strip(), type=c[1], T=c[2], H=c[3],
                        dS=c[4], dT=c[5], hys=c[6], mode=c[7], ref=c[8].strip()))
    return out


def pair_line(field_line, val_line, kind, quantity, problems, approx):
    """Pairs '/'-separated field and value tokens of one line.
    Returns [(field, value)], or None if a pairing problem was added."""
    if not val_line:
        return []
    fs, vs = split_vals(field_line), split_vals(val_line)
    if len(fs) != len(vs):
        problems.append(f'{quantity}: {len(fs)} field value(s) vs {len(vs)} value(s) in one line')
        return None
    out = []
    for f, v in zip(fs, vs):
        mf, mv = RE_FIELD.match(f), RE_VAL.match(v)
        if not mf or not mv:
            problems.append(f'{quantity}: not a plain number: field {f!r} value {v!r}')
            return None
        if mv.group(1):
            approx.add(quantity)
        out.append((float(mf.group(1)), float(mv.group(2))))
    return out


def build(row):
    """-> list of record dicts (1 per type line), each with 'points', plus review reasons."""
    problems, approx_rows = [], []
    comp, star = parse_name(row['comp'])
    tl = lines(row['type'])
    types = nonblank(tl)
    nt = len(types)
    if nt == 0:
        problems.append('type missing')
    Tl, Hl, Sl, Dl, Yl, Ml = (lines(row[k]) for k in ('T', 'H', 'dS', 'dT', 'hys', 'mode'))
    n_cells = {k: len(v) for k, v in zip(('T', 'H', 'dS', 'dT', 'hys', 'mode'), (Tl, Hl, Sl, Dl, Yl, Ml))}

    # strip trailing blank lines produced by '\n' at the end of a cell
    def trim(ls):
        while len(ls) > 1 and not ls[-1]:
            ls = ls[:-1]
        return ls
    tl_, Tl, Hl, Sl, Dl, Yl, Ml = map(trim, (tl, Tl, Hl, Sl, Dl, Yl, Ml))
    # type lines: blank lines inside the cell are dropped for the type only
    nrec = max(nt, 1)

    recs = [dict(rtype=(types[k] if nt else ''), T=None, hys=None, mode=None, points=[], approx=set(),
                 notes=[]) for k in range(nrec)]

    def single_value(ls, rx, label, k_target, field):
        return None

    def assign_per_type(ls, label):
        """lines -> list per record, or None if not assignable."""
        nb = nonblank(ls)
        if not nb:
            return [''] * nrec
        if nrec == 1:
            return [ls[0]] if len(ls) == 1 else None
        if len(ls) == nrec:
            return ls
        # T cells may carry blank separator lines ('310||325'): only the non-blank ones count
        if len(nb) == nrec and label == 'T':
            return nb
        return None

    # --- T ---
    per_T = assign_per_type(Tl, 'T')
    if per_T is None:
        problems.append(f'T: {len(Tl)} line(s) for {nrec} type line(s): {row["T"]!r}')
    else:
        for k, v in enumerate(per_T):
            if not v:
                continue
            m = RE_T.match(v)
            if not m:
                problems.append(f'T: not a plain number: {v!r}')
            else:
                recs[k]['T'] = float(m.group(2))
                if m.group(1):
                    recs[k]['approx'].add('T')

    # --- hysteresis ---
    nbY = nonblank(Yl)
    if nbY:
        if nrec == 1 and len(Yl) == 1:
            per_Y = Yl
        elif nrec > 1 and len(Yl) == nrec:
            per_Y = Yl
        elif nrec > 1 and len(Yl) == 1:
            f = [k for k in range(nrec) if recs[k]['rtype'] == 'FOPT']
            per_Y = None
            if len(f) == 1:
                per_Y = [''] * nrec
                per_Y[f[0]] = Yl[0]
                recs[f[0]]['notes'].append('hyst_single_line_assigned_to_FOPT')
            else:
                problems.append(f'hysteresis: single line, {nrec} types, not exactly one FOPT')
        else:
            per_Y = None
            problems.append(f'hysteresis: {len(Yl)} line(s) for {nrec} type line(s)')
        if per_Y:
            for k, v in enumerate(per_Y):
                if not v:
                    continue
                m = RE_HYS.match(v)
                if not m:
                    problems.append(f'hysteresis not a plain number: {v!r}')
                    recs[k]['notes'].append(f'hyst_raw={v}')
                else:
                    recs[k]['hys'] = float(m.group(2))
                    if m.group(1):
                        recs[k]['approx'].add('hys')

    # --- mode ---
    nbM = nonblank(Ml)
    if nrec == 1:
        recs[0]['mode'] = '|'.join(nbM) if nbM else None
    elif len(Ml) == 1:
        for r in recs:
            r['mode'] = Ml[0] or None
    elif len(Ml) == nrec:
        for k, r in enumerate(recs):
            r['mode'] = Ml[k] or None
    else:
        problems.append(f'mode: {len(Ml)} line(s) for {nrec} type line(s): {row["mode"]!r}')
        for r in recs:
            r['mode'] = row['mode'].replace('\n', '|')

    # --- field / dS / dT points ---
    def points_for(rec_idx, field_line, S_line, D_line):
        ap = set()
        ps = pair_line(field_line, S_line, 'dS', 'dS_signed', problems, ap)
        pd_ = pair_line(field_line, D_line, 'dT', 'dT_ad_signed', problems, ap)
        for q, p in (('dS_signed', ps), ('dT_ad_signed', pd_)):
            for f, v in (p or []):
                recs[rec_idx]['points'].append((q, f, v))
        recs[rec_idx]['approx'] |= ({'dS'} if 'dS_signed' in ap else set()) | ({'dT'} if 'dT_ad_signed' in ap else set())

    if nrec == 1:
        nf = len(Hl)
        if nf == 1:
            if len(Sl) == 1 and len(Dl) == 1:
                points_for(0, Hl[0], Sl[0], Dl[0])
            else:
                problems.append(f'field 1 line but dS {len(Sl)} / dT {len(Dl)} lines')
        else:
            ok = len(Sl) == nf and (len(Dl) == nf or not nonblank(Dl))
            if not ok:
                problems.append(f'measurement lines: field {nf}, dS {len(Sl)}, dT {len(Dl)}')
            else:
                for k in range(nf):
                    points_for(0, Hl[k], Sl[k], Dl[k] if len(Dl) == nf else '')
    else:
        # several type lines
        shared_field = Hl[0] if len(Hl) == 1 else None
        for k in range(nrec):
            fl = shared_field if shared_field is not None else (Hl[k] if len(Hl) == nrec else None)
            if fl is None:
                problems.append(f'field: {len(Hl)} line(s) for {nrec} type line(s)')
                break
            S = Sl[k] if len(Sl) == nrec else None
            D = Dl[k] if len(Dl) == nrec else ('' if not nonblank(Dl) else None)
            if S is None and nonblank(Sl):
                problems.append(f'dS: {len(Sl)} line(s) for {nrec} type line(s)')
                S = ''
            if D is None:
                problems.append(f'dT: {len(Dl)} line(s) for {nrec} type line(s): {row["dT"]!r}')
                D = ''
            points_for(k, fl, S or '', D or '')

    for r in recs:
        r['comp'], r['star'] = comp, star
    return recs, problems


def build_all(path):
    rows = load_rows(path)
    records, review, points_flat, flagged = [], [], [], []
    for row in rows:
        try:
            recs, problems = build(row)
        except FormulaError as e:
            review.append(dict(table_row=row['table_row'], comp=row['comp'], ref=row['ref'],
                               reason=f'composition: {e}', **{k: row[k].replace('\n', '|') for k in
                               ('type', 'T', 'H', 'dS', 'dT', 'hys', 'mode')}))
            continue
        comp = recs[0]['comp']
        metal_sum, total = raw_sums(comp)
        at_pct_row = 90 <= metal_sum <= 110
        # A8: flag only if NEITHER the metal sum NOR the total sum is 100 (B can replace an element
        # or be an add-on; either way one of the two sums is 100)
        sum_flag = at_pct_row and abs(metal_sum - 100) > SUM_FLAG_TOL and abs(total - 100) > SUM_FLAG_TOL
        metal_raw = {e: v for e, v in comp.items() if e not in INTERSTITIALS}
        inter_raw = {e: v for e, v in comp.items() if e in INTERSTITIALS}
        unknown = [e for e in comp if e not in ELEMENTS]
        m_pct, i_pct = split_composition(comp)
        key = composition_key(metal_raw, {e: 100.0 * v / sum(metal_raw.values()) for e, v in inter_raw.items()} or None)
        if sum_flag:
            flagged.append((row['table_row'], row['comp'], round(metal_sum, 3), round(total, 3)))
        multi = len(recs) > 1
        sub = re.sub(r'[^A-Za-z]', '', row['sub'].replace('Ni-Mn-', 'NiMn').replace('Others Heusler alloys', 'Others'))
        for k, r in enumerate(recs):
            ext = f"S6-{sub}-{row['table_row']:04d}" + (f'-{k + 1}' if multi else '')
            comments = [f"type={r['rtype'] or 'missing'}", f"mode={r['mode'] or ''}"]
            if r['star']:
                comments.append('single_crystal')
            if r['approx']:
                comments.append('approx=' + ','.join(sorted(r['approx'])))
            if sum_flag:
                comments.append(f'sum_off:metal={metal_sum:.2f},total={total:.2f}')
            comments += r['notes']
            if problems:
                comments.append('pairing_ambiguous')
            rec = dict(
                source=SOURCE, external_id=ext, licence=LICENCE, quality_flag=QUALITY_FLAG,
                family=row['sub'], composition_text=row['comp'],
                composition_details=f"raw_metal_sum={metal_sum:.3f};raw_total={total:.3f}",
                composition_key=key,
                metal_at_pct={e: round(v, 4) for e, v in m_pct.items()},
                interstitial_at_pct={e: round(v, 4) for e, v in i_pct.items()} or None,
                article_ref=row['ref'], doi=None,
                t_tr_k=r['T'], t_tr_source=T_SOURCE.get(r['rtype']) if r['T'] is not None else None,
                t_hys_k=r['hys'], comments=';'.join(comments))
            records.append(rec)
            for q, f, v in r['points']:
                points_flat.append((ext, q, f, v, None, None))
        if problems:
            review.append(dict(table_row=row['table_row'], comp=row['comp'], ref=row['ref'],
                               reason=' | '.join(problems),
                               **{k: row[k].replace('\n', '|') for k in ('type', 'T', 'H', 'dS', 'dT', 'hys', 'mode')}))
    return rows, records, points_flat, review, flagged


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--docx', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--load', action='store_true',
                    help='write to the database (one transaction). Without it nothing is written (dry run).')
    ap.add_argument('--seed', type=int, default=17)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    rows, records, points, review, flagged = build_all(a.docx)
    n_rows = len(rows)
    print(f'rows read from the docx: {n_rows}')
    rows_with_records = len({r['external_id'].rsplit('-', 1)[0] if re.search(r'-\d$', r['external_id']) else r['external_id'] for r in records})
    print(f'records built: {len(records)} (from {rows_with_records} rows; '
          f'{len(records) - rows_with_records} extra records from rows with several type lines)')
    rejected = n_rows - rows_with_records
    print(f'rows rejected (no record): {rejected}')
    ids = [r['external_id'] for r in records]
    assert len(ids) == len(set(ids)), 'external_id not unique'
    print(f"quality_flag: {Counter(r['quality_flag'] for r in records)}")
    print(f"record types: {Counter(r['comments'].split(';')[0] for r in records)}")
    print(f"composition keys: {len(set(r['composition_key'] for r in records))} distinct")

    # A6: simulate the writer
    seen, submitted, skipped, conflicts = set(), len(points), 0, []
    inserted = 0
    for ext, q, f, v, tp, fw in points:
        if v is None or f is None:
            skipped += 1
            continue
        key = (ext, q, f)
        if key in seen:
            conflicts.append(key)
            continue
        seen.add(key)
        inserted += 1
    print(f'points submitted {submitted} = inserted {inserted} + skipped {skipped} + conflicts {len(conflicts)}')
    print(f"  by quantity: {Counter(p[1] for p in points)}")
    print(f"  records with at least one point: {len({p[0] for p in points})}; without: {len(records) - len({p[0] for p in points})}")
    print(f"  dS_signed: {sum(1 for p in points if p[1] == 'dS_signed' and p[3] > 0)} positive, "
          f"{sum(1 for p in points if p[1] == 'dS_signed' and p[3] < 0)} negative, "
          f"{sum(1 for p in points if p[1] == 'dS_signed' and p[3] == 0)} zero")
    print(f'F6/A8 flagged rows (neither metal sum nor total sum within {SUM_FLAG_TOL} of 100): {len(flagged)}')
    for f in flagged:
        print('   ', f)
    print(f'review table: {len(review)} rows')
    print(f"  reason classes: {Counter(r['reason'].split(':')[0].split(' ')[0] for r in review)}")

    with open(out / 'records.json', 'w') as fh:
        json.dump(records, fh, indent=1, default=str)
    with open(out / 'points.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['external_id', 'quantity', 'field_t', 'value', 't_peak_k', 'fwhm_k'])
        w.writerows(points)
    if review:
        with open(out / 'review.csv', 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(review[0]))
            w.writeheader()
            w.writerows(review)
    random.seed(a.seed)
    sample = random.sample(range(n_rows), 20)
    with open(out / 'sample20.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['table_row', 'comp', 'type', 'T', 'H', 'dS', 'dT', 'hys', 'mode', 'ref', '->records'])
        for i in sorted(sample):
            r = rows[i]
            recs = [x for x in records if x['external_id'].split('-')[2] == f"{r['table_row']:04d}"]
            w.writerow([r['table_row'], r['comp']] + [r[k].replace('\n', '|') for k in ('type', 'T', 'H', 'dS', 'dT', 'hys', 'mode', 'ref')]
                       + [json.dumps([(x['external_id'], x['t_tr_k'], [(p[1], p[2], p[3]) for p in points if p[0] == x['external_id']]) for x in recs])])
    print(f'written to {out}')

    if not a.load:
        print('DRY RUN: nothing written to the database (use --load to write).')
        return
    from psycopg2.extras import Json
    from literature_db import replace_points, upsert_records
    from stage_two.alloy.alloy_db_v2 import get_db
    db = get_db()
    cur = db.cursor
    try:
        recs = [{**r, 'metal_at_pct': Json(r['metal_at_pct']),
                 'interstitial_at_pct': Json(r['interstitial_at_pct']) if r['interstitial_at_pct'] else None}
                for r in records]
        ids = upsert_records(cur, recs)
        n_points = replace_points(cur, ids, points)
        if len(ids) != len(records) or n_points != inserted:
            raise RuntimeError(f'count mismatch: records {len(ids)} vs {len(records)}, points {n_points} vs {inserted}')
        db.commit()
        print(f"Imported {len(ids)} records and {n_points} points (source '{SOURCE}')")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
