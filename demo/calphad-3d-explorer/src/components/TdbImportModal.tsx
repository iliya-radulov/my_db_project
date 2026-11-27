import { AlertTriangle, FileText, RotateCcw, Upload, X } from 'lucide-react';
import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from 'react';
import {
  ParsedTdbPreview,
  buildSystemFromTdb,
  inspectTdbFile,
} from '../calphad/tdbParser';
import { CalphadSystem } from '../calphad/types';

interface TdbImportModalProps {
  open: boolean;
  hasReplacedDefaults: boolean;
  onClose: () => void;
  onImportSystem: (system: CalphadSystem, mode: 'replace' | 'add') => void;
  onRestoreDefaults: () => void;
}

const SAMPLE_TDB_TEMPLATE = `$ Sample CALPHAD .TDB — Cu-Ni-Zn Ternary Brass / Nickel-Silver
ELEMENT CU FCC_A1 63.546 5004.0 33.15 !
ELEMENT NI FCC_A1 58.693 4787.0 29.79 !
ELEMENT ZN HCP_A3 65.380 5657.0 41.63 !

FUNCTION GHSERCU 298.15 -7770.458+130.485235*T-24.112392*T*LN(T); 3200 N !
FUNCTION GHSERNI 298.15 -5179.159+117.854*T-22.096*T*LN(T); 3000 N !
FUNCTION GHSERZN 298.15 -7285.787+118.470069*T-23.701314*T*LN(T); 1700 N !

PHASE LIQUID:L % 1 1.0 !
CONSTITUENT LIQUID:L :CU,NI,ZN: !
  PARAMETER G(LIQUID,CU;0) 298.15 +12964.735-9.511904*T+GHSERCU#; 3200 N !
  PARAMETER G(LIQUID,NI;0) 298.15 +16414.686-9.397*T+GHSERNI#; 3000 N !
  PARAMETER G(LIQUID,ZN;0) 298.15 +7157.213-10.29299*T+GHSERZN#; 1700 N !
  PARAMETER L(LIQUID,CU,NI;0) 298.15 +12048.61+1.29893*T; 3000 N !
  PARAMETER L(LIQUID,CU,ZN;0) 298.15 -40695.5+12.653*T; 3000 N !
  PARAMETER L(LIQUID,NI,ZN;0) 298.15 -52000+14.2*T; 3000 N !

PHASE FCC_A1 % 2 1 1 !
CONSTITUENT FCC_A1 :CU,NI,ZN:VA: !
  PARAMETER G(FCC_A1,CU:VA;0) 298.15 +GHSERCU#; 3200 N !
  PARAMETER G(FCC_A1,NI:VA;0) 298.15 +GHSERNI#; 3000 N !
  PARAMETER G(FCC_A1,ZN:VA;0) 298.15 +2969.82-1.56968*T+GHSERZN#; 1700 N !
  PARAMETER L(FCC_A1,CU,NI:VA;0) 298.15 +8047.72+3.42217*T; 3000 N !
  PARAMETER L(FCC_A1,CU,ZN:VA;0) 298.15 -42803.75+10.02258*T; 3000 N !
  PARAMETER L(FCC_A1,NI,ZN:VA;0) 298.15 -46200+11.5*T; 3000 N !

PHASE BCC_A2 % 2 1 3 !
CONSTITUENT BCC_A2 :CU,NI,ZN:VA: !
  PARAMETER G(BCC_A2,CU:VA;0) 298.15 +4017-1.255*T+GHSERCU#; 3200 N !
  PARAMETER G(BCC_A2,NI:VA;0) 298.15 +8715.084-3.556*T+GHSERNI#; 3000 N !
  PARAMETER G(BCC_A2,ZN:VA;0) 298.15 +2886.96-2.5104*T+GHSERZN#; 1700 N !
  PARAMETER L(BCC_A2,CU,ZN:VA;0) 298.15 -51595.87+13.06392*T; 3000 N !
  PARAMETER L(BCC_A2,NI,ZN:VA;0) 298.15 -68500+16.8*T; 3000 N !

PHASE HCP_A3 % 2 1 0.5 !
CONSTITUENT HCP_A3 :CU,NI,ZN:VA: !
  PARAMETER G(HCP_A3,CU:VA;0) 298.15 +600+0.2*T+GHSERCU#; 3200 N !
  PARAMETER G(HCP_A3,NI:VA;0) 298.15 +1046+1.255*T+GHSERNI#; 3000 N !
  PARAMETER G(HCP_A3,ZN:VA;0) 298.15 +GHSERZN#; 1700 N !
  PARAMETER L(HCP_A3,CU,ZN:VA;0) 298.15 -35433.3+5.25*T; 3000 N !
`;

export function TdbImportModal({
  open,
  hasReplacedDefaults,
  onClose,
  onImportSystem,
  onRestoreDefaults,
}: TdbImportModalProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [rawText, setRawText] = useState<string>('');
  const [fileName, setFileName] = useState<string>('custom.tdb');
  const [dragging, setDragging] = useState<boolean>(false);
  const [selectedEls, setSelectedEls] = useState<[string, string, string]>(['', '', '']);
  const [importMode, setImportMode] = useState<'replace' | 'add'>('replace');
  const [buildError, setBuildError] = useState<string | null>(null);

  const preview: ParsedTdbPreview | null = useMemo(() => {
    if (!rawText.trim()) return null;
    try {
      return inspectTdbFile(rawText, fileName);
    } catch {
      return null;
    }
  }, [rawText, fileName]);

  // Auto-select first 3 detected elements whenever a new TDB is loaded
  useEffect(() => {
    if (!preview || preview.elements.length < 3) return;
    const syms = preview.elements.map((e) => e.symbol);
    setSelectedEls((prev) => {
      if (
        prev[0] &&
        prev[1] &&
        prev[2] &&
        syms.includes(prev[0]) &&
        syms.includes(prev[1]) &&
        syms.includes(prev[2]) &&
        new Set(prev).size === 3
      ) {
        return prev;
      }
      return [syms[0], syms[1], syms[2]];
    });
    setBuildError(null);
  }, [preview]);

  // Escape closes modal cleanly
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const readUploadedFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      const content = typeof reader.result === 'string' ? reader.result : '';
      setFileName(file.name);
      setRawText(content);
      setBuildError(null);
    };
    reader.readAsText(file);
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) readUploadedFile(file);
    e.target.value = '';
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) readUploadedFile(file);
  };

  const handleElementPick = (slot: 0 | 1 | 2, sym: string) => {
    setSelectedEls((prev) => {
      const next: [string, string, string] = [...prev];
      next[slot] = sym;
      return next;
    });
    setBuildError(null);
  };

  const uniqueSelectedCount = new Set(selectedEls.filter(Boolean)).size;
  const canBuild =
    preview !== null &&
    preview.elements.length >= 3 &&
    preview.parameterCount > 0 &&
    uniqueSelectedCount === 3;

  const handleSubmit = () => {
    if (!preview || !canBuild) return;
    try {
      const system = buildSystemFromTdb(preview, selectedEls);
      onImportSystem(system, importMode);
      onClose();
    } catch (err) {
      setBuildError(
        err instanceof Error ? err.message : 'Unable to build phase diagram from this TDB.',
      );
    }
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-[#060911]/88 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tdb-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-2xl rounded-lg border border-slate-700/80 bg-[#0E1522] shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3.5">
          <div>
            <h2
              id="tdb-modal-title"
              className="text-base font-semibold text-slate-50"
            >
              Import CALPHAD .TDB File
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Load Thermo-Calc or OpenCalphad databases with ELEMENT, FUNCTION, PHASE, and PARAMETER G/L records.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close import dialog"
            className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="overflow-y-auto px-5 py-4 space-y-4">
          {/* File Dropzone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            className={`rounded-md border border-dashed px-4 py-4 transition-colors flex flex-wrap items-center justify-between gap-3 ${
              dragging
                ? 'border-amber-400 bg-amber-500/10'
                : 'border-slate-700 bg-[#0A0F19]'
            }`}
          >
            <div className="flex items-center gap-3 min-w-0">
              <Upload className="w-5 h-5 text-amber-400 shrink-0" />
              <div className="min-w-0">
                <div className="text-xs font-medium text-slate-200 truncate">
                  {rawText ? fileName : 'Drop a .tdb file here or browse from disk'}
                </div>
                <div className="text-[11px] text-slate-400">
                  Parsed locally in your browser · Supports multi-component TDBs
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".tdb,.TDB,.txt"
                onChange={handleFileChange}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-3 py-1.5 rounded text-xs font-medium bg-slate-800 text-slate-100 hover:bg-slate-700 border border-slate-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                Browse File
              </button>
              <button
                type="button"
                onClick={() => {
                  setFileName('Cu-Ni-Zn_sample.tdb');
                  setRawText(SAMPLE_TDB_TEMPLATE);
                  setBuildError(null);
                }}
                className="px-3 py-1.5 rounded text-xs font-medium text-slate-300 hover:text-white border border-slate-700/80 hover:border-slate-500 transition-colors cursor-pointer whitespace-nowrap"
              >
                Load Sample TDB
              </button>
            </div>
          </div>

          {/* Direct Paste / Edit Area */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label
                htmlFor="tdb-textarea"
                className="text-xs font-medium text-slate-300 flex items-center gap-1.5"
              >
                <FileText className="w-3.5 h-3.5 text-slate-400" />
                <span>TDB Source Text</span>
              </label>
              {rawText && (
                <button
                  type="button"
                  onClick={() => {
                    setRawText('');
                    setFileName('custom.tdb');
                    setBuildError(null);
                  }}
                  className="text-[11px] text-slate-400 hover:text-slate-200 cursor-pointer"
                >
                  Clear
                </button>
              )}
            </div>
            <textarea
              id="tdb-textarea"
              value={rawText}
              onChange={(e) => {
                setRawText(e.target.value);
                setBuildError(null);
              }}
              placeholder="Paste CALPHAD .TDB content here (ELEMENT, FUNCTION, PHASE, CONSTITUENT, PARAMETER G/L)..."
              rows={6}
              spellCheck={false}
              className="w-full rounded-md border border-slate-800 bg-[#070B12] p-3 font-mono text-[11px] leading-relaxed text-slate-200 placeholder:text-slate-600 focus:border-amber-500/70 focus:outline-none select-text"
            />
          </div>

          {/* Live Parse Diagnostics & Ternary Element Picker */}
          {preview && (
            <div className="rounded-md border border-slate-800 bg-[#0A0F19] p-3.5 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="font-medium text-slate-200">Parsed Database Summary</span>
                <span className="font-mono text-[11px] text-slate-400">
                  {preview.elements.length} elements · {preview.phases.length} phases ·{' '}
                  {preview.functionCount} functions · {preview.parameterCount} parameters
                </span>
              </div>

              {/* Ternary Subsystem Element Selectors */}
              {preview.elements.length >= 3 && (
                <div className="grid grid-cols-3 gap-3 pt-1">
                  {(['Corner A', 'Corner B', 'Corner C'] as const).map((label, idx) => {
                    const slot = idx as 0 | 1 | 2;
                    return (
                      <div key={label} className="flex flex-col gap-1">
                        <label
                          htmlFor={`el-slot-${slot}`}
                          className="text-[11px] text-slate-400"
                        >
                          {label}
                        </label>
                        <select
                          id={`el-slot-${slot}`}
                          value={selectedEls[slot]}
                          onChange={(e) => handleElementPick(slot, e.target.value)}
                          className="rounded border border-slate-700 bg-[#0E1522] px-2.5 py-1.5 font-mono text-xs text-slate-100 focus:border-amber-500 focus:outline-none cursor-pointer"
                        >
                          {preview.elements.map((el) => (
                            <option key={el.symbol} value={el.symbol}>
                              {el.displaySymbol} ({el.mass.toFixed(1)})
                            </option>
                          ))}
                        </select>
                      </div>
                    );
                  })}
                </div>
              )}

              {uniqueSelectedCount < 3 && preview.elements.length >= 3 && (
                <p className="text-xs text-amber-400">
                  Select three distinct elements for corners A, B, and C.
                </p>
              )}

              {preview.warnings.length > 0 && (
                <div className="space-y-1 text-xs text-amber-300/90">
                  {preview.warnings.map((w, idx) => (
                    <div key={idx} className="flex items-start gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {buildError && (
            <div className="rounded-md border border-rose-500/40 bg-rose-950/30 px-3.5 py-2.5 text-xs text-rose-200">
              {buildError}
            </div>
          )}

          {/* Replace vs Add Mode Selector */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <div className="inline-flex items-center gap-1 rounded-md border border-slate-800 bg-[#090D16] p-1">
              <button
                type="button"
                onClick={() => setImportMode('replace')}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                  importMode === 'replace'
                    ? 'bg-slate-800 text-slate-50'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Replace Existing Systems
              </button>
              <button
                type="button"
                onClick={() => setImportMode('add')}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                  importMode === 'add'
                    ? 'bg-slate-800 text-slate-50'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Add Alongside Existing
              </button>
            </div>

            {hasReplacedDefaults && (
              <button
                type="button"
                onClick={() => {
                  onRestoreDefaults();
                  onClose();
                }}
                className="inline-flex items-center gap-1.5 text-xs text-slate-300 hover:text-white cursor-pointer whitespace-nowrap"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Restore Built-In Systems</span>
              </button>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-2.5 border-t border-slate-800 bg-[#0A0F19] px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded text-xs font-medium text-slate-300 hover:text-white border border-slate-700/80 hover:border-slate-500 transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!canBuild}
            onClick={handleSubmit}
            className="px-4 py-1.5 rounded text-xs font-semibold bg-amber-500 text-slate-950 hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer whitespace-nowrap"
          >
            {importMode === 'replace' ? 'Replace & Compute 3D Diagram' : 'Add & Compute 3D Diagram'}
          </button>
        </div>
      </div>
    </div>
  );
}
