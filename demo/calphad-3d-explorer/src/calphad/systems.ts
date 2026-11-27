import { CalphadSystem } from './types';

/**
 * Curated CALPHAD ternary alloy assessments using SGTE-referenced unary
 * lattice stabilities (relative to LIQUID) and Redlich-Kister-Muggianu
 * excess Gibbs energy polynomials (in J/mol).
 */
export const CALPHAD_SYSTEMS: CalphadSystem[] = [
  {
    id: 'sn-ag-cu',
    name: 'Sn–Ag–Cu',
    subtitle: 'Lead-Free SAC Solder Ternary Eutectic',
    reference: 'NIST / Moon et al. (2000) CALPHAD Assessment',
    elements: [
      {
        symbol: 'Sn',
        name: 'Tin',
        atomicMass: 118.71,
        meltingPointK: 505.08,
        enthalpyFusionJ: 7029,
        color: '#38BDF8',
      },
      {
        symbol: 'Ag',
        name: 'Silver',
        atomicMass: 107.87,
        meltingPointK: 1234.93,
        enthalpyFusionJ: 11297,
        color: '#E2E8F0',
      },
      {
        symbol: 'Cu',
        name: 'Copper',
        atomicMass: 63.546,
        meltingPointK: 1357.77,
        enthalpyFusionJ: 13263,
        color: '#F59E0B',
      },
    ],
    tempMinK: 420,
    tempMaxK: 1450,
    defaultSliceK: 680,
    tunableInteraction: {
      phaseId: 'LIQUID',
      pair: [1, 2],
      label: 'L₀(Ag,Cu) Liquid',
      minDeltaJ: -18000,
      maxDeltaJ: 18000,
    },
    phases: [
      {
        id: 'LIQUID',
        label: 'Liquid (L)',
        shortLabel: 'L',
        crystalStructure: 'Amorphous Melt',
        kind: 'liquid',
        color: '#38BDF8',
        interactions: [
          // Sn-Ag: negative mixing enthalpy
          { pair: [0, 1], a0: -5200, b0: -3.2, a1: -9800, b1: 4.1 },
          // Sn-Cu: strong compound-forming negative mixing
          { pair: [0, 2], a0: -9200, b0: -2.4, a1: -11500, b1: 4.8 },
          // Ag-Cu: positive eutectic miscibility tendency
          { pair: [1, 2], a0: 14800, b0: -1.9, a1: 1200, b1: 0.4 },
        ],
        ternaryL: { a: -6500, b: 2.0 },
      },
      {
        id: 'BCT_A5',
        label: 'β-Sn (BCT_A5)',
        shortLabel: 'β-Sn',
        crystalStructure: 'Tetragonal tI4',
        kind: 'solution',
        color: '#3B82F6',
        unaryStabilities: [
          { a: -7029, b: 13.916 }, // Sn melts at 505.1 K
          { a: -4200, b: 14.5 },   // Metastable Ag in BCT
          { a: -3800, b: 15.2 },   // Metastable Cu in BCT
        ],
        interactions: [
          { pair: [0, 1], a0: 18500, b0: 0 },
          { pair: [0, 2], a0: 21000, b0: 0 },
          { pair: [1, 2], a0: 24000, b0: 0 },
        ],
      },
      {
        id: 'FCC_AG',
        label: 'FCC_A1 (Ag-rich)',
        shortLabel: 'FCC (Ag)',
        crystalStructure: 'Cubic cF4',
        kind: 'solution',
        color: '#94A3B8',
        unaryStabilities: [
          { a: -2900, b: 12.8 },
          { a: -11297, b: 9.148 }, // Ag melts at 1234.9 K
          { a: -13263, b: 9.768 }, // Cu melts at 1357.8 K
        ],
        interactions: [
          { pair: [0, 1], a0: -2800, b0: -1.2, a1: 5200, b1: 0 },
          { pair: [0, 2], a0: -3200, b0: 0.8, a1: 6800, b1: 0 },
          { pair: [1, 2], a0: 33500, b0: -7.6, a1: -3200, b1: 1.1 },
        ],
      },
      {
        id: 'AG3SN',
        label: 'ε-Ag₃Sn (Orthorhombic)',
        shortLabel: 'Ag₃Sn',
        crystalStructure: 'Orthorhombic oP8',
        kind: 'compound',
        color: '#2DD4BF',
        stoichiometry: [0.25, 0.75, 0.0],
        compoundStability: { a: -13600, b: 10.65 },
        homogeneityCurvature: 34000,
      },
      {
        id: 'CU6SN5',
        label: 'η-Cu₆Sn₅ (Hexagonal)',
        shortLabel: 'Cu₆Sn₅',
        crystalStructure: 'Monoclinic / hP4',
        kind: 'compound',
        color: '#F59E0B',
        stoichiometry: [0.455, 0.0, 0.545],
        compoundStability: { a: -15800, b: 11.4 },
        homogeneityCurvature: 29000,
      },
    ],
  },
  {
    id: 'al-mg-si',
    name: 'Al–Mg–Si',
    subtitle: '6xxx Series Precipitation-Hardened Aluminum',
    reference: 'COST 507 / Lacaze & Sundman CALPHAD Assessment',
    elements: [
      {
        symbol: 'Al',
        name: 'Aluminum',
        atomicMass: 26.982,
        meltingPointK: 933.47,
        enthalpyFusionJ: 10711,
        color: '#60A5FA',
      },
      {
        symbol: 'Mg',
        name: 'Magnesium',
        atomicMass: 24.305,
        meltingPointK: 923.0,
        enthalpyFusionJ: 8480,
        color: '#34D399',
      },
      {
        symbol: 'Si',
        name: 'Silicon',
        atomicMass: 28.085,
        meltingPointK: 1687.0,
        enthalpyFusionJ: 50210,
        color: '#A78BFA',
      },
    ],
    tempMinK: 550,
    tempMaxK: 1750,
    defaultSliceK: 1050,
    tunableInteraction: {
      phaseId: 'LIQUID',
      pair: [1, 2],
      label: 'L₀(Mg,Si) Liquid',
      minDeltaJ: -22000,
      maxDeltaJ: 22000,
    },
    phases: [
      {
        id: 'LIQUID',
        label: 'Liquid (L)',
        shortLabel: 'L',
        crystalStructure: 'Amorphous Melt',
        kind: 'liquid',
        color: '#38BDF8',
        interactions: [
          // Al-Mg eutectic liquid
          { pair: [0, 1], a0: -11200, b0: 7.2, a1: -950, b1: 0.4 },
          // Al-Si classic simple eutectic
          { pair: [0, 2], a0: -11340, b0: -1.23, a1: -3530, b1: 1.36 },
          // Mg-Si strong compound-forming melt
          { pair: [1, 2], a0: -38500, b0: 8.6, a1: 4200, b1: -1.5 },
        ],
        ternaryL: { a: -12000, b: 4.0 },
      },
      {
        id: 'FCC_AL',
        label: 'FCC_A1 (α-Al)',
        shortLabel: 'α-Al',
        crystalStructure: 'Cubic cF4',
        kind: 'solution',
        color: '#3B82F6',
        unaryStabilities: [
          { a: -10711, b: 11.474 }, // Al melts at 933.5 K
          { a: -5400, b: 10.6 },
          { a: -8200, b: 13.8 },
        ],
        interactions: [
          { pair: [0, 1], a0: 4970, b0: -3.5, a1: 900, b1: 0.4 },
          { pair: [0, 2], a0: 14500, b0: -4.2 },
          { pair: [1, 2], a0: 26000, b0: 0 },
        ],
      },
      {
        id: 'HCP_MG',
        label: 'HCP_A3 (Mg)',
        shortLabel: 'Mg (HCP)',
        crystalStructure: 'Hexagonal hP2',
        kind: 'solution',
        color: '#10B981',
        unaryStabilities: [
          { a: -5200, b: 12.1 },
          { a: -8480, b: 9.187 }, // Mg melts at 923.0 K
          { a: -4200, b: 15.0 },
        ],
        interactions: [
          { pair: [0, 1], a0: 4200, b0: -2.1 },
          { pair: [0, 2], a0: 28000, b0: 0 },
          { pair: [1, 2], a0: 19500, b0: 0 },
        ],
      },
      {
        id: 'DIAMOND_SI',
        label: 'DIAMOND_A4 (Si)',
        shortLabel: 'Si',
        crystalStructure: 'Cubic cF8',
        kind: 'solution',
        color: '#8B5CF6',
        unaryStabilities: [
          { a: -2400, b: 16.5 },
          { a: -1800, b: 17.0 },
          { a: -50210, b: 29.763 }, // Si melts at 1687.0 K
        ],
        interactions: [
          { pair: [0, 1], a0: 32000, b0: 0 },
          { pair: [0, 2], a0: 26000, b0: 0 },
          { pair: [1, 2], a0: 29000, b0: 0 },
        ],
      },
      {
        id: 'MG2SI',
        label: 'Mg₂Si (Antifluorite)',
        shortLabel: 'Mg₂Si',
        crystalStructure: 'Cubic cF12 (C1)',
        kind: 'compound',
        color: '#F59E0B',
        stoichiometry: [0.0, 0.667, 0.333],
        // Congruent melting peak near 1358 K
        compoundStability: { a: -41200, b: 23.1 },
        homogeneityCurvature: 42000,
      },
    ],
  },
  {
    id: 'fe-cr-ni',
    name: 'Fe–Cr–Ni',
    subtitle: 'Austenitic & Duplex Stainless Steel System',
    reference: 'SGTE / Miettinen (1999) Stainless CALPHAD',
    elements: [
      {
        symbol: 'Fe',
        name: 'Iron',
        atomicMass: 55.845,
        meltingPointK: 1811.0,
        enthalpyFusionJ: 13807,
        color: '#F97316',
      },
      {
        symbol: 'Cr',
        name: 'Chromium',
        atomicMass: 51.996,
        meltingPointK: 2180.0,
        enthalpyFusionJ: 20500,
        color: '#22D3EE',
      },
      {
        symbol: 'Ni',
        name: 'Nickel',
        atomicMass: 58.693,
        meltingPointK: 1728.0,
        enthalpyFusionJ: 17480,
        color: '#A3E635',
      },
    ],
    tempMinK: 850,
    tempMaxK: 2250,
    defaultSliceK: 1550,
    tunableInteraction: {
      phaseId: 'SIGMA',
      pair: [0, 1],
      label: 'ΔG(σ-Phase) Stability',
      minDeltaJ: -6000,
      maxDeltaJ: 6000,
    },
    phases: [
      {
        id: 'LIQUID',
        label: 'Liquid (L)',
        shortLabel: 'L',
        crystalStructure: 'Amorphous Melt',
        kind: 'liquid',
        color: '#38BDF8',
        interactions: [
          { pair: [0, 1], a0: -14550, b0: 6.65 },
          { pair: [0, 2], a0: -16911, b0: 5.16, a1: 10180, b1: -4.15 },
          { pair: [1, 2], a0: 318, b0: -7.33, a1: 16941, b1: -6.37 },
        ],
        ternaryL: { a: -8200, b: 2.8 },
      },
      {
        id: 'BCC_A2',
        label: 'BCC_A2 (δ/α-Ferrite)',
        shortLabel: 'BCC (α/δ)',
        crystalStructure: 'Cubic cI2',
        kind: 'solution',
        color: '#06B6D4',
        unaryStabilities: [
          { a: -13807, b: 7.624 },  // Fe melts at 1811 K
          { a: -20500, b: 9.404 },  // Cr melts at 2180 K
          { a: -8600, b: 8.8 },     // Metastable Ni in BCC
        ],
        interactions: [
          { pair: [0, 1], a0: 20500, b0: -9.68 },
          { pair: [0, 2], a0: -956, b0: -1.28 },
          { pair: [1, 2], a0: 17170, b0: -11.82 },
        ],
      },
      {
        id: 'FCC_A1',
        label: 'FCC_A1 (γ-Austenite)',
        shortLabel: 'FCC (γ)',
        crystalStructure: 'Cubic cF4',
        kind: 'solution',
        color: '#F97316',
        unaryStabilities: [
          { a: -12980, b: 7.21 },   // γ-Fe competitive just below δ-Fe
          { a: -11800, b: 9.1 },    // Cr in FCC
          { a: -17480, b: 10.116 }, // Ni melts at 1728 K
        ],
        interactions: [
          { pair: [0, 1], a0: 10833, b0: -7.477 },
          { pair: [0, 2], a0: -12054, b0: 3.274, a1: 11082, b1: -4.45 },
          { pair: [1, 2], a0: 8030, b0: -12.88, a1: 33080, b1: -16.04 },
        ],
      },
      {
        id: 'SIGMA',
        label: 'σ-Phase (FeCr Tetragonal)',
        shortLabel: 'σ-Phase',
        crystalStructure: 'Tetragonal tP30 (D8b)',
        kind: 'compound',
        color: '#E11D48',
        stoichiometry: [0.48, 0.47, 0.05],
        compoundStability: { a: -21900, b: 13.85 },
        homogeneityCurvature: 22000,
        subsolidusOnly: true,
      },
    ],
  },
];

/**
 * Generates an authentic CALPHAD .TDB (Thermodynamic Database) text block
 * representing the active system and live Redlich-Kister delta offset.
 */
export function formatSystemAsTdb(
  system: CalphadSystem,
  deltaInteractionJ: number,
): string {
  const [e0, e1, e2] = system.elements;
  const lines: string[] = [
    `$ ===============================================================`,
    `$ CALPHAD Thermodynamic Database (.TDB) — ${system.name}`,
    `$ ${system.subtitle}`,
    `$ Ref: ${system.reference}`,
    `$ ===============================================================`,
    ``,
    `ELEMENT ${e0.symbol.padEnd(4)} MASS=${e0.atomicMass.toFixed(3)}  T_MELT=${e0.meltingPointK.toFixed(2)} K !`,
    `ELEMENT ${e1.symbol.padEnd(4)} MASS=${e1.atomicMass.toFixed(3)}  T_MELT=${e1.meltingPointK.toFixed(2)} K !`,
    `ELEMENT ${e2.symbol.padEnd(4)} MASS=${e2.atomicMass.toFixed(3)}  T_MELT=${e2.meltingPointK.toFixed(2)} K !`,
    ``,
  ];

  for (const phase of system.phases) {
    lines.push(`PHASE ${phase.id}  %  1 1.0  !  $ ${phase.label} (${phase.crystalStructure})`);
    if (phase.unaryStabilities) {
      phase.unaryStabilities.forEach((st, idx) => {
        const el = system.elements[idx].symbol;
        const sign = st.b >= 0 ? '+' : '-';
        lines.push(
          `  PARAMETER G(${phase.id},${el};0)  298.15  ${st.a.toFixed(0)} ${sign} ${Math.abs(st.b).toFixed(3)}*T;  3000 N !`,
        );
      });
    }
    if (phase.interactions) {
      for (const inter of phase.interactions) {
        const s0 = system.elements[inter.pair[0]].symbol;
        const s1 = system.elements[inter.pair[1]].symbol;
        const isTuned =
          system.tunableInteraction.phaseId === phase.id &&
          system.tunableInteraction.pair[0] === inter.pair[0] &&
          system.tunableInteraction.pair[1] === inter.pair[1];
        const a0 = inter.a0 + (isTuned ? deltaInteractionJ : 0);
        const sign0 = inter.b0 >= 0 ? '+' : '-';
        lines.push(
          `  PARAMETER L(${phase.id},${s0},${s1};0)  298.15  ${a0.toFixed(0)} ${sign0} ${Math.abs(inter.b0).toFixed(3)}*T;  3000 N !`,
        );
        if (inter.a1 !== undefined && inter.b1 !== undefined) {
          const sign1 = inter.b1 >= 0 ? '+' : '-';
          lines.push(
            `  PARAMETER L(${phase.id},${s0},${s1};1)  298.15  ${inter.a1.toFixed(0)} ${sign1} ${Math.abs(inter.b1).toFixed(3)}*T;  3000 N !`,
          );
        }
      }
    }
    if (phase.ternaryL) {
      const signT = phase.ternaryL.b >= 0 ? '+' : '-';
      lines.push(
        `  PARAMETER L(${phase.id},${e0.symbol},${e1.symbol},${e2.symbol};0)  298.15  ${phase.ternaryL.a.toFixed(0)} ${signT} ${Math.abs(phase.ternaryL.b).toFixed(3)}*T;  3000 N !`,
      );
    }
    if (phase.kind === 'compound' && phase.stoichiometry && phase.compoundStability) {
      const isTuned = system.tunableInteraction.phaseId === phase.id;
      const aC = phase.compoundStability.a + (isTuned ? deltaInteractionJ : 0);
      const signC = phase.compoundStability.b >= 0 ? '+' : '-';
      const stoichStr = phase.stoichiometry
        .map((v, i) => (v > 0 ? `${system.elements[i].symbol}_${v.toFixed(2)}` : null))
        .filter(Boolean)
        .join(':');
      lines.push(
        `  PARAMETER G(${phase.id},${stoichStr};0)  298.15  ${aC.toFixed(0)} ${signC} ${Math.abs(phase.compoundStability.b).toFixed(3)}*T;  3000 N !`,
      );
    }
    lines.push('');
  }

  return lines.join('\n');
}
