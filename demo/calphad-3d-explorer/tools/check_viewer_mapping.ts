// Checks that the viewer reads a dataset exactly as pycalphad wrote it: the probe at grid-node
// compositions must return the stored phases, fractions and Gibbs energy.
// Usage (from demo/calphad-3d-explorer): npx tsx tools/check_viewer_mapping.ts datasets/<file>.json
import { readFileSync } from 'fs';
import { systemFromDataset } from '../src/calphad/dataset.ts';
import { assembleDiagram, probeThermodynamics } from '../src/calphad/solver.ts';
const raw = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const sys = systemFromDataset(raw);
const c = sys.computed!;
const d = assembleDiagram(sys, c.subdivisions, c.nodes, c.nodeIndexMap, false);
let bad = 0, checked = 0;
// every 7th dataset node at several temperatures: probe at the exact node composition must equal the JSON state
raw.nodes.forEach((n: any, idx: number) => {
  if (idx % 7) return;
  for (const k of [0, 40, 80, 120, 180]) {
    const T = raw.grid.temperatures_K[k];
    const p = probeThermodynamics(d, 0, n.xA, n.xB, n.xC, T, 'isotherm');
    const want = n.states[k] ?? {};
    const got = Object.fromEntries(p.equilibriumPhases.map((e: any) => [e.phaseId, e.fraction]));
    const same = Object.keys(want).length === Object.keys(got).length &&
      Object.entries(want).every(([ph, f]) => Math.abs((got[ph] ?? -1) - (f as number)) < 1e-9);
    const gmOk = n.gm_J[k] === null ? Number.isNaN(p.gibbsKJ) : Math.abs(p.gibbsKJ * 1000 - n.gm_J[k]) < 1e-6;
    checked++; if (!same || !gmOk) { bad++; if (bad < 4) console.log('MISMATCH', n.xA, n.xB, n.xC, T, want, got); }
  }
});
console.log(`probe vs JSON: ${checked} checks, ${bad} mismatches`);
if (bad) process.exitCode = 1;
const fe = c.nodes.find(n => n.xA === 1)!, la = c.nodes.find(n => n.xB === 1)!, si = c.nodes.find(n => n.xC === 1)!;
console.log('corners Tliq: Fe', fe.tLiquidus, 'La', la.tLiquidus, 'Si', si.tLiquidus, '| elements', sys.elements.map(e => `${e.symbol} Tm ${e.meltingPointK}`).join(', '));
console.log('labels:', d.invariantPoints.map(p => `${p.label} ${Math.round(p.tempK)} K`).join(' | '));
