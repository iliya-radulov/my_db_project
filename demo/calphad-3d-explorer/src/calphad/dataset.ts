import { ELEMENT_LOOKUP, ELEMENT_PALETTE, PHASE_PALETTE } from './tdbParser';
import { CalphadSystem, ComputedSource, ElementSpec, GridNode, PhaseDefinition } from './types';

/** JSON written by tools/export_ternary.py (schema calphad-ternary-dataset/1). */
export interface TernaryDatasetFile {
  schema: string;
  system: {
    elements: [string, string, string];
    label: string;
    source: { tdb_file: string; tdb_path: string; tdb_sha256: string };
  };
  grid: {
    subdivisions: number;
    temperatures_K: number[];
    temperature_step_K: number;
  };
  phases: { considered: string[]; appearing: string[]; liquid: string[]; excluded: string[] };
  provenance: Record<string, unknown> & {
    pycalphad?: string;
    created_utc?: string;
    failed_points?: number;
    rejected_points?: number;
  };
  nodes: Array<{
    i: number; // steps of element B (dataset convention)
    j: number; // steps of element C
    xA: number;
    xB: number;
    xC: number;
    t_liquidus_K: number | null;
    t_solidus_K: number | null;
    primary_phase: string | null;
    solid_assemblage: string[] | null;
    states: Array<Record<string, number> | null>;
    gm_J: Array<number | null>;
  }>;
}

export const DATASET_SCHEMA = 'calphad-ternary-dataset/1';
const LIQUID_COLOR = '#38BDF8'; // same as the built-in systems

function displaySymbol(s: string): string {
  return s.length <= 1 ? s : s[0] + s.slice(1).toLowerCase();
}

function dominant(state: Record<string, number> | null, exclude: Set<string>): string | null {
  if (!state) return null;
  let best: string | null = null;
  for (const [p, f] of Object.entries(state)) {
    if (exclude.has(p)) continue;
    if (best === null || f > state[best]) best = p;
  }
  return best;
}

/** Throws with a readable message if the file is not a usable dataset. */
export function validateDataset(d: unknown): asserts d is TernaryDatasetFile {
  const ds = d as TernaryDatasetFile;
  if (!ds || typeof ds !== 'object') throw new Error('Not a JSON object.');
  if (ds.schema !== DATASET_SCHEMA) {
    throw new Error(`Unknown dataset schema "${String(ds.schema)}" (expected ${DATASET_SCHEMA}).`);
  }
  const N = ds.grid?.subdivisions;
  const nT = ds.grid?.temperatures_K?.length;
  if (!Number.isInteger(N) || N < 1 || !nT) throw new Error('Missing or invalid grid.');
  if (ds.system?.elements?.length !== 3) throw new Error('A ternary dataset needs exactly three elements.');
  const expected = ((N + 1) * (N + 2)) / 2;
  if (!Array.isArray(ds.nodes) || ds.nodes.length !== expected) {
    throw new Error(`Expected ${expected} grid nodes for ${N} subdivisions, found ${ds.nodes?.length}.`);
  }
  for (const n of ds.nodes) {
    if (n.states?.length !== nT || n.gm_J?.length !== nT) {
      throw new Error(`Node (${n.i}, ${n.j}) does not have one state per temperature.`);
    }
  }
}

/** Builds a CalphadSystem (with `computed`) from a validated dataset. */
export function systemFromDataset(ds: TernaryDatasetFile): CalphadSystem {
  validateDataset(ds);
  const N = ds.grid.subdivisions;
  const temps = ds.grid.temperatures_K;
  const tMin = temps[0];
  const tMax = temps[temps.length - 1];
  const liquids = new Set(ds.phases.liquid);
  const stride = N + 1;
  const nodeIndexMap = new Int32Array(stride * stride).fill(-1);

  let liquidusAboveRange = 0;
  let solidusBelowRange = 0;
  const nodes: GridNode[] = [];
  const states: ComputedSource['states'] = [];
  const gmJ: ComputedSource['gmJ'] = [];

  for (const n of ds.nodes) {
    // dataset: i = steps of B, j = steps of C; front-end grid: i = steps of A, j = steps of B
    const iF = N - n.i - n.j;
    const jF = n.i;
    const xA = iF / N;
    const xB = jF / N;
    const xC = n.j / N;

    let tLiq = n.t_liquidus_K;
    if (tLiq === null) {
      tLiq = tMax; // not all liquid even at the highest computed temperature
      liquidusAboveRange++;
    }
    let tSol = n.t_solidus_K;
    if (tSol === null) {
      tSol = tMin; // liquid present even at the lowest computed temperature
      solidusBelowRange++;
    }

    const firstAbove = temps.findIndex((t) => t > tSol!);
    const kSol = firstAbove < 0 ? temps.length - 1 : Math.max(0, firstAbove - 1); // last grid T at or below the solidus
    const kLiq = temps.reduce((b, t, k) => (Math.abs(t - tLiq!) < Math.abs(temps[b] - tLiq!) ? k : b), 0);
    const primary =
      n.primary_phase ?? dominant(n.states[temps.length - 1], liquids) ?? ds.phases.liquid[0] ?? 'LIQUID';
    const solid = dominant(n.states[kSol], liquids) ?? primary;
    const g = n.gm_J[kLiq];

    nodeIndexMap[iF * stride + jF] = nodes.length;
    nodes.push({
      i: iF,
      j: jF,
      xA,
      xB,
      xC,
      tLiquidus: tLiq,
      tSolidus: Math.min(tSol, tLiq),
      tSolvus: NaN,
      primaryPhaseId: primary,
      solidPhaseId: solid,
      gLiquidusKJ: g === null ? NaN : g / 1000,
    });
    states.push(n.states);
    gmJ.push(n.gm_J);
  }

  // phases: liquid first (the scene treats phases[0] as the liquid), then the solids that appear
  const solidIds = ds.phases.appearing.filter((p) => !liquids.has(p));
  const liquidId = ds.phases.liquid[0] ?? 'LIQUID';
  const phases: PhaseDefinition[] = [
    { id: liquidId, label: 'Liquid (L)', shortLabel: 'L', crystalStructure: 'Liquid', kind: 'liquid', color: LIQUID_COLOR },
    ...solidIds.map((id, k) => ({
      id,
      label: id.replace(/_/g, ' '),
      shortLabel: id, // full name: shortened names collide (e.g. two LASI2 phases)
      crystalStructure: id,
      kind: 'solution' as const,
      color: PHASE_PALETTE[k % PHASE_PALETTE.length],
    })),
  ];

  const corner = (iF: number, jF: number) => nodes[nodeIndexMap[iF * stride + jF]];
  const cornerNodes = [corner(N, 0), corner(0, N), corner(0, 0)]; // pure A, pure B, pure C
  const elements = ds.system.elements.map((sym, idx) => {
    const ref = ELEMENT_LOOKUP[sym.toUpperCase()];
    return {
      symbol: displaySymbol(sym),
      name: ref?.name ?? displaySymbol(sym),
      atomicMass: ref?.mass ?? 55.0,
      meltingPointK: cornerNodes[idx]?.tLiquidus ?? NaN,
      enthalpyFusionJ: ref?.hfJ ?? NaN,
      color: ELEMENT_PALETTE[idx],
    };
  }) as [ElementSpec, ElementSpec, ElementSpec];

  const src = ds.system.source;
  const prov = ds.provenance;
  const totalPoints = ds.nodes.length * temps.length;
  const stem = src.tdb_file.replace(/\.tdb$/i, '');
  const shortStem = stem.length > 28 ? `${stem.slice(0, 27)}…` : stem;
  const elementsLabel = elements.map((e) => e.symbol).join('–');
  const step = ds.grid.temperature_step_K;

  const computed: ComputedSource = {
    subdivisions: N,
    temperaturesK: temps,
    temperatureStepK: step,
    nodeIndexMap,
    states,
    gmJ,
    nodes,
    tdbFile: src.tdb_file,
    tdbSha256: src.tdb_sha256,
    pycalphadVersion: String(prov.pycalphad ?? 'unknown'),
    createdUtc: String(prov.created_utc ?? 'unknown'),
    failedPoints: Number(prov.failed_points ?? 0),
    rejectedPoints: Number(prov.rejected_points ?? 0),
    totalPoints,
    liquidusAboveRange,
    solidusBelowRange,
    provenance: { ...prov, source: src, grid: ds.grid, phases: ds.phases },
  };

  return {
    id: `dataset-${src.tdb_sha256.slice(0, 12)}-${elementsLabel}`,
    name: `${elementsLabel} · ${shortStem}`,
    subtitle: `Computed equilibria · ${src.tdb_file} · grid ${N}, ${tMin}–${tMax} K in ${step} K steps`,
    reference: `pycalphad ${computed.pycalphadVersion} · ${src.tdb_file} · sha256 ${src.tdb_sha256.slice(0, 12)}…`,
    elements,
    tempMinK: tMin,
    tempMaxK: tMax,
    defaultSliceK: Math.round((tMin + (tMax - tMin) * 0.45) / step) * step,
    phases,
    tunableInteraction: { phaseId: liquidId, pair: [0, 1], label: 'Not available for computed datasets', minDeltaJ: 0, maxDeltaJ: 0 },
    computed,
  };
}
