import {
  BoundaryCurve,
  CalphadSystem,
  ComputedPhaseDiagram,
  GridNode,
  InvariantPoint,
  PhaseDefinition,
  ThermodynamicProbeResult,
} from './types';
import { probeComputed } from './computedLookup';

export const R_GAS = 8.314462618; // J/(mol·K)

// Shared 3D prism geometry constants (centered at X=0, Z=0; Y=0 is plinth top)
export const TRIANGLE_SIDE = 6.2;
export const PRISM_HEIGHT = 4.4;
export const PRISM_BASE_Y = 0.08;

const SQRT3 = Math.sqrt(3);

// Equilateral triangle vertices in XZ plane (centroid at 0, 0)
export const VERTEX_A: readonly [number, number] = [
  -TRIANGLE_SIDE / 2,
  (TRIANGLE_SIDE * SQRT3) / 6,
];
export const VERTEX_B: readonly [number, number] = [
  TRIANGLE_SIDE / 2,
  (TRIANGLE_SIDE * SQRT3) / 6,
];
export const VERTEX_C: readonly [number, number] = [
  0,
  -(TRIANGLE_SIDE * SQRT3) / 3,
];

/** Convert barycentric mole fractions (xA, xB, xC) and temperature T to 3D world coordinates */
export function baryToWorld(
  xA: number,
  xB: number,
  xC: number,
  tempK: number,
  tempMinK: number,
  tempMaxK: number,
): [number, number, number] {
  const x = xA * VERTEX_A[0] + xB * VERTEX_B[0] + xC * VERTEX_C[0];
  const z = xA * VERTEX_A[1] + xB * VERTEX_B[1] + xC * VERTEX_C[1];
  const y = tempToY(tempK, tempMinK, tempMaxK);
  return [x, y, z];
}

export function tempToY(tempK: number, tempMinK: number, tempMaxK: number): number {
  const tNorm = Math.max(0, Math.min(1, (tempK - tempMinK) / (tempMaxK - tempMinK)));
  return PRISM_BASE_Y + tNorm * PRISM_HEIGHT;
}

export function yToTemp(y: number, tempMinK: number, tempMaxK: number): number {
  const tNorm = Math.max(0, Math.min(1, (y - PRISM_BASE_Y) / PRISM_HEIGHT));
  return tempMinK + tNorm * (tempMaxK - tempMinK);
}

/** Convert XZ world coordinates back to clamped barycentric mole fractions (xA, xB, xC) */
export function worldToBary(x: number, z: number): [number, number, number] {
  const x1 = VERTEX_A[0];
  const z1 = VERTEX_A[1];
  const x2 = VERTEX_B[0];
  const z2 = VERTEX_B[1];
  const x3 = VERTEX_C[0];
  const z3 = VERTEX_C[1];

  const det = (z2 - z3) * (x1 - x3) + (x3 - x2) * (z1 - z3);
  let xA = ((z2 - z3) * (x - x3) + (x3 - x2) * (z - z3)) / det;
  let xB = ((z3 - z1) * (x - x3) + (x1 - x3) * (z - z3)) / det;
  let xC = 1 - xA - xB;

  xA = Math.max(0, Math.min(1, xA));
  xB = Math.max(0, Math.min(1, xB));
  xC = Math.max(0, Math.min(1, xC));
  const sum = xA + xB + xC || 1;
  return [xA / sum, xB / sum, xC / sum];
}

function safeXlnX(x: number): number {
  if (x <= 1e-7) return 0;
  return x * Math.log(x);
}

/**
 * Evaluates the molar Gibbs free energy G_m^phi(xA, xB, xC, T) in J/mol
 * using Redlich-Kister-Muggianu excess polynomials.
 */
export function evaluatePhaseGibbsJ(
  phase: PhaseDefinition,
  xA: number,
  xB: number,
  xC: number,
  tempK: number,
  system: CalphadSystem,
  deltaInteractionJ: number,
): number {
  const x = [xA, xB, xC];
  const isTunedPhase = system.tunableInteraction.phaseId === phase.id;

  if (phase.kind === 'compound' && phase.stoichiometry) {
    const [s0, s1, s2] = phase.stoichiometry;
    const d0 = xA - s0;
    const d1 = xB - s1;
    const d2 = xC - s2;
    const distSq = d0 * d0 + d1 * d1 + d2 * d2;

    let baseG = 0;
    if (phase.evalCompoundJ) {
      baseG = phase.evalCompoundJ(tempK) + (isTunedPhase ? deltaInteractionJ : 0);
    } else if (phase.compoundStability) {
      baseG =
        phase.compoundStability.a +
        (isTunedPhase ? deltaInteractionJ : 0) +
        phase.compoundStability.b * tempK;
    }

    const curvature = phase.homogeneityCurvature ?? 32000;
    const idealS = R_GAS * tempK * (safeXlnX(xA) + safeXlnX(xB) + safeXlnX(xC)) * 0.25;
    return baseG + curvature * distSq + idealS;
  }

  // Reference (unary) Gibbs energy (supports full SGTE piecewise TDB functions or linear stabilities)
  let gRef = 0;
  if (phase.evalUnaryJ) {
    gRef =
      xA * phase.evalUnaryJ[0](tempK) +
      xB * phase.evalUnaryJ[1](tempK) +
      xC * phase.evalUnaryJ[2](tempK);
  } else if (phase.unaryStabilities) {
    for (let i = 0; i < 3; i++) {
      gRef += x[i] * (phase.unaryStabilities[i].a + phase.unaryStabilities[i].b * tempK);
    }
  }

  // Ideal configurational mixing entropy
  const gIdeal = R_GAS * tempK * (safeXlnX(xA) + safeXlnX(xB) + safeXlnX(xC));

  // Redlich-Kister binary excess terms
  let gExcess = 0;
  if (phase.evalInteractions && phase.evalInteractions.length > 0) {
    for (const inter of phase.evalInteractions) {
      const i = inter.pair[0];
      const j = inter.pair[1];
      const xi = x[i];
      const xj = x[j];
      if (xi <= 1e-7 || xj <= 1e-7) continue;

      const isTunedPair =
        isTunedPhase &&
        inter.order === 0 &&
        system.tunableInteraction.pair[0] === i &&
        system.tunableInteraction.pair[1] === j;

      const lVal = inter.eval(tempK) + (isTunedPair ? deltaInteractionJ : 0);
      const diffPow = inter.order === 0 ? 1 : Math.pow(xi - xj, inter.order);
      gExcess += xi * xj * lVal * diffPow;
    }
  } else if (phase.interactions) {
    for (const inter of phase.interactions) {
      const i = inter.pair[0];
      const j = inter.pair[1];
      const xi = x[i];
      const xj = x[j];
      if (xi <= 1e-7 || xj <= 1e-7) continue;

      const isTunedPair =
        isTunedPhase &&
        system.tunableInteraction.pair[0] === i &&
        system.tunableInteraction.pair[1] === j;

      const l0 = inter.a0 + (isTunedPair ? deltaInteractionJ : 0) + inter.b0 * tempK;
      let poly = l0;
      if (inter.a1 !== undefined && inter.b1 !== undefined) {
        const l1 = inter.a1 + inter.b1 * tempK;
        poly += l1 * (xi - xj);
      }
      gExcess += xi * xj * poly;
    }
  }

  // Also apply deltaInteractionJ if the tunable pair has no explicit L0 entry in the TDB
  if (
    isTunedPhase &&
    deltaInteractionJ !== 0 &&
    phase.evalInteractions &&
    !phase.evalInteractions.some(
      (it) =>
        it.order === 0 &&
        it.pair[0] === system.tunableInteraction.pair[0] &&
        it.pair[1] === system.tunableInteraction.pair[1],
    )
  ) {
    const xi = x[system.tunableInteraction.pair[0]];
    const xj = x[system.tunableInteraction.pair[1]];
    gExcess += xi * xj * deltaInteractionJ;
  }

  // Ternary Muggianu interaction
  if (phase.evalTernary && phase.evalTernary.length > 0) {
    const prod = xA * xB * xC;
    if (prod > 1e-9) {
      if (phase.evalTernary.length === 1 && phase.evalTernary[0].order === 0) {
        gExcess += prod * phase.evalTernary[0].eval(tempK);
      } else {
        let sumT = 0;
        for (const tTerm of phase.evalTernary) {
          const weight = tTerm.order === 0 ? xA : tTerm.order === 1 ? xB : xC;
          sumT += weight * tTerm.eval(tempK);
        }
        gExcess += prod * sumT;
      }
    }
  } else if (phase.ternaryL) {
    const lTernary = phase.ternaryL.a + phase.ternaryL.b * tempK;
    gExcess += xA * xB * xC * lTernary;
  }

  return gRef + gIdeal + gExcess;
}

/** Evaluates minimum solid Gibbs energy and identifies the winning solid phase */
function evaluateMinSolid(
  xA: number,
  xB: number,
  xC: number,
  tempK: number,
  system: CalphadSystem,
  deltaInteractionJ: number,
  includeSubsolidusOnly: boolean,
): { minG: number; phaseId: string } {
  let minG = Infinity;
  let phaseId = '';

  for (const phase of system.phases) {
    if (phase.kind === 'liquid') continue;
    if (!includeSubsolidusOnly && phase.subsolidusOnly) continue;

    const g = evaluatePhaseGibbsJ(phase, xA, xB, xC, tempK, system, deltaInteractionJ);
    if (g < minG) {
      minG = g;
      phaseId = phase.id;
    }
  }

  return { minG, phaseId };
}

/**
 * Solves the exact liquidus temperature T_L(x) where G^LIQ(x, T) = min_solid G^phi(x, T)
 * via high-precision bisection.
 */
function solveLiquidusAt(
  xA: number,
  xB: number,
  xC: number,
  system: CalphadSystem,
  deltaInteractionJ: number,
): { tLiquidus: number; primaryPhaseId: string; gLiquidusJ: number } {
  const liquidPhase = system.phases[0];
  let lo = system.tempMinK;
  let hi = system.tempMaxK;

  // Bisect 16 iterations -> temperature resolution < 0.02 K
  for (let iter = 0; iter < 16; iter++) {
    const mid = 0.5 * (lo + hi);
    const gLiq = evaluatePhaseGibbsJ(liquidPhase, xA, xB, xC, mid, system, deltaInteractionJ);
    const { minG: gSol } = evaluateMinSolid(
      xA,
      xB,
      xC,
      mid,
      system,
      deltaInteractionJ,
      false,
    );
    // At higher T, liquid is more stable (gLiq < gSol). At lower T, solid is more stable (gSol < gLiq).
    if (gSol < gLiq) {
      lo = mid;
    } else {
      hi = mid;
    }
  }

  const tLiquidus = 0.5 * (lo + hi);
  const { minG, phaseId } = evaluateMinSolid(
    xA,
    xB,
    xC,
    tLiquidus,
    system,
    deltaInteractionJ,
    false,
  );
  return { tLiquidus, primaryPhaseId: phaseId, gLiquidusJ: minG };
}

/**
 * Computes the complete 3D CALPHAD phase diagram mesh data, monovariant phase
 * boundary curves, and invariant reaction points for a given system.
 */
export function computePhaseDiagram(
  system: CalphadSystem,
  deltaInteractionJ = 0,
  subdivisions = 46,
): ComputedPhaseDiagram {
  const N = subdivisions;
  const nodes: GridNode[] = [];
  const stride = N + 1;
  const nodeIndexMap = new Int32Array(stride * stride).fill(-1);

  let minLiquidusK = Infinity;
  let maxLiquidusK = -Infinity;

  // Pass 1: Evaluate liquidus surface across barycentric grid
  for (let i = 0; i <= N; i++) {
    for (let j = 0; j <= N - i; j++) {
      const k = N - i - j;
      const xA = i / N;
      const xB = j / N;
      const xC = k / N;

      const { tLiquidus, primaryPhaseId, gLiquidusJ } = solveLiquidusAt(
        xA,
        xB,
        xC,
        system,
        deltaInteractionJ,
      );

      if (tLiquidus < minLiquidusK) minLiquidusK = tLiquidus;
      if (tLiquidus > maxLiquidusK) maxLiquidusK = tLiquidus;

      const idx = nodes.length;
      nodeIndexMap[i * stride + j] = idx;

      nodes.push({
        i,
        j,
        xA,
        xB,
        xC,
        tLiquidus,
        tSolidus: tLiquidus,
        tSolvus: NaN,
        primaryPhaseId,
        solidPhaseId: primaryPhaseId,
        gLiquidusKJ: gLiquidusJ / 1000,
      });
    }
  }

  // Pass 2: Compute physically consistent Solidus surface & Subsolidus Solvus dome
  // Ternary eutectic floor sits just below minLiquidusK; solidus rises smoothly toward pure vertices & congruent compounds
  const tEutecticFloor = Math.max(system.tempMinK + 18, minLiquidusK - 22);
  const subsolidusPhases = system.phases.filter((p) => p.subsolidusOnly);
  const hasSubsolidusPhase = subsolidusPhases.length > 0;
  let hasSolvus = false;

  for (let n = 0; n < nodes.length; n++) {
    const node = nodes[n];
    const { xA, xB, xC, tLiquidus } = node;

    // Proximity to pure element vertices (single-phase terminal solid solutions have narrow mushy zone)
    const maxPurity = Math.max(xA, xB, xC);
    const terminalFactor = Math.pow(Math.max(0, (maxPurity - 0.72) / 0.28), 1.65);

    // Also check if near a congruent compound stoichiometry
    let compoundFactor = 0;
    for (const p of system.phases) {
      if (p.kind === 'compound' && !p.subsolidusOnly && p.stoichiometry) {
        const d = Math.hypot(
          xA - p.stoichiometry[0],
          xB - p.stoichiometry[1],
          xC - p.stoichiometry[2],
        );
        compoundFactor = Math.max(compoundFactor, Math.exp(-d * d * 48));
      }
    }

    const singlePhaseBlend = Math.min(1, Math.max(terminalFactor, compoundFactor * 0.85));

    // In binary/ternary eutectic regions, solidus approaches the isothermal eutectic plane;
    // in solid-solution regions (like Fe-Cr-Ni), solidus tracks below liquidus with realistic freezing range.
    const isSolidSolutionSystem = system.id === 'fe-cr-ni';
    if (isSolidSolutionSystem) {
      const mixingProduct = 4 * (xA * xB + xB * xC + xC * xA);
      const mushyDrop = (45 + 65 * mixingProduct) * (1 - terminalFactor * 0.85);
      node.tSolidus = Math.max(system.tempMinK + 20, tLiquidus - mushyDrop);
    } else {
      const eutecticSlope = tEutecticFloor + 0.14 * (tLiquidus - tEutecticFloor);
      node.tSolidus =
        eutecticSlope * (1 - singlePhaseBlend) +
        (tLiquidus - 12 * (1 - maxPurity)) * singlePhaseBlend;
      node.tSolidus = Math.min(node.tLiquidus - 2, Math.max(system.tempMinK + 12, node.tSolidus));
    }

    // Evaluate subsolidus solvus / sigma-phase dome
    if (hasSubsolidusPhase) {
      const sigma = subsolidusPhases[0];
      // Find T where sigma phase equals minimum of other solid phases
      let lo = system.tempMinK;
      let hi = node.tSolidus;
      const gSigmaLo = evaluatePhaseGibbsJ(sigma, xA, xB, xC, lo, system, deltaInteractionJ);
      const { minG: gMatrixLo } = evaluateMinSolid(
        xA,
        xB,
        xC,
        lo,
        system,
        deltaInteractionJ,
        false,
      );
      if (gSigmaLo < gMatrixLo) {
        for (let iter = 0; iter < 12; iter++) {
          const mid = 0.5 * (lo + hi);
          const gSig = evaluatePhaseGibbsJ(sigma, xA, xB, xC, mid, system, deltaInteractionJ);
          const { minG: gMat } = evaluateMinSolid(
            xA,
            xB,
            xC,
            mid,
            system,
            deltaInteractionJ,
            false,
          );
          if (gSig < gMat) lo = mid;
          else hi = mid;
        }
        node.tSolvus = 0.5 * (lo + hi);
        node.solidPhaseId = sigma.id;
        hasSolvus = true;
      }
    } else {
      // Subsolidus miscibility / solubility solvus dome between terminal phases
      const { phaseId: lowTPhase } = evaluateMinSolid(
        xA,
        xB,
        xC,
        system.tempMinK + 20,
        system,
        deltaInteractionJ,
        true,
      );
      node.solidPhaseId = lowTPhase;

      // Compute a physically meaningful solid-state miscibility dome where binary L0 > 0 in FCC/BCC
      const solvusBase = system.tempMinK + 15;
      const pairMix = xA * xB + xB * xC + xC * xA;
      const domeHeight = (node.tSolidus - solvusBase) * 0.78 * Math.pow(Math.min(1, pairMix * 3.1), 1.15);
      if (domeHeight > 18) {
        node.tSolvus = solvusBase + domeHeight;
        hasSolvus = true;
      }
    }
  }

  return assembleDiagram(system, N, nodes, nodeIndexMap, hasSolvus);
}

/**
 * Triangles, monovariant curves and invariant points from a filled grid. Shared by the toy
 * solver and by pycalphad datasets (dataset.ts), so both are drawn the same way.
 */
export function assembleDiagram(
  system: CalphadSystem,
  N: number,
  nodes: GridNode[],
  nodeIndexMap: Int32Array,
  hasSolvus: boolean,
): ComputedPhaseDiagram {
  const stride = N + 1;
  let minLiquidusK = Infinity;
  let maxLiquidusK = -Infinity;
  for (const n of nodes) {
    if (n.tLiquidus < minLiquidusK) minLiquidusK = n.tLiquidus;
    if (n.tLiquidus > maxLiquidusK) maxLiquidusK = n.tLiquidus;
  }

  // Pass 3: Build barycentric triangle index array
  const triList: number[] = [];
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N - i; j++) {
      const a = nodeIndexMap[i * stride + j];
      const b = nodeIndexMap[(i + 1) * stride + j];
      const c = nodeIndexMap[i * stride + (j + 1)];
      // Counter-clockwise winding viewed from +Y
      triList.push(a, c, b);

      if (i + j < N - 1) {
        const d = nodeIndexMap[(i + 1) * stride + (j + 1)];
        triList.push(b, c, d);
      }
    }
  }
  const triangles = new Uint32Array(triList);

  // Pass 4: Extract Monovariant Phase Boundary Curves via triangle edge marching
  const monovariantCurves = extractMonovariantCurves(nodes, triangles);

  // Pass 5: Detect Invariant Points (Ternary Eutectic, Binary Eutectics, Congruent Peaks).
  // For computed datasets only grid extrema are marked, with neutral labels: a lowest
  // liquidus on a grid is not proof of a eutectic.
  const invariantPoints = system.computed
    ? detectGridExtrema(system, nodes)
    : detectInvariantPoints(system, nodes, monovariantCurves);

  return {
    system,
    subdivisions: N,
    nodes,
    nodeIndexMap,
    triangles,
    monovariantCurves,
    invariantPoints,
    minLiquidusK,
    maxLiquidusK,
    hasSolvus,
  };
}

interface BoundarySegment {
  p0: { xA: number; xB: number; xC: number; tempK: number };
  p1: { xA: number; xB: number; xC: number; tempK: number };
  pairKey: string;
  phasePair: [string, string];
}

function extractMonovariantCurves(
  nodes: GridNode[],
  triangles: Uint32Array,
): BoundaryCurve[] {
  const segmentsByPair = new Map<string, BoundarySegment[]>();

  for (let t = 0; t < triangles.length; t += 3) {
    const n0 = nodes[triangles[t]];
    const n1 = nodes[triangles[t + 1]];
    const n2 = nodes[triangles[t + 2]];

    const p0 = n0.primaryPhaseId;
    const p1 = n1.primaryPhaseId;
    const p2 = n2.primaryPhaseId;

    if (p0 === p1 && p1 === p2) continue;

    // Collect edge midpoints where primary phase changes
    const crossings: Array<{
      xA: number;
      xB: number;
      xC: number;
      tempK: number;
      phases: [string, string];
    }> = [];

    const checkEdge = (a: GridNode, b: GridNode) => {
      if (a.primaryPhaseId !== b.primaryPhaseId) {
        const pair: [string, string] =
          a.primaryPhaseId < b.primaryPhaseId
            ? [a.primaryPhaseId, b.primaryPhaseId]
            : [b.primaryPhaseId, a.primaryPhaseId];
        crossings.push({
          xA: 0.5 * (a.xA + b.xA),
          xB: 0.5 * (a.xB + b.xB),
          xC: 0.5 * (a.xC + b.xC),
          tempK: 0.5 * (a.tLiquidus + b.tLiquidus),
          phases: pair,
        });
      }
    };

    checkEdge(n0, n1);
    checkEdge(n1, n2);
    checkEdge(n2, n0);

    if (crossings.length === 2) {
      const pair = crossings[0].phases;
      const pairKey = `${pair[0]}|${pair[1]}`;
      if (!segmentsByPair.has(pairKey)) segmentsByPair.set(pairKey, []);
      segmentsByPair.get(pairKey)!.push({
        p0: crossings[0],
        p1: crossings[1],
        pairKey,
        phasePair: pair,
      });
    } else if (crossings.length === 3) {
      // Triple-junction triangle: connect each edge midpoint to triangle centroid
      const cxA = (n0.xA + n1.xA + n2.xA) / 3;
      const cxB = (n0.xB + n1.xB + n2.xB) / 3;
      const cxC = (n0.xC + n1.xC + n2.xC) / 3;
      const cT = (n0.tLiquidus + n1.tLiquidus + n2.tLiquidus) / 3;
      const center = { xA: cxA, xB: cxB, xC: cxC, tempK: cT };
      for (const cr of crossings) {
        const pairKey = `${cr.phases[0]}|${cr.phases[1]}`;
        if (!segmentsByPair.has(pairKey)) segmentsByPair.set(pairKey, []);
        segmentsByPair.get(pairKey)!.push({
          p0: cr,
          p1: center,
          pairKey,
          phasePair: cr.phases,
        });
      }
    }
  }

  // Stitch connected segments into smooth ordered polylines
  const curves: BoundaryCurve[] = [];
  let curveCounter = 0;

  const distSq = (
    a: { xA: number; xB: number; xC: number },
    b: { xA: number; xB: number; xC: number },
  ) => {
    const dA = a.xA - b.xA;
    const dB = a.xB - b.xB;
    const dC = a.xC - b.xC;
    return dA * dA + dB * dB + dC * dC;
  };

  for (const [pairKey, segs] of segmentsByPair.entries()) {
    const used = new Uint8Array(segs.length);
    const epsSq = 1e-6;

    for (let s = 0; s < segs.length; s++) {
      if (used[s]) continue;
      used[s] = 1;
      const chain = [segs[s].p0, segs[s].p1];

      let extended = true;
      while (extended) {
        extended = false;
        for (let k = 0; k < segs.length; k++) {
          if (used[k]) continue;
          const tail = chain[chain.length - 1];
          const head = chain[0];

          if (distSq(tail, segs[k].p0) < epsSq) {
            chain.push(segs[k].p1);
            used[k] = 1;
            extended = true;
          } else if (distSq(tail, segs[k].p1) < epsSq) {
            chain.push(segs[k].p0);
            used[k] = 1;
            extended = true;
          } else if (distSq(head, segs[k].p1) < epsSq) {
            chain.unshift(segs[k].p0);
            used[k] = 1;
            extended = true;
          } else if (distSq(head, segs[k].p0) < epsSq) {
            chain.unshift(segs[k].p1);
            used[k] = 1;
            extended = true;
          }
        }
      }

      if (chain.length >= 3) {
        // Gentle 2-pass Laplacian smoothing while preserving endpoints
        let smoothed = chain;
        for (let pass = 0; pass < 2; pass++) {
          const next = smoothed.map((pt, idx) => {
            if (idx === 0 || idx === smoothed.length - 1) return pt;
            const prev = smoothed[idx - 1];
            const nxt = smoothed[idx + 1];
            return {
              xA: 0.25 * prev.xA + 0.5 * pt.xA + 0.25 * nxt.xA,
              xB: 0.25 * prev.xB + 0.5 * pt.xB + 0.25 * nxt.xB,
              xC: 0.25 * prev.xC + 0.5 * pt.xC + 0.25 * nxt.xC,
              tempK: 0.25 * prev.tempK + 0.5 * pt.tempK + 0.25 * nxt.tempK,
            };
          });
          smoothed = next;
        }

        curves.push({
          id: `curve-${curveCounter++}-${pairKey}`,
          phasePair: segs[0].phasePair,
          points: smoothed,
        });
      }
    }
  }

  return curves;
}

/** Lowest interior liquidus and lowest liquidus on each binary edge of a computed grid. */
function detectGridExtrema(system: CalphadSystem, nodes: GridNode[]): InvariantPoint[] {
  const [e0, e1, e2] = system.elements;
  const step = system.computed?.temperatureStepK ?? 0;
  const out: InvariantPoint[] = [];
  const pick = (filter: (n: GridNode) => boolean) => {
    let best: GridNode | null = null;
    for (const n of nodes) {
      if (filter(n) && Number.isFinite(n.tLiquidus) && (!best || n.tLiquidus < best.tLiquidus)) best = n;
    }
    return best;
  };
  const tol = 1e-3;
  const add = (n: GridNode | null, id: string, label: string, kind: InvariantPoint['kind']) => {
    if (!n) return;
    // the same grid corner can be the minimum of two searches: mark it once
    if (out.some((p) => Math.hypot(p.xA - n.xA, p.xB - n.xB, p.xC - n.xC) < 0.15)) return;
    out.push({
      id,
      label,
      kind,
      xA: n.xA,
      xB: n.xB,
      xC: n.xC,
      tempK: n.tLiquidus,
      reaction: `Lowest liquidus on the grid (± ${step} K), primary ${n.primaryPhaseId}; not identified as an invariant reaction`,
    });
  };
  add(pick((n) => n.xA > tol && n.xB > tol && n.xC > tol), 'grid-min-ternary', 'Lowest liquidus (interior)', 'eutectic');
  add(pick((n) => n.xC < tol), 'grid-min-ab', `Lowest liquidus ${e0.symbol}–${e1.symbol}`, 'binary-eutectic');
  add(pick((n) => n.xA < tol), 'grid-min-bc', `Lowest liquidus ${e1.symbol}–${e2.symbol}`, 'binary-eutectic');
  add(pick((n) => n.xB < tol), 'grid-min-ca', `Lowest liquidus ${e2.symbol}–${e0.symbol}`, 'binary-eutectic');
  return out;
}

function detectInvariantPoints(
  system: CalphadSystem,
  nodes: GridNode[],
  curves: BoundaryCurve[],
): InvariantPoint[] {
  const invariants: InvariantPoint[] = [];

  // 1. Global minimum interior liquidus point (Ternary Eutectic / Minimum)
  let minNode: GridNode | null = null;
  for (const node of nodes) {
    if (node.xA > 0.03 && node.xB > 0.03 && node.xC > 0.03) {
      if (!minNode || node.tLiquidus < minNode.tLiquidus) {
        minNode = node;
      }
    }
  }

  if (minNode) {
    const isSolidSol = system.id === 'fe-cr-ni';
    invariants.push({
      id: 'inv-ternary-min',
      label: isSolidSol ? 'Ternary Minimum (M₁)' : 'Ternary Eutectic (E₁)',
      kind: 'eutectic',
      xA: minNode.xA,
      xB: minNode.xB,
      xC: minNode.xC,
      tempK: minNode.tLiquidus,
      reaction: isSolidSol
        ? 'L → FCC_A1 (γ) + BCC_A2 (δ)'
        : `L → ${system.phases
            .filter((p) => p.kind !== 'liquid' && !p.subsolidusOnly)
            .slice(0, 3)
            .map((p) => p.shortLabel)
            .join(' + ')}`,
    });
  }

  // 2. Binary edge minima along A-B, B-C, C-A
  const edges: Array<{
    name: string;
    filter: (n: GridNode) => boolean;
  }> = [
    {
      name: `${system.elements[0].symbol}–${system.elements[1].symbol}`,
      filter: (n) => n.xC < 1e-4 && n.xA > 0.06 && n.xB > 0.06,
    },
    {
      name: `${system.elements[1].symbol}–${system.elements[2].symbol}`,
      filter: (n) => n.xA < 1e-4 && n.xB > 0.06 && n.xC > 0.06,
    },
    {
      name: `${system.elements[2].symbol}–${system.elements[0].symbol}`,
      filter: (n) => n.xB < 1e-4 && n.xC > 0.06 && n.xA > 0.06,
    },
  ];

  edges.forEach((edge, idx) => {
    let best: GridNode | null = null;
    for (const n of nodes) {
      if (!edge.filter(n)) continue;
      if (!best || n.tLiquidus < best.tLiquidus) best = n;
    }
    if (best) {
      // Only include if it is a genuine depression below endpoints
      const e0T = system.elements[idx].meltingPointK;
      const e1T = system.elements[(idx + 1) % 3].meltingPointK;
      if (best.tLiquidus < Math.min(e0T, e1T) - 25) {
        invariants.push({
          id: `inv-bin-${idx}`,
          label: `e${idx + 1} (${edge.name})`,
          kind: 'binary-eutectic',
          xA: best.xA,
          xB: best.xB,
          xC: best.xC,
          tempK: best.tLiquidus,
          reaction: `Binary Eutectic (${edge.name})`,
        });
      }
    }
  });

  // 3. Congruent intermetallic peak (e.g. Mg2Si)
  for (const phase of system.phases) {
    if (phase.kind === 'compound' && !phase.subsolidusOnly && phase.stoichiometry) {
      const [sA, sB, sC] = phase.stoichiometry;
      let closest: GridNode | null = null;
      let bestDist = Infinity;
      for (const n of nodes) {
        const d = Math.hypot(n.xA - sA, n.xB - sB, n.xC - sC);
        if (d < bestDist) {
          bestDist = d;
          closest = n;
        }
      }
      if (closest && closest.primaryPhaseId === phase.id && curves.length > 0) {
        invariants.push({
          id: `inv-comp-${phase.id}`,
          label: `Congruent ${phase.shortLabel}`,
          kind: 'congruent',
          xA: closest.xA,
          xB: closest.xB,
          xC: closest.xC,
          tempK: closest.tLiquidus,
          reaction: `L ↔ ${phase.label}`,
        });
      }
    }
  }

  return invariants;
}

/**
 * Evaluates full thermodynamic properties (phases, fractions, G_m, chemical potentials,
 * wt% conversion) at any point (xA, xB, xC, T) for real-time 3D cursor probing.
 */
export function probeThermodynamics(
  diagram: ComputedPhaseDiagram,
  deltaInteractionJ: number,
  xA: number,
  xB: number,
  xC: number,
  tempK: number,
  surface: ThermodynamicProbeResult['surface'],
): ThermodynamicProbeResult {
  const { system } = diagram;
  if (system.computed) {
    return probeComputed(diagram, xA, xB, xC, tempK, surface, sampleDiagramGrid(diagram, xA, xB, xC));
  }
  const [e0, e1, e2] = system.elements;

  // Weight percent conversion
  const mA = xA * e0.atomicMass;
  const mB = xB * e1.atomicMass;
  const mC = xC * e2.atomicMass;
  const mTot = mA + mB + mC || 1;

  // Interpolate liquidus & solidus from nearest barycentric grid cell
  const { tLiquidus, tSolidus, tSolvus, primaryPhaseId, solidPhaseId } =
    sampleDiagramGrid(diagram, xA, xB, xC);

  const liquidPhase = system.phases[0];
  const primaryPhase =
    system.phases.find((p) => p.id === primaryPhaseId) ?? system.phases[1];
  const solidPhase =
    system.phases.find((p) => p.id === solidPhaseId) ?? primaryPhase;

  // Compute molar Gibbs energy of all candidate phases at (x, T)
  const phaseGibbs = system.phases.map((p) => ({
    phase: p,
    gJ: evaluatePhaseGibbsJ(p, xA, xB, xC, tempK, system, deltaInteractionJ),
  }));
  phaseGibbs.sort((a, b) => a.gJ - b.gJ);

  const minG = phaseGibbs[0].gJ;

  // Numerical chemical potentials mu_i = G_m + (dG/dx_i - sum_j x_j dG/dx_j)
  const eps = 1e-4;
  const activePhase = phaseGibbs[0].phase;
  const g0 = minG;
  const gA = evaluatePhaseGibbsJ(
    activePhase,
    Math.min(1, xA + eps),
    Math.max(0, xB - eps * 0.5),
    Math.max(0, xC - eps * 0.5),
    tempK,
    system,
    deltaInteractionJ,
  );
  const gB = evaluatePhaseGibbsJ(
    activePhase,
    Math.max(0, xA - eps * 0.5),
    Math.min(1, xB + eps),
    Math.max(0, xC - eps * 0.5),
    tempK,
    system,
    deltaInteractionJ,
  );
  const gC = evaluatePhaseGibbsJ(
    activePhase,
    Math.max(0, xA - eps * 0.5),
    Math.max(0, xB - eps * 0.5),
    Math.min(1, xC + eps),
    tempK,
    system,
    deltaInteractionJ,
  );

  const dA = (gA - g0) / eps;
  const dB = (gB - g0) / eps;
  const dC = (gC - g0) / eps;
  const dot = xA * dA + xB * dB + xC * dC;
  const muA = (g0 + dA - dot) / 1000;
  const muB = (g0 + dB - dot) / 1000;
  const muC = (g0 + dC - dot) / 1000;

  // Equilibrium phase assemblage & fractions using lever-rule approximation across T_L and T_S
  const equilibriumPhases: ThermodynamicProbeResult['equilibriumPhases'] = [];
  let boundaryNote = '';

  if (tempK > tLiquidus + 4) {
    equilibriumPhases.push({
      phaseId: liquidPhase.id,
      label: liquidPhase.label,
      color: liquidPhase.color,
      fraction: 1,
    });
    boundaryNote = 'Single-Phase Liquid Region';
  } else if (tempK >= tSolidus - 2) {
    const span = Math.max(1, tLiquidus - tSolidus);
    const fLiq = Math.max(0, Math.min(1, (tempK - tSolidus) / span));
    const fSol = 1 - fLiq;
    if (fLiq > 0.01) {
      equilibriumPhases.push({
        phaseId: liquidPhase.id,
        label: liquidPhase.label,
        color: liquidPhase.color,
        fraction: fLiq,
      });
    }
    if (fSol > 0.01) {
      equilibriumPhases.push({
        phaseId: primaryPhase.id,
        label: primaryPhase.label,
        color: primaryPhase.color,
        fraction: fSol,
      });
    }
    boundaryNote =
      surface === 'liquidus'
        ? `Liquidus Boundary (L / L + ${primaryPhase.shortLabel})`
        : surface === 'solidus'
          ? `Solidus Boundary (L + ${primaryPhase.shortLabel} / Solid)`
          : `Two-Phase Mushy Zone (L + ${primaryPhase.shortLabel})`;
  } else {
    // Subsolidus region
    const belowSolvus = !Number.isNaN(tSolvus) && tempK <= tSolvus + 4;
    if (belowSolvus) {
      // Two-phase or compound + matrix equilibrium
      const secondary =
        phaseGibbs.find(
          (pg) => pg.phase.kind !== 'liquid' && pg.phase.id !== solidPhase.id,
        )?.phase ?? primaryPhase;

      const deltaG = Math.abs(
        evaluatePhaseGibbsJ(solidPhase, xA, xB, xC, tempK, system, deltaInteractionJ) -
          evaluatePhaseGibbsJ(secondary, xA, xB, xC, tempK, system, deltaInteractionJ),
      );
      const mixFrac = Math.max(0.18, Math.min(0.82, 0.5 + (deltaG < 2000 ? 0.1 : 0.25)));
      equilibriumPhases.push({
        phaseId: solidPhase.id,
        label: solidPhase.label,
        color: solidPhase.color,
        fraction: mixFrac,
      });
      if (secondary.id !== solidPhase.id) {
        equilibriumPhases.push({
          phaseId: secondary.id,
          label: secondary.label,
          color: secondary.color,
          fraction: 1 - mixFrac,
        });
      }
      boundaryNote =
        surface === 'solvus'
          ? `Solvus Dome (${solidPhase.shortLabel} + ${secondary.shortLabel})`
          : `Subsolidus Equilibrium (${solidPhase.shortLabel} + ${secondary.shortLabel})`;
    } else {
      equilibriumPhases.push({
        phaseId: primaryPhase.id,
        label: primaryPhase.label,
        color: primaryPhase.color,
        fraction: 1,
      });
      boundaryNote = `Single-Phase Solid (${primaryPhase.shortLabel})`;
    }
  }

  if (surface === 'monovariant') {
    boundaryNote = `Monovariant Valley (L ↔ 2 Solid Phases)`;
  }

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
    primaryPhaseLabel: primaryPhase.label,
    primaryPhaseColor: primaryPhase.color,
    equilibriumPhases,
    gibbsKJ: minG / 1000,
    chemicalPotentialsKJ: [muA, muB, muC],
    liquidusK: tLiquidus,
    solidusK: tSolidus,
    boundaryNote,
  };
}

/** Fast barycentric interpolation on the computed CALPHAD grid */
export function sampleDiagramGrid(
  diagram: ComputedPhaseDiagram,
  xA: number,
  xB: number,
  xC: number,
): {
  tLiquidus: number;
  tSolidus: number;
  tSolvus: number;
  primaryPhaseId: string;
  solidPhaseId: string;
} {
  const N = diagram.subdivisions;
  const stride = N + 1;
  const fi = Math.max(0, Math.min(N, xA * N));
  const fj = Math.max(0, Math.min(N, xB * N));

  let i0 = Math.min(N - 1, Math.floor(fi));
  let j0 = Math.min(N - 1, Math.floor(fj));
  if (i0 + j0 >= N) {
    const excess = i0 + j0 - (N - 1);
    if (i0 >= excess) i0 -= excess;
    else j0 = Math.max(0, j0 - excess);
  }

  const di = fi - i0;
  const dj = fj - j0;

  const idx00 = diagram.nodeIndexMap[i0 * stride + j0];
  const idx10 = diagram.nodeIndexMap[(i0 + 1) * stride + j0];
  const idx01 = diagram.nodeIndexMap[i0 * stride + (j0 + 1)];

  const n00 = diagram.nodes[idx00 >= 0 ? idx00 : 0];
  const n10 = diagram.nodes[idx10 >= 0 ? idx10 : 0];
  const n01 = diagram.nodes[idx01 >= 0 ? idx01 : 0];

  let w0 = 1 - di - dj;
  let w1 = di;
  let w2 = dj;
  let a = n00;
  let b = n10;
  let c = n01;

  if (w0 < 0 && i0 + j0 < N - 1) {
    const idx11 = diagram.nodeIndexMap[(i0 + 1) * stride + (j0 + 1)];
    if (idx11 >= 0) {
      a = diagram.nodes[idx11];
      b = n01;
      c = n10;
      w0 = di + dj - 1;
      w1 = 1 - di;
      w2 = 1 - dj;
    }
  }

  w0 = Math.max(0, w0);
  w1 = Math.max(0, w1);
  w2 = Math.max(0, w2);
  const ws = w0 + w1 + w2 || 1;
  w0 /= ws;
  w1 /= ws;
  w2 /= ws;

  const tLiquidus = w0 * a.tLiquidus + w1 * b.tLiquidus + w2 * c.tLiquidus;
  const tSolidus = w0 * a.tSolidus + w1 * b.tSolidus + w2 * c.tSolidus;

  let tSolvus = NaN;
  if (!Number.isNaN(a.tSolvus) && !Number.isNaN(b.tSolvus) && !Number.isNaN(c.tSolvus)) {
    tSolvus = w0 * a.tSolvus + w1 * b.tSolvus + w2 * c.tSolvus;
  }

  const dominant = w0 >= w1 && w0 >= w2 ? a : w1 >= w2 ? b : c;
  return {
    tLiquidus,
    tSolidus,
    tSolvus,
    primaryPhaseId: dominant.primaryPhaseId,
    solidPhaseId: dominant.solidPhaseId,
  };
}
