import {
  ComputedPhaseDiagram,
  ComputedSource,
  ThermodynamicProbeResult,
} from './types';

/** Index of the grid node nearest to (xA, xB); the grid is the dataset grid, no interpolation. */
export function nearestNodeIndex(src: ComputedSource, xA: number, xB: number): number {
  const N = src.subdivisions;
  const a = Math.max(0, Math.min(1, xA)) * N;
  const b = Math.max(0, Math.min(1, xB)) * N;
  const c = N - a - b;
  const i0 = Math.floor(a);
  const j0 = Math.floor(b);
  let best = -1;
  let bestD = Infinity;
  // nearest of the four surrounding grid points that lie inside the triangle
  for (const [i, j] of [[i0, j0], [i0 + 1, j0], [i0, j0 + 1], [i0 + 1, j0 + 1]]) {
    if (i < 0 || j < 0 || i + j > N) continue;
    const k = N - i - j;
    const d = (a - i) ** 2 + (b - j) ** 2 + (c - k) ** 2;
    if (d < bestD) {
      bestD = d;
      best = src.nodeIndexMap[i * (N + 1) + j];
    }
  }
  return best;
}

/** Index of the grid temperature nearest to T. */
export function nearestTempIndex(src: ComputedSource, tempK: number): number {
  const ts = src.temperaturesK;
  let best = 0;
  for (let k = 1; k < ts.length; k++) {
    if (Math.abs(ts[k] - tempK) < Math.abs(ts[best] - tempK)) best = k;
  }
  return best;
}

export interface ComputedState {
  /** {phase: fraction}, or null where pycalphad did not converge */
  phases: Record<string, number> | null;
  gmJ: number | null;
  nodeIndex: number;
  gridTempK: number;
}

/** Equilibrium at the grid node and grid temperature nearest to (x, T). */
export function computedStateAt(
  src: ComputedSource,
  xA: number,
  xB: number,
  tempK: number,
): ComputedState {
  const n = nearestNodeIndex(src, xA, xB);
  const k = nearestTempIndex(src, tempK);
  if (n < 0) return { phases: null, gmJ: null, nodeIndex: n, gridTempK: src.temperaturesK[k] };
  return {
    phases: src.states[n][k],
    gmJ: src.gmJ[n][k],
    nodeIndex: n,
    gridTempK: src.temperaturesK[k],
  };
}

/** Stable key of a phase set, e.g. "FCC_A1+LIQUID" (used to colour and outline phase fields). */
export function phaseSetKey(phases: Record<string, number> | null): string {
  if (!phases) return '';
  return Object.keys(phases).sort().join('+');
}

/**
 * Probe result from the dataset itself: the phases, fractions and molar Gibbs energy that
 * pycalphad computed at the nearest grid point and temperature. Chemical potentials are not
 * stored in the dataset and are reported as NaN.
 */
export function probeComputed(
  diagram: ComputedPhaseDiagram,
  xA: number,
  xB: number,
  xC: number,
  tempK: number,
  surface: ThermodynamicProbeResult['surface'],
  grid: { tLiquidus: number; tSolidus: number; primaryPhaseId: string },
): ThermodynamicProbeResult {
  const { system } = diagram;
  const src = system.computed!;
  const [e0, e1, e2] = system.elements;
  const mA = xA * e0.atomicMass;
  const mB = xB * e1.atomicMass;
  const mC = xC * e2.atomicMass;
  const mTot = mA + mB + mC || 1;

  const st = computedStateAt(src, xA, xB, tempK);
  const byId = new Map(system.phases.map((p) => [p.id, p]));
  const primary = byId.get(grid.primaryPhaseId) ?? system.phases[0];

  const equilibriumPhases = st.phases
    ? Object.entries(st.phases)
        .sort((a, b) => b[1] - a[1])
        .map(([id, f]) => {
          const p = byId.get(id);
          return { phaseId: id, label: p?.label ?? id, color: p?.color ?? '#94A3B8', fraction: f };
        })
    : [];

  const node = st.nodeIndex >= 0 ? src.nodes[st.nodeIndex] : null;
  const where = node
    ? `grid point ${(node.xA * 100).toFixed(1)} / ${(node.xB * 100).toFixed(1)} / ${(node.xC * 100).toFixed(1)} at.%, ${st.gridTempK} K`
    : 'outside the grid';
  const boundaryNote = st.phases
    ? `${phaseSetKey(st.phases).replace(/\+/g, ' + ')} (pycalphad, ${where})`
    : `pycalphad did not converge here (${where})`;

  return {
    xA,
    xB,
    xC,
    wtA: mA / mTot,
    wtB: mB / mTot,
    wtC: mC / mTot,
    tempK,
    tempC: tempK - 273.15,
    surface,
    primaryPhaseLabel: primary.label,
    primaryPhaseColor: primary.color,
    equilibriumPhases,
    gibbsKJ: st.gmJ === null ? NaN : st.gmJ / 1000,
    chemicalPotentialsKJ: [NaN, NaN, NaN],
    liquidusK: grid.tLiquidus,
    solidusK: grid.tSolidus,
    boundaryNote,
  };
}
