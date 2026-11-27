export interface ElementSpec {
  symbol: string;
  name: string;
  atomicMass: number; // g/mol
  meltingPointK: number;
  enthalpyFusionJ: number; // J/mol
  color: string;
}

export interface BinaryInteraction {
  pair: [0 | 1 | 2, 0 | 1 | 2];
  /** L0 = a0 + b0 * T (J/mol) */
  a0: number;
  b0: number;
  /** L1 = a1 + b1 * T (J/mol) */
  a1?: number;
  b1?: number;
}

export interface PhaseDefinition {
  id: string;
  label: string;
  shortLabel: string;
  crystalStructure: string;
  kind: 'liquid' | 'solution' | 'compound';
  color: string;
  /**
   * For solution phases: unary lattice stability relative to LIQUID:
   * G_i^phi - G_i^LIQ = a_i + b_i * T (J/mol).
   * At T_m of pure i in this phase, a_i + b_i * T_m = 0 (with a_i < 0, b_i > 0).
   */
  unaryStabilities?: [
    { a: number; b: number },
    { a: number; b: number },
    { a: number; b: number },
  ];
  interactions?: BinaryInteraction[];
  ternaryL?: { a: number; b: number };
  /**
   * For stoichiometric or narrow-homogeneity intermetallic compounds:
   */
  stoichiometry?: [number, number, number];
  /** Formation Gibbs energy relative to pure LIQUID elements: a + b*T (J/mol) */
  compoundStability?: { a: number; b: number };
  /** Curvature penalty away from exact stoichiometry (J/mol) for smooth CALPHAD sublattice spread */
  homogeneityCurvature?: number;
  /** Whether this phase forms primarily a subsolidus solvus dome rather than primary liquidus */
  subsolidusOnly?: boolean;
  /** Optional full SGTE/TDB piecewise temperature evaluators (J/mol) */
  evalUnaryJ?: [
    (tempK: number) => number,
    (tempK: number) => number,
    (tempK: number) => number,
  ];
  evalInteractions?: Array<{
    pair: [0 | 1 | 2, 0 | 1 | 2];
    order: number;
    eval: (tempK: number) => number;
  }>;
  evalTernary?: Array<{
    order: number;
    eval: (tempK: number) => number;
  }>;
  evalCompoundJ?: (tempK: number) => number;
}

export interface CalphadSystem {
  id: string;
  name: string;
  subtitle: string;
  reference: string;
  elements: [ElementSpec, ElementSpec, ElementSpec];
  tempMinK: number;
  tempMaxK: number;
  defaultSliceK: number;
  phases: PhaseDefinition[];
  /** Interactive tunable parameter metadata for live Redlich-Kister experimentation */
  tunableInteraction: {
    phaseId: string;
    pair: [0 | 1 | 2, 0 | 1 | 2];
    label: string;
    minDeltaJ: number;
    maxDeltaJ: number;
  };
  /** Original uploaded TDB text when imported by the user */
  rawTdb?: string;
  isCustomTdb?: boolean;
  /** Places where the importer had to invent data the TDB did not contain (shown in the header) */
  buildNotes?: string[];
}

export interface GridNode {
  i: number;
  j: number;
  xA: number;
  xB: number;
  xC: number;
  /** Liquidus temperature (K) */
  tLiquidus: number;
  /** Solidus temperature (K) */
  tSolidus: number;
  /** Subsolidus solvus / dome temperature (K), or NaN if none at this composition */
  tSolvus: number;
  /** Primary crystallizing phase ID at liquidus */
  primaryPhaseId: string;
  /** Subsolidus equilibrium phase ID below solidus */
  solidPhaseId: string;
  /** Molar Gibbs energy at liquidus (kJ/mol) */
  gLiquidusKJ: number;
}

export interface BoundaryCurve {
  id: string;
  phasePair: [string, string];
  points: Array<{ xA: number; xB: number; xC: number; tempK: number }>;
}

export interface InvariantPoint {
  id: string;
  label: string;
  kind: 'eutectic' | 'peritectic' | 'congruent' | 'binary-eutectic';
  xA: number;
  xB: number;
  xC: number;
  tempK: number;
  reaction: string;
}

export interface ComputedPhaseDiagram {
  system: CalphadSystem;
  subdivisions: number;
  nodes: GridNode[];
  /** Lookup index (i, j) -> node index in nodes[] */
  nodeIndexMap: Int32Array;
  /** Triangle vertex indices into nodes[] */
  triangles: Uint32Array;
  monovariantCurves: BoundaryCurve[];
  invariantPoints: InvariantPoint[];
  minLiquidusK: number;
  maxLiquidusK: number;
  hasSolvus: boolean;
}

export interface ThermodynamicProbeResult {
  xA: number;
  xB: number;
  xC: number;
  wtA: number;
  wtB: number;
  wtC: number;
  tempK: number;
  tempC: number;
  surface: 'liquidus' | 'solidus' | 'solvus' | 'isotherm' | 'monovariant';
  primaryPhaseLabel: string;
  primaryPhaseColor: string;
  equilibriumPhases: Array<{
    phaseId: string;
    label: string;
    color: string;
    fraction: number;
  }>;
  gibbsKJ: number;
  chemicalPotentialsKJ: [number, number, number];
  liquidusK: number;
  solidusK: number;
  boundaryNote: string;
}

export type CameraPresetId =
  | 'iso'
  | 'top'
  | 'ab'
  | 'bc'
  | 'ca';

export interface LayerVisibility {
  liquidus: boolean;
  solidus: boolean;
  solvus: boolean;
  monovariant: boolean;
  isotherm: boolean;
  wireframe: boolean;
  invariants: boolean;
}
