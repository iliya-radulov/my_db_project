import { CalphadSystem, ElementSpec, PhaseDefinition } from './types';

/**
 * Standard Periodic Table lookup for element names, atomic masses (g/mol),
 * and reference melting points (K) when a TDB omits mass or melting metadata.
 */
const ELEMENT_LOOKUP: Record<
  string,
  { name: string; mass: number; tmK: number; hfJ: number }
> = {
  AG: { name: 'Silver', mass: 107.87, tmK: 1234.93, hfJ: 11297 },
  AL: { name: 'Aluminum', mass: 26.982, tmK: 933.47, hfJ: 10711 },
  AU: { name: 'Gold', mass: 196.97, tmK: 1337.33, hfJ: 12550 },
  B: { name: 'Boron', mass: 10.81, tmK: 2349, hfJ: 50200 },
  BI: { name: 'Bismuth', mass: 208.98, tmK: 544.55, hfJ: 11300 },
  C: { name: 'Carbon', mass: 12.011, tmK: 3823, hfJ: 117000 },
  CA: { name: 'Calcium', mass: 40.078, tmK: 1115, hfJ: 8540 },
  CD: { name: 'Cadmium', mass: 112.41, tmK: 594.22, hfJ: 6190 },
  CE: { name: 'Cerium', mass: 140.12, tmK: 1071, hfJ: 5460 },
  CO: { name: 'Cobalt', mass: 58.933, tmK: 1768, hfJ: 16200 },
  CR: { name: 'Chromium', mass: 51.996, tmK: 2180, hfJ: 20500 },
  CU: { name: 'Copper', mass: 63.546, tmK: 1357.77, hfJ: 13263 },
  FE: { name: 'Iron', mass: 55.845, tmK: 1811, hfJ: 13807 },
  GA: { name: 'Gallium', mass: 69.723, tmK: 302.91, hfJ: 5590 },
  GE: { name: 'Germanium', mass: 72.63, tmK: 1211.4, hfJ: 36940 },
  HF: { name: 'Hafnium', mass: 178.49, tmK: 2506, hfJ: 27200 },
  IN: { name: 'Indium', mass: 114.82, tmK: 429.75, hfJ: 3281 },
  LA: { name: 'Lanthanum', mass: 138.91, tmK: 1193, hfJ: 6200 },
  LI: { name: 'Lithium', mass: 6.94, tmK: 453.65, hfJ: 3000 },
  MG: { name: 'Magnesium', mass: 24.305, tmK: 923, hfJ: 8480 },
  MN: { name: 'Manganese', mass: 54.938, tmK: 1519, hfJ: 12910 },
  MO: { name: 'Molybdenum', mass: 95.95, tmK: 2896, hfJ: 37480 },
  N: { name: 'Nitrogen', mass: 14.007, tmK: 63.15, hfJ: 720 },
  NA: { name: 'Sodium', mass: 22.99, tmK: 370.87, hfJ: 2600 },
  NB: { name: 'Niobium', mass: 92.906, tmK: 2750, hfJ: 30000 },
  ND: { name: 'Neodymium', mass: 144.24, tmK: 1297, hfJ: 7140 },
  NI: { name: 'Nickel', mass: 58.693, tmK: 1728, hfJ: 17480 },
  O: { name: 'Oxygen', mass: 15.999, tmK: 54.36, hfJ: 444 },
  PB: { name: 'Lead', mass: 207.2, tmK: 600.61, hfJ: 4770 },
  PD: { name: 'Palladium', mass: 106.42, tmK: 1828, hfJ: 16740 },
  PT: { name: 'Platinum', mass: 195.08, tmK: 2041.4, hfJ: 22175 },
  RE: { name: 'Rhenium', mass: 186.21, tmK: 3459, hfJ: 60430 },
  SB: { name: 'Antimony', mass: 121.76, tmK: 903.78, hfJ: 19790 },
  SC: { name: 'Scandium', mass: 44.956, tmK: 1814, hfJ: 14100 },
  SI: { name: 'Silicon', mass: 28.085, tmK: 1687, hfJ: 50210 },
  SN: { name: 'Tin', mass: 118.71, tmK: 505.08, hfJ: 7029 },
  TA: { name: 'Tantalum', mass: 180.95, tmK: 3290, hfJ: 36570 },
  TI: { name: 'Titanium', mass: 47.867, tmK: 1941, hfJ: 14150 },
  V: { name: 'Vanadium', mass: 50.942, tmK: 2183, hfJ: 21500 },
  W: { name: 'Tungsten', mass: 183.84, tmK: 3695, hfJ: 52310 },
  Y: { name: 'Yttrium', mass: 88.906, tmK: 1799, hfJ: 11420 },
  ZN: { name: 'Zinc', mass: 65.38, tmK: 692.68, hfJ: 7320 },
  ZR: { name: 'Zirconium', mass: 91.224, tmK: 2128, hfJ: 14000 },
};

const PHASE_PALETTE = [
  '#3B82F6', // Cobalt
  '#10B981', // Emerald
  '#F59E0B', // Amber
  '#8B5CF6', // Violet
  '#EC4899', // Rose
  '#14B8A6', // Teal
  '#F97316', // Orange
  '#6366F1', // Indigo
  '#84CC16', // Lime
  '#06B6D4', // Cyan
];

const ELEMENT_PALETTE = ['#38BDF8', '#E2E8F0', '#F59E0B'];

interface PiecewisePiece {
  tLow: number;
  tHigh: number;
  expr: string;
}

type TempFunc = (tempK: number) => number;

interface ParsedPhaseRaw {
  name: string;
  siteRatios: number[];
  constituents: string[][];
}

interface ParsedParamRaw {
  kind: 'G' | 'L';
  phase: string;
  sublattices: string[][]; // e.g. [['AL', 'MG'], ['VA']]
  order: number;
  pieces: PiecewisePiece[];
}

export interface ParsedTdbPreview {
  fileName: string;
  rawText: string;
  elements: Array<{ symbol: string; displaySymbol: string; mass: number }>;
  phases: Array<{ name: string; siteRatios: number[]; isLiquid: boolean }>;
  functionCount: number;
  parameterCount: number;
  warnings: string[];
  // Internal parsed structures kept for building the chosen ternary subsystem
  _functions: Map<string, PiecewisePiece[]>;
  _phasesMap: Map<string, ParsedPhaseRaw>;
  _params: ParsedParamRaw[];
}

const IGNORED_ELEMENTS = new Set(['/-', 'VA', 'ELECTRON_GAS', 'VACANCY', 'E']);

function toDisplaySymbol(symUpper: string): string {
  if (symUpper.length <= 1) return symUpper;
  return symUpper[0] + symUpper.slice(1).toLowerCase();
}

/**
 * Strips `$` comments and splits a Thermo-Calc / OpenCalphad `.TDB` file
 * into normalized `!`-terminated command statements.
 */
function tokenizeTdbStatements(rawText: string): string[] {
  const cleanedLines = rawText
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => {
      const dollarIdx = line.indexOf('$');
      return dollarIdx >= 0 ? line.slice(0, dollarIdx) : line;
    });

  const joined = cleanedLines.join(' ');
  const statements: string[] = [];
  let current = '';

  for (let i = 0; i < joined.length; i++) {
    const ch = joined[i];
    if (ch === '!') {
      const trimmed = current.trim();
      if (trimmed.length > 0) statements.push(trimmed);
      current = '';
    } else {
      current += ch;
    }
  }
  const leftover = current.trim();
  if (leftover.length > 0) statements.push(leftover);

  return statements;
}

/**
 * Parses a TDB piecewise temperature body:
 * `298.15 expr1 ; 933.47 Y expr2 ; 6000 N`
 */
function parsePiecewiseBody(body: string): PiecewisePiece[] {
  const pieces: PiecewisePiece[] = [];
  const trimmed = body.trim();
  if (!trimmed) return pieces;

  // Match initial low temperature
  const firstMatch = trimmed.match(/^([+-]?\d+(?:\.\d*)?(?:[eEdD][+-]?\d+)?)\s+([\s\S]+)$/);
  if (!firstMatch) return pieces;

  let tLow = Number(firstMatch[1].replace(/[dD]/g, 'E'));
  const rest = firstMatch[2];

  // Split by `;`
  const segments = rest.split(';');
  for (let s = 0; s < segments.length; s++) {
    const seg = segments[s].trim();
    if (!seg) continue;

    if (s === 0) {
      // First segment is purely expression1; its tHigh sits at start of segment 1
      const expr = seg;
      const nextSeg = segments[s + 1]?.trim() ?? '';
      const hiMatch = nextSeg.match(/^([+-]?\d+(?:\.\d*)?(?:[eEdD][+-]?\d+)?)/);
      const tHigh = hiMatch ? Number(hiMatch[1].replace(/[dD]/g, 'E')) : 6000;
      pieces.push({ tLow, tHigh, expr });
      tLow = tHigh;
    } else {
      // Subsequent segment format: `933.47 Y expr2` or `6000 N` (or `6000 N REF0`)
      const m = seg.match(
        /^([+-]?\d+(?:\.\d*)?(?:[eEdD][+-]?\d+)?)\s+([YNyn])\s*([\s\S]*)$/,
      );
      if (!m) continue;
      const flag = m[2].toUpperCase();
      if (flag !== 'Y') break; // End of piecewise definition
      const expr = m[3].trim();
      if (!expr) continue;
      const nextSeg = segments[s + 1]?.trim() ?? '';
      const hiMatch = nextSeg.match(/^([+-]?\d+(?:\.\d*)?(?:[eEdD][+-]?\d+)?)/);
      const tHigh = hiMatch ? Number(hiMatch[1].replace(/[dD]/g, 'E')) : 6000;
      pieces.push({ tLow, tHigh, expr });
      tLow = tHigh;
    }
  }

  return pieces;
}

/**
 * Safe recursive-descent arithmetic evaluator for CALPHAD / SGTE Gibbs energy
 * expressions: supports `+`, `-`, `*`, `/`, `**`, `^`, `LN(...)`, `LOG(...)`,
 * `EXP(...)`, `ABS(...)`, `T`, scientific notation (`E`/`D`), and `FUNC#` refs.
 */
function compileExpression(
  expr: string,
  fnEvalMap: Map<string, TempFunc>,
): TempFunc {
  // Tokenize once at compile time for fast evaluation
  const src = expr.replace(/\s+/g, '').toUpperCase();
  const tokens: string[] = [];
  let i = 0;

  while (i < src.length) {
    const ch = src[i];
    if (ch === '*' && src[i + 1] === '*') {
      tokens.push('**');
      i += 2;
      continue;
    }
    if ('+-*/^(),'.includes(ch)) {
      tokens.push(ch);
      i++;
      continue;
    }
    // Number with optional scientific notation (E or D)
    if (/[0-9.]/.test(ch)) {
      let start = i;
      while (i < src.length && /[0-9.]/.test(src[i])) i++;
      if (i < src.length && (src[i] === 'E' || src[i] === 'D')) {
        i++;
        if (i < src.length && (src[i] === '+' || src[i] === '-')) i++;
        while (i < src.length && /[0-9]/.test(src[i])) i++;
      }
      tokens.push(src.slice(start, i).replace('D', 'E'));
      continue;
    }
    // Identifier or function ref ending in `#`
    if (/[A-Z_]/.test(ch)) {
      let start = i;
      while (i < src.length && /[A-Z0-9_#]/.test(src[i])) i++;
      tokens.push(src.slice(start, i));
      continue;
    }
    i++;
  }

  // Recursive-descent AST compiler -> returns fast closure (T: number) => number
  let pos = 0;
  const peek = () => tokens[pos];
  const consume = () => tokens[pos++];

  function parseAddSub(): TempFunc {
    let left = parseMulDiv();
    while (peek() === '+' || peek() === '-') {
      const op = consume();
      const right = parseMulDiv();
      const l = left;
      const r = right;
      left = op === '+' ? (T) => l(T) + r(T) : (T) => l(T) - r(T);
    }
    return left;
  }

  function parseMulDiv(): TempFunc {
    let left = parseUnary();
    while (peek() === '*' || peek() === '/') {
      const op = consume();
      const right = parseUnary();
      const l = left;
      const r = right;
      left =
        op === '*'
          ? (T) => l(T) * r(T)
          : (T) => {
              const denom = r(T);
              return Math.abs(denom) < 1e-12 ? 0 : l(T) / denom;
            };
    }
    return left;
  }

  function parseUnary(): TempFunc {
    if (peek() === '+') {
      consume();
      return parseUnary();
    }
    if (peek() === '-') {
      consume();
      const inner = parseUnary();
      return (T) => -inner(T);
    }
    return parsePow();
  }

  function parsePow(): TempFunc {
    let base = parsePrimary();
    while (peek() === '**' || peek() === '^') {
      consume();
      const exp = parseUnary();
      const b = base;
      const e = exp;
      base = (T) => Math.pow(b(T), e(T));
    }
    return base;
  }

  function parsePrimary(): TempFunc {
    const tok = peek();
    if (!tok) return () => 0;

    if (tok === '(') {
      consume();
      const inner = parseAddSub();
      if (peek() === ')') consume();
      return inner;
    }

    if (/^[0-9.]/.test(tok)) {
      consume();
      const num = Number(tok);
      return () => (Number.isFinite(num) ? num : 0);
    }

    consume();
    if (tok === 'T') {
      return (T) => T;
    }
    if (tok === 'R') {
      return () => 8.314462618;
    }

    // Built-in math functions: LN(...), LOG(...), EXP(...), ABS(...)
    if (peek() === '(') {
      consume();
      const arg = parseAddSub();
      if (peek() === ')') consume();
      if (tok === 'LN' || tok === 'LOG') {
        return (T) => Math.log(Math.max(1e-6, arg(T)));
      }
      if (tok === 'LOG10') {
        return (T) => Math.log10(Math.max(1e-6, arg(T)));
      }
      if (tok === 'EXP') {
        return (T) => Math.exp(Math.max(-60, Math.min(60, arg(T))));
      }
      if (tok === 'ABS') {
        return (T) => Math.abs(arg(T));
      }
      return arg;
    }

    // Named TDB FUNCTION reference (e.g. GHSERAL# or GHSERAL)
    const refName = tok.endsWith('#') ? tok.slice(0, -1) : tok;
    return (T) => {
      const fn = fnEvalMap.get(refName);
      return fn ? fn(T) : 0;
    };
  }

  const rootFn = parseAddSub();
  return (T: number) => {
    const v = rootFn(T);
    return Number.isFinite(v) ? v : 0;
  };
}

function compilePiecewise(
  pieces: PiecewisePiece[],
  fnEvalMap: Map<string, TempFunc>,
): TempFunc {
  if (pieces.length === 0) return () => 0;
  const compiled = pieces.map((p) => ({
    tLow: p.tLow,
    tHigh: p.tHigh,
    fn: compileExpression(p.expr, fnEvalMap),
  }));

  if (compiled.length === 1) {
    return compiled[0].fn;
  }

  return (T: number) => {
    for (let i = 0; i < compiled.length; i++) {
      if (T <= compiled[i].tHigh || i === compiled.length - 1) {
        return compiled[i].fn(T);
      }
    }
    return compiled[compiled.length - 1].fn(T);
  };
}

/**
 * Inspects a `.TDB` file and extracts all elements, phases, functions, and parameters
 * so the UI can show a live summary and let the user select 3 elements if >3 exist.
 */
export function inspectTdbFile(
  rawText: string,
  fileName = 'custom.tdb',
): ParsedTdbPreview {
  const statements = tokenizeTdbStatements(rawText);
  const warnings: string[] = [];

  const elementsMap = new Map<string, { symbol: string; displaySymbol: string; mass: number }>();
  const functionsMap = new Map<string, PiecewisePiece[]>();
  const phasesMap = new Map<string, ParsedPhaseRaw>();
  const params: ParsedParamRaw[] = [];

  for (const stmt of statements) {
    const upper = stmt.toUpperCase();

    // 1. ELEMENT statement
    if (/^ELEM(?:ENT)?\s+/.test(upper)) {
      const parts = stmt.split(/\s+/);
      const rawSym = (parts[1] ?? '').toUpperCase();
      if (!rawSym || IGNORED_ELEMENTS.has(rawSym)) continue;

      // Support both standard `ELEMENT AL FCC_A1 26.9815 ...` and our `ELEMENT Sn MASS=118.71 ...`
      let mass = ELEMENT_LOOKUP[rawSym]?.mass ?? 55.0;
      const massEq = stmt.match(/MASS\s*=\s*([0-9.]+)/i);
      if (massEq) {
        mass = Number(massEq[1]);
      } else if (parts[3] && /^[0-9.]+(?:[eEdD][+-]?\d+)?$/.test(parts[3])) {
        const parsedMass = Number(parts[3].replace(/[dD]/g, 'E'));
        if (parsedMass > 0.5) mass = parsedMass;
      }

      elementsMap.set(rawSym, {
        symbol: rawSym,
        displaySymbol: toDisplaySymbol(rawSym),
        mass,
      });
      continue;
    }

    // 2. FUNCTION statement
    if (/^FUNC(?:TION)?\s+/.test(upper)) {
      const m = stmt.match(/^FUNC(?:TION)?\s+([A-Za-z0-9_]+)\s+([\s\S]+)$/i);
      if (m) {
        const fnName = m[1].toUpperCase();
        const pieces = parsePiecewiseBody(m[2]);
        if (pieces.length > 0) {
          functionsMap.set(fnName, pieces);
        }
      }
      continue;
    }

    // 3. PHASE statement
    // Format: PHASE <name> <modelFlags> <numSublattices> <r1> <r2> ...
    if (/^PHASE\s+/.test(upper)) {
      const m = stmt.match(/^PHASE\s+([A-Za-z0-9_#:+-]+)\s+\S+\s+(\d+)\s+([\s\S]+)$/i);
      if (m) {
        const rawPhaseName = m[1].toUpperCase().split(':')[0];
        const numSub = Number(m[2]);
        const numTokens = m[3]
          .trim()
          .split(/\s+/)
          .slice(0, numSub)
          .map((t) => Number(t))
          .filter((n) => Number.isFinite(n) && n > 0);
        const siteRatios = numTokens.length === numSub ? numTokens : Array(numSub).fill(1);
        const existing = phasesMap.get(rawPhaseName);
        phasesMap.set(rawPhaseName, {
          name: rawPhaseName,
          siteRatios,
          constituents: existing?.constituents ?? [],
        });
      }
      continue;
    }

    // 4. CONSTITUENT statement
    // Format: CONSTITUENT <phase> :AL,MG,SI:VA:
    if (/^CONST(?:ITUENT)?\s+/.test(upper)) {
      const m = stmt.match(/^CONST(?:ITUENT)?\s+([A-Za-z0-9_#:+-]+)\s+([\s\S]+)$/i);
      if (m) {
        const rawPhaseName = m[1].toUpperCase().split(':')[0];
        const body = m[2].trim();
        const subRaw = body
          .replace(/^:/, '')
          .replace(/:$/, '')
          .split(':')
          .map((s) =>
            s
              .split(',')
              .map((sp) => sp.replace(/%/g, '').trim().toUpperCase())
              .filter(Boolean),
          );
        const existing = phasesMap.get(rawPhaseName);
        if (existing) {
          existing.constituents = subRaw;
        } else {
          phasesMap.set(rawPhaseName, {
            name: rawPhaseName,
            siteRatios: subRaw.map(() => 1),
            constituents: subRaw,
          });
        }
      }
      continue;
    }

    // 5. PARAMETER G(...) or L(...)
    if (/^PARAM(?:ETER)?\s+/.test(upper)) {
      const m = stmt.match(
        /^PARAM(?:ETER)?\s+([GL])\(\s*([^,()]+)\s*,\s*([^;()]+?)(?:\s*;\s*(\d+))?\s*\)\s+([\s\S]+)$/i,
      );
      if (!m) continue;

      const kind = m[1].toUpperCase() as 'G' | 'L';
      const phaseName = m[2].trim().toUpperCase().split(':')[0];
      const speciesExpr = m[3].trim().toUpperCase();
      const order = m[4] ? Number(m[4]) : 0;
      const body = m[5];

      const pieces = parsePiecewiseBody(body);
      if (pieces.length === 0) continue;

      const sublattices = speciesExpr.split(':').map((sub) =>
        sub
          .split(',')
          .map((sp) => sp.replace(/%/g, '').trim())
          .filter(Boolean),
      );

      params.push({
        kind,
        phase: phaseName,
        sublattices,
        order,
        pieces,
      });

      // Ensure phase exists even if PARAMETER appeared without PHASE header
      if (!phasesMap.has(phaseName)) {
        phasesMap.set(phaseName, {
          name: phaseName,
          siteRatios: sublattices.map(() => 1),
          constituents: [],
        });
      }
    }
  }

  // If no explicit ELEMENT statements were present, infer elements from parameters
  if (elementsMap.size === 0) {
    for (const p of params) {
      for (const sub of p.sublattices) {
        for (const sp of sub) {
          const clean = sp.split('_')[0];
          if (!IGNORED_ELEMENTS.has(clean) && /^[A-Z]{1,2}$/.test(clean)) {
            elementsMap.set(clean, {
              symbol: clean,
              displaySymbol: toDisplaySymbol(clean),
              mass: ELEMENT_LOOKUP[clean]?.mass ?? 55.0,
            });
          }
        }
      }
    }
  }

  const elements = Array.from(elementsMap.values());
  const phases = Array.from(phasesMap.values()).map((p) => ({
    name: p.name,
    siteRatios: p.siteRatios,
    isLiquid: p.name.includes('LIQ'),
  }));

  if (elements.length < 3) {
    warnings.push(
      `Detected ${elements.length} element(s). A 3D ternary phase diagram requires at least 3 chemical elements.`,
    );
  }
  if (!phases.some((p) => p.isLiquid)) {
    warnings.push(
      'No LIQUID phase header detected — liquidus will default to ideal melt reference if missing.',
    );
  }
  if (params.length === 0) {
    warnings.push('No PARAMETER G(...) or L(...) records found in this file.');
  }

  return {
    fileName,
    rawText,
    elements,
    phases,
    functionCount: functionsMap.size,
    parameterCount: params.length,
    warnings,
    _functions: functionsMap,
    _phasesMap: phasesMap,
    _params: params,
  };
}

/**
 * Compiles a parsed `.TDB` preview + chosen 3 elements `[A, B, C]` into an active
 * `CalphadSystem` ready for real-time 3D phase diagram calculation.
 */
export function buildSystemFromTdb(
  preview: ParsedTdbPreview,
  selectedSymbolsUpper: [string, string, string],
  customTitle?: string,
): CalphadSystem {
  const [symA, symB, symC] = selectedSymbolsUpper.map((s) => s.toUpperCase()) as [
    string,
    string,
    string,
  ];
  const symToIdx = new Map<string, 0 | 1 | 2>([
    [symA, 0],
    [symB, 1],
    [symC, 2],
  ]);

  // Compile all TDB FUNCTION blocks into callable temperature functions
  const fnEvalMap = new Map<string, TempFunc>();
  for (const [fnName, pieces] of preview._functions.entries()) {
    fnEvalMap.set(fnName, compilePiecewise(pieces, fnEvalMap));
  }

  // Places where data had to be invented because the TDB does not contain it
  const buildNotes: string[] = [];

  // Find GHSER fallback reference functions if available
  const getGhser = (sym: string): TempFunc => {
    const candidates = [`GHSER${sym}`, `G_SER_${sym}`, `GHSER_${sym}`];
    for (const c of candidates) {
      if (fnEvalMap.has(c)) return fnEvalMap.get(c)!;
    }
    buildNotes.push(`No GHSER${sym} function in the file: its reference energy is set to 0.`);
    return () => 0;
  };

  // Group parameters by phase
  const paramsByPhase = new Map<string, ParsedParamRaw[]>();
  for (const p of preview._params) {
    if (!paramsByPhase.has(p.phase)) paramsByPhase.set(p.phase, []);
    paramsByPhase.get(p.phase)!.push(p);
  }

  // Helper: map a parameter's sublattice list (ignoring pure VA sublattices)
  // Returns either a solution unary/binary/ternary entry or a stoichiometric compound entry
  const builtPhases: PhaseDefinition[] = [];
  let colorCounter = 0;

  // Identify LIQUID phase name first
  const liquidPhaseName =
    Array.from(preview._phasesMap.keys()).find((n) => n.includes('LIQ')) ?? 'LIQUID';

  // Ensure LIQUID is built first and sits at phases[0]
  const orderedPhaseNames = [
    liquidPhaseName,
    ...Array.from(preview._phasesMap.keys()).filter((n) => n !== liquidPhaseName),
  ];

  // Collect liquid unary functions first so missing solid unaries can gracefully stay unstable
  const liquidUnaries: [TempFunc | null, TempFunc | null, TempFunc | null] = [
    null,
    null,
    null,
  ];

  for (const phaseName of orderedPhaseNames) {
    const rawPhase = preview._phasesMap.get(phaseName);
    const pParams = paramsByPhase.get(phaseName) ?? [];
    const isLiquid = phaseName === liquidPhaseName;

    if (!isLiquid && pParams.length === 0) continue;

    // Determine active non-VA sublattices and total atom count per formula unit
    const ratios = rawPhase?.siteRatios ?? [1];
    const constits = rawPhase?.constituents ?? [];
    const nonVaIndices: number[] = [];
    for (let s = 0; s < ratios.length; s++) {
      const spList = constits[s] ?? [];
      const isPureVa = spList.length > 0 && spList.every((sp) => IGNORED_ELEMENTS.has(sp));
      if (!isPureVa) nonVaIndices.push(s);
    }

    const totalAtoms =
      nonVaIndices.reduce((acc, idx) => acc + (ratios[idx] ?? 1), 0) || 1;

    // Try classifying as substitutional solution vs stoichiometric compound
    const unaries: [TempFunc | null, TempFunc | null, TempFunc | null] = [
      null,
      null,
      null,
    ];
    const binaryInts: Array<{
      pair: [0 | 1 | 2, 0 | 1 | 2];
      order: number;
      eval: TempFunc;
    }> = [];
    const ternaryInts: Array<{ order: number; eval: TempFunc }> = [];

    // Also track candidate stoichiometric endmembers (for multi-sublattice intermetallics like MG:SI)
    const compoundCandidates: Array<{
      stoich: [number, number, number];
      evalPerAtom: TempFunc;
    }> = [];

    for (const param of pParams) {
      // Strip pure-VA sublattices from the parameter's sublattice species list
      const activeSubs: Array<{ species: string[]; ratio: number }> = [];
      for (let s = 0; s < param.sublattices.length; s++) {
        const sub = param.sublattices[s];
        if (sub.every((sp) => IGNORED_ELEMENTS.has(sp))) continue;
        activeSubs.push({
          species: sub,
          ratio: ratios[s] ?? 1,
        });
      }

      if (activeSubs.length === 0) continue;

      const compiledFn = compilePiecewise(param.pieces, fnEvalMap);

      // Case A: Single active metallic sublattice (e.g. LIQUID, FCC_A1:VA, BCC_A2:VA, HCP_A3:VA)
      if (activeSubs.length === 1) {
        const spList = activeSubs[0].species;
        const scale = 1 / (activeSubs[0].ratio || 1);

        // Check for custom exported compound notation like `SN_0.45:CU_0.55` handled below
        if (param.kind === 'G' && spList.length === 1) {
          const cleanSym = spList[0].split('_')[0];
          const elIdx = symToIdx.get(cleanSym);
          if (elIdx !== undefined) {
            unaries[elIdx] = (T) => compiledFn(T) * scale;
          }
        } else if (param.kind === 'L' && spList.length === 2) {
          const i0 = symToIdx.get(spList[0]);
          const i1 = symToIdx.get(spList[1]);
          if (i0 !== undefined && i1 !== undefined && i0 !== i1) {
            // Preserve sign of odd Redlich-Kister orders if pair is reversed
            const flipped = i0 > i1;
            const pair: [0 | 1 | 2, 0 | 1 | 2] = flipped ? [i1, i0] : [i0, i1];
            const sign = flipped && param.order % 2 === 1 ? -1 : 1;
            binaryInts.push({
              pair,
              order: param.order,
              eval: (T) => sign * compiledFn(T) * scale,
            });
          }
        } else if (param.kind === 'L' && spList.length === 3) {
          const idxs = spList.map((s) => symToIdx.get(s));
          if (idxs.every((v) => v !== undefined)) {
            ternaryInts.push({
              order: param.order,
              eval: (T) => compiledFn(T) * scale,
            });
          }
        }
      } else if (param.kind === 'G') {
        // Case B: Multi-sublattice compound endmember (e.g. MG:SI or AL:FE:SI or SN_0.25:AG_0.75)
        const counts: [number, number, number] = [0, 0, 0];
        let valid = true;
        let sumWeight = 0;

        for (const sub of activeSubs) {
          if (sub.species.length !== 1) {
            valid = false;
            break;
          }
          const token = sub.species[0];
          const underscoreMatch = token.match(/^([A-Z]{1,2})_([0-9.]+)$/);
          if (underscoreMatch) {
            const idx = symToIdx.get(underscoreMatch[1]);
            const w = Number(underscoreMatch[2]);
            if (idx === undefined || !Number.isFinite(w)) {
              valid = false;
              break;
            }
            counts[idx] += w;
            sumWeight += w;
          } else {
            const idx = symToIdx.get(token);
            if (idx === undefined) {
              valid = false;
              break;
            }
            counts[idx] += sub.ratio;
            sumWeight += sub.ratio;
          }
        }

        if (valid && sumWeight > 0) {
          const stoich: [number, number, number] = [
            counts[0] / sumWeight,
            counts[1] / sumWeight,
            counts[2] / sumWeight,
          ];
          const normDivisor =
            activeSubs.some((s) => s.species[0].includes('_')) ? 1 : totalAtoms;
          // If it's a pure unary endmember (e.g. A:A), store as unary too
          if (stoich[0] > 0.999) {
            unaries[0] = (T) => compiledFn(T) / normDivisor;
          } else if (stoich[1] > 0.999) {
            unaries[1] = (T) => compiledFn(T) / normDivisor;
          } else if (stoich[2] > 0.999) {
            unaries[2] = (T) => compiledFn(T) / normDivisor;
          } else {
            compoundCandidates.push({
              stoich,
              evalPerAtom: (T) => compiledFn(T) / normDivisor,
            });
          }
        }
      }
    }

    if (isLiquid) {
      // Fill missing liquid unary with GHSER + estimated fusion Gibbs energy
      const finalUnaries: [TempFunc, TempFunc, TempFunc] = [0, 1, 2].map((idx) => {
        if (unaries[idx]) {
          liquidUnaries[idx] = unaries[idx];
          return unaries[idx]!;
        }
        const sym = selectedSymbolsUpper[idx];
        const ref = ELEMENT_LOOKUP[sym] ?? { tmK: 1200, hfJ: 12000 };
        buildNotes.push(
          `No liquid function for ${sym}: estimated from a built-in melting point ` +
            `(${ref.tmK} K) and enthalpy of fusion (${ref.hfJ} J/mol)` +
            (ELEMENT_LOOKUP[sym] ? '.' : ' (generic default, element not in the table).'),
        );
        const ghser = getGhser(sym);
        const sf = ref.hfJ / ref.tmK;
        const fallback: TempFunc = (T) => ghser(T) + ref.hfJ - sf * T;
        liquidUnaries[idx] = fallback;
        return fallback;
      }) as [TempFunc, TempFunc, TempFunc];

      builtPhases.push({
        id: phaseName,
        label: 'Liquid (L)',
        shortLabel: 'L',
        crystalStructure: 'Amorphous Melt',
        kind: 'liquid',
        color: '#38BDF8',
        evalUnaryJ: finalUnaries,
        evalInteractions: binaryInts,
        evalTernary: ternaryInts,
      });
      continue;
    }

    const unaryCount = unaries.filter(Boolean).length;

    // Decide whether this solid phase acts as a solution phase or stoichiometric compound(s)
    if (unaryCount > 0) {
      // Solution phase: any element absent from this phase receives a +45 kJ/mol destabilization relative to liquid
      const finalUnaries: [TempFunc, TempFunc, TempFunc] = [0, 1, 2].map((idx) => {
        if (unaries[idx]) return unaries[idx]!;
        const liqU = liquidUnaries[idx] ?? getGhser(selectedSymbolsUpper[idx]);
        return (T: number) => liqU(T) + 45000;
      }) as [TempFunc, TempFunc, TempFunc];

      const color = PHASE_PALETTE[colorCounter++ % PHASE_PALETTE.length];
      builtPhases.push({
        id: phaseName,
        label: phaseName.replace(/_/g, ' '),
        shortLabel: phaseName.slice(0, 10),
        crystalStructure: inferCrystalStructure(phaseName),
        kind: 'solution',
        color,
        evalUnaryJ: finalUnaries,
        evalInteractions: binaryInts,
        evalTernary: ternaryInts,
      });
    } else if (compoundCandidates.length > 0) {
      // Pick the most thermodynamically stable endmember (or add distinct stoichiometric compounds)
      // Limit to top 2 distinct compounds per phase to keep visualization clean
      const picked = compoundCandidates.slice(0, 2);
      picked.forEach((cand, cIdx) => {
        const color = PHASE_PALETTE[colorCounter++ % PHASE_PALETTE.length];
        const compId = picked.length > 1 ? `${phaseName}_${cIdx + 1}` : phaseName;
        builtPhases.push({
          id: compId,
          label: formatPhaseLabel(phaseName),
          shortLabel: phaseName.slice(0, 10),
          crystalStructure: inferCrystalStructure(phaseName),
          kind: 'compound',
          color,
          stoichiometry: cand.stoich,
          evalCompoundJ: cand.evalPerAtom,
          homogeneityCurvature: 34000,
          subsolidusOnly: phaseName.includes('SIGMA'),
        });
      });
    }
  }

  // Ensure at least one solid phase exists (if user uploaded an incomplete snippet)
  if (builtPhases.length < 2) {
    throw new Error(
      `No valid solid phase parameters found for ${symA}–${symB}–${symC} in this .TDB file.`,
    );
  }

  // Solve pure-component melting points directly from the compiled TDB functions!
  const liquidPhase = builtPhases[0];
  const solidPhases = builtPhases.slice(1).filter((p) => !p.subsolidusOnly);

  const solvedMeltK: [number, number, number] = [0, 1, 2].map((idx) => {
    const sym = selectedSymbolsUpper[idx];
    const fallbackTm = ELEMENT_LOOKUP[sym]?.tmK ?? 1200;
    const x: [number, number, number] = [
      idx === 0 ? 1 : 0,
      idx === 1 ? 1 : 0,
      idx === 2 ? 1 : 0,
    ];

    const diffAt = (T: number) => {
      const gL = liquidPhase.evalUnaryJ ? liquidPhase.evalUnaryJ[idx](T) : 0;
      let minS = Infinity;
      for (const sp of solidPhases) {
        let gS = Infinity;
        if (sp.kind === 'solution' && sp.evalUnaryJ) {
          gS = sp.evalUnaryJ[idx](T);
        } else if (sp.kind === 'compound' && sp.stoichiometry && sp.evalCompoundJ) {
          const d = Math.hypot(
            x[0] - sp.stoichiometry[0],
            x[1] - sp.stoichiometry[1],
            x[2] - sp.stoichiometry[2],
          );
          if (d < 0.05) gS = sp.evalCompoundJ(T);
        }
        if (gS < minS) minS = gS;
      }
      return gL - minS; // > 0 when solid stable (low T), < 0 when liquid stable (high T)
    };

    // Bracket search from 250 K to 4000 K
    let lo = 250;
    let hi = 4000;
    let found = false;
    for (let t = 300; t <= 3900; t += 100) {
      const d1 = diffAt(t - 100);
      const d2 = diffAt(t);
      if (d1 >= 0 && d2 <= 0) {
        lo = t - 100;
        hi = t;
        found = true;
        break;
      }
    }
    if (!found) return fallbackTm;

    for (let iter = 0; iter < 16; iter++) {
      const mid = 0.5 * (lo + hi);
      if (diffAt(mid) > 0) lo = mid;
      else hi = mid;
    }
    return 0.5 * (lo + hi);
  }) as [number, number, number];

  const minTm = Math.min(...solvedMeltK);
  const maxTm = Math.max(...solvedMeltK);
  const tempMinK = Math.max(250, Math.floor((minTm * 0.62) / 50) * 50);
  const tempMaxK = Math.ceil((maxTm * 1.08 + 60) / 50) * 50;
  const defaultSliceK = Math.round((tempMinK + (tempMaxK - tempMinK) * 0.45) / 10) * 10;

  const elements: [ElementSpec, ElementSpec, ElementSpec] = [0, 1, 2].map((idx) => {
    const sym = selectedSymbolsUpper[idx];
    const parsedEl = preview.elements.find((e) => e.symbol === sym);
    const ref = ELEMENT_LOOKUP[sym];
    return {
      symbol: toDisplaySymbol(sym),
      name: ref?.name ?? toDisplaySymbol(sym),
      atomicMass: parsedEl?.mass ?? ref?.mass ?? 55.0,
      meltingPointK: solvedMeltK[idx],
      enthalpyFusionJ: ref?.hfJ ?? 12000,
      color: ELEMENT_PALETTE[idx],
    };
  }) as [ElementSpec, ElementSpec, ElementSpec];

  // Choose the most impactful liquid binary interaction parameter for the live slider
  const firstLiqInt = liquidPhase.evalInteractions?.[0];
  const tunePair: [0 | 1 | 2, 0 | 1 | 2] = firstLiqInt ? firstLiqInt.pair : [0, 1];
  const tuneLabel = `L₀(${elements[tunePair[0]].symbol},${elements[tunePair[1]].symbol}) Liquid`;

  const displayName =
    customTitle?.trim() ||
    `${elements[0].symbol}–${elements[1].symbol}–${elements[2].symbol}`;

  return {
    id: `tdb-${symA.toLowerCase()}-${symB.toLowerCase()}-${symC.toLowerCase()}-${Date.now()}`,
    name: displayName,
    subtitle: `Imported from ${preview.fileName} (${builtPhases.length} phases)`,
    reference: `User CALPHAD .TDB · ${preview.fileName}`,
    elements,
    tempMinK,
    tempMaxK,
    defaultSliceK,
    phases: builtPhases,
    tunableInteraction: {
      phaseId: liquidPhase.id,
      pair: tunePair,
      label: tuneLabel,
      minDeltaJ: -20000,
      maxDeltaJ: 20000,
    },
    rawTdb: preview.rawText,
    isCustomTdb: true,
    buildNotes,
  };
}

function formatPhaseLabel(name: string): string {
  return name.replace(/_/g, ' ');
}

function inferCrystalStructure(phaseName: string): string {
  const u = phaseName.toUpperCase();
  if (u.includes('FCC')) return 'Cubic cF4';
  if (u.includes('BCC')) return 'Cubic cI2';
  if (u.includes('HCP')) return 'Hexagonal hP2';
  if (u.includes('DIAMOND')) return 'Cubic cF8';
  if (u.includes('BCT')) return 'Tetragonal tI4';
  if (u.includes('SIGMA')) return 'Tetragonal tP30';
  if (u.includes('LAVES')) return 'Laves Phase';
  if (u.includes('LIQ')) return 'Amorphous Melt';
  return 'TDB Assessed Phase';
}
