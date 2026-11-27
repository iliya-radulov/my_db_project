import { Database, RotateCcw, Upload } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { assembleDiagram, computePhaseDiagram } from './calphad/solver';
import { systemFromDataset } from './calphad/dataset';
import { CALPHAD_SYSTEMS } from './calphad/systems';
import {
  CalphadSystem,
  CameraPresetId,
  LayerVisibility,
  ThermodynamicProbeResult,
} from './calphad/types';
import { ControlDock } from './components/ControlDock';
import {
  PhaseDiagramCanvas,
  PhaseDiagramCanvasHandle,
} from './components/PhaseDiagramCanvas';
import { TdbImportModal } from './components/TdbImportModal';

const DEFAULT_LAYERS: LayerVisibility = {
  liquidus: true,
  solidus: true,
  solvus: true,
  monovariant: true,
  isotherm: true,
  wireframe: false,
  invariants: true,
};

export default function App() {
  const canvasRef = useRef<PhaseDiagramCanvasHandle | null>(null);

  const [systems, setSystems] = useState<CalphadSystem[]>(CALPHAD_SYSTEMS);
  const [hasReplacedDefaults, setHasReplacedDefaults] = useState<boolean>(false);
  const [systemId, setSystemId] = useState<string>(CALPHAD_SYSTEMS[0].id);
  const [importModalOpen, setImportModalOpen] = useState<boolean>(false);

  const activeSystem = useMemo(
    () => systems.find((s) => s.id === systemId) ?? systems[0],
    [systems, systemId],
  );

  const [deltaInteractionJ, setDeltaInteractionJ] = useState<number>(0);
  const [sliceTempK, setSliceTempK] = useState<number>(
    CALPHAD_SYSTEMS[0].defaultSliceK,
  );
  const [explodeFactor, setExplodeFactor] = useState<number>(0);
  const [layers, setLayers] = useState<LayerVisibility>(DEFAULT_LAYERS);
  const [autoRotate, setAutoRotate] = useState<boolean>(false);
  const [activePreset, setActivePreset] = useState<CameraPresetId>('iso');
  const [dockCollapsed, setDockCollapsed] = useState<boolean>(false);

  const [probe, setProbe] = useState<ThermodynamicProbeResult | null>(null);
  const [probePinned, setProbePinned] = useState<boolean>(false);

  // Recompute exact 3D CALPHAD Gibbs equilibria whenever system or Redlich-Kister offset changes
  const diagram = useMemo(() => {
    const c = activeSystem.computed;
    // pycalphad dataset: the grid is already computed; only triangles, curves and labels are built
    if (c) return assembleDiagram(activeSystem, c.subdivisions, c.nodes, c.nodeIndexMap, false);
    return computePhaseDiagram(activeSystem, deltaInteractionJ, 46);
  }, [activeSystem, deltaInteractionJ]);

  const datasetInputRef = useRef<HTMLInputElement | null>(null);
  const [datasetError, setDatasetError] = useState<string | null>(null);

  const handleSelectSystem = useCallback(
    (nextId: string) => {
      const nextSys = systems.find((s) => s.id === nextId) ?? systems[0];
      setSystemId(nextSys.id);
      setDeltaInteractionJ(0);
      setSliceTempK(nextSys.defaultSliceK);
      setProbe(null);
      setProbePinned(false);
    },
    [systems],
  );

  const handleImportSystem = useCallback(
    (newSystem: CalphadSystem, mode: 'replace' | 'add') => {
      if (mode === 'replace') {
        setSystems([newSystem]);
        setHasReplacedDefaults(true);
      } else {
        setSystems((prev) => [...prev, newSystem]);
      }
      setSystemId(newSystem.id);
      setDeltaInteractionJ(0);
      setSliceTempK(newSystem.defaultSliceK);
      setProbe(null);
      setProbePinned(false);
    },
    [],
  );

  const handleDatasetFile = useCallback(
    async (file: File | undefined) => {
      if (!file) return;
      try {
        const sys = systemFromDataset(JSON.parse(await file.text()));
        setDatasetError(null);
        handleImportSystem(sys, 'add');
      } catch (err) {
        setDatasetError(`${file.name}: ${err instanceof Error ? err.message : String(err)}`);
      }
    },
    [handleImportSystem],
  );

  const handleRestoreDefaults = useCallback(() => {
    setSystems(CALPHAD_SYSTEMS);
    setHasReplacedDefaults(false);
    setSystemId(CALPHAD_SYSTEMS[0].id);
    setDeltaInteractionJ(0);
    setSliceTempK(CALPHAD_SYSTEMS[0].defaultSliceK);
    setProbe(null);
    setProbePinned(false);
  }, []);

  const handleToggleLayer = useCallback((key: keyof LayerVisibility) => {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const handleSelectCameraPreset = useCallback((preset: CameraPresetId) => {
    setActivePreset(preset);
    canvasRef.current?.setCameraPreset(preset);
  }, []);

  const handleProbeChange = useCallback(
    (result: ThermodynamicProbeResult | null, pinned: boolean) => {
      setProbe(result);
      setProbePinned(pinned);
    },
    [],
  );

  const handleClearPin = useCallback(() => {
    canvasRef.current?.clearPin();
  }, []);

  const handleExportSnapshot = useCallback(() => {
    const dataUrl = canvasRef.current?.captureSnapshot();
    if (!dataUrl) return;
    const link = document.createElement('a');
    link.download = `calphad-${activeSystem.id}-${Math.round(sliceTempK)}K.png`;
    link.href = dataUrl;
    link.click();
  }, [activeSystem.id, sliceTempK]);

  // Keyboard shortcut 'H' to toggle Zen/Cinema mode (collapse/expand bottom dock)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (importModalOpen) return;
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable)
      ) {
        return;
      }
      if (e.key === 'h' || e.key === 'H') {
        setDockCollapsed((prev) => !prev);
      } else if (e.key === 'Escape' && probePinned) {
        canvasRef.current?.clearPin();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [probePinned, importModalOpen]);

  return (
    <main className="relative w-screen h-screen overflow-hidden bg-[#0B1018]">
      {/* Full-bleed 3D WebGL Viewport (100% unobstructed center) */}
      <PhaseDiagramCanvas
        ref={canvasRef}
        diagram={diagram}
        deltaInteractionJ={deltaInteractionJ}
        sliceTempK={sliceTempK}
        explodeFactor={explodeFactor}
        layers={layers}
        autoRotate={autoRotate}
        onProbeChange={handleProbeChange}
      />

      {/* Minimal Top-Left Spec Header, System Selector & TDB Upload */}
      <header className="fixed top-4 left-5 z-20 flex flex-col gap-1.5 pointer-events-auto">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-base font-semibold tracking-tight text-slate-50 whitespace-nowrap">
            CALPHAD 3D Phase Explorer
          </h1>

          {/* Functional Segmented Alloy System Switcher */}
          <nav
            aria-label="Ternary alloy systems"
            className="inline-flex items-center gap-1 rounded-md border border-slate-700/70 bg-[#0E1522]/94 p-0.5"
          >
            {systems.map((sys) => {
              const active = sys.id === activeSystem.id;
              return (
                <button
                  key={sys.id}
                  type="button"
                  onClick={() => handleSelectSystem(sys.id)}
                  aria-pressed={active}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                    active
                      ? 'bg-amber-500 text-slate-950 font-semibold'
                      : 'text-slate-300 hover:text-white'
                  }`}
                >
                  {sys.name}
                </button>
              );
            })}
          </nav>

          {/* Direct Custom .TDB Importer Trigger */}
          <button
            type="button"
            onClick={() => setImportModalOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-700/80 bg-[#0E1522]/94 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:border-amber-500/70 hover:text-white transition-colors cursor-pointer whitespace-nowrap"
          >
            <Upload className="w-3.5 h-3.5 text-amber-400" />
            <span>Import .TDB</span>
          </button>

          {/* pycalphad dataset written by tools/export_ternary.py */}
          <button
            type="button"
            onClick={() => datasetInputRef.current?.click()}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-700/80 bg-[#0E1522]/94 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:border-emerald-500/70 hover:text-white transition-colors cursor-pointer whitespace-nowrap"
            title="Load a dataset computed with pycalphad (tools/export_ternary.py)"
          >
            <Database className="w-3.5 h-3.5 text-emerald-400" />
            <span>Load dataset</span>
          </button>
          <input
            ref={datasetInputRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            data-testid="dataset-input"
            onChange={(e) => {
              void handleDatasetFile(e.target.files?.[0]);
              e.target.value = '';
            }}
          />

          {hasReplacedDefaults && (
            <button
              type="button"
              onClick={handleRestoreDefaults}
              className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors cursor-pointer whitespace-nowrap"
              title="Restore built-in Sn-Ag-Cu, Al-Mg-Si, and Fe-Cr-Ni systems"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Defaults</span>
            </button>
          )}
        </div>

        {datasetError && (
          <p className="text-[11px] text-rose-300 max-w-xl" role="alert">
            Dataset not loaded: {datasetError}
          </p>
        )}

        {activeSystem.computed ? (
          <p className="text-[11px] text-emerald-300/90 max-w-2xl" data-testid="computed-note">
            Computed with pycalphad {activeSystem.computed.pycalphadVersion} from{' '}
            <span className="font-mono">{activeSystem.computed.tdbFile}</span> (sha256{' '}
            <span className="font-mono">{activeSystem.computed.tdbSha256.slice(0, 12)}…</span>).
            Liquidus/solidus resolution {activeSystem.computed.temperatureStepK} K; values at the
            nearest grid point and temperature.{' '}
            {activeSystem.computed.failedPoints} of {activeSystem.computed.totalPoints} points did not
            converge and {activeSystem.computed.rejectedPoints} were rejected as not the minimum (grey in
            the slice).
            {activeSystem.computed.liquidusAboveRange > 0 &&
              ` Liquidus above ${activeSystem.tempMaxK} K at ${activeSystem.computed.liquidusAboveRange} grid points (drawn at ${activeSystem.tempMaxK} K).`}
            {activeSystem.computed.solidusBelowRange > 0 &&
              ` Solidus below ${activeSystem.tempMinK} K at ${activeSystem.computed.solidusBelowRange} grid points (drawn at ${activeSystem.tempMinK} K).`}
          </p>
        ) : (
        /* What the surfaces are (and are not): keep visible until the pycalphad backend replaces the solver */
        <p
          className="text-[11px] text-amber-300/90 max-w-xl"
          title="The solver finds, at each composition, the temperature where the liquid and the most stable solid have equal Gibbs energy (the T0 surface). A real liquidus needs the common-tangent (convex-hull) construction, so two-phase regions are not shown and temperatures can differ by tens to hundreds of K. Compounds are approximated by narrow parabolas."
        >
          Qualitative demo: surfaces are T₀ (equal-G) surfaces, not equilibrium liquidus or phase boundaries.
        </p>
        )}
        {activeSystem.buildNotes && activeSystem.buildNotes.length > 0 && (
          <ul className="text-[11px] text-amber-200/80 list-disc pl-4 max-w-xl">
            {activeSystem.buildNotes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}

        {/* Clean unboxed scientific metadata */}
        <p className="text-xs text-slate-400">
          <span>{activeSystem.subtitle}</span>
          <span className="mx-2 text-slate-600" aria-hidden="true">
            ·
          </span>
          <span className="font-mono text-[11px] text-slate-400">
            {activeSystem.computed
              ? 'pycalphad dataset'
              : activeSystem.isCustomTdb
                ? 'Custom .TDB'
                : 'Redlich-Kister-Muggianu'}
          </span>
        </p>
      </header>

      {/* Unified Collapsible Bottom Laboratory Dock */}
      <ControlDock
        diagram={diagram}
        sliceTempK={sliceTempK}
        onSliceTempChange={setSliceTempK}
        explodeFactor={explodeFactor}
        onExplodeChange={setExplodeFactor}
        layers={layers}
        onToggleLayer={handleToggleLayer}
        deltaInteractionJ={deltaInteractionJ}
        onDeltaInteractionChange={setDeltaInteractionJ}
        autoRotate={autoRotate}
        onToggleAutoRotate={() => setAutoRotate((v) => !v)}
        activePreset={activePreset}
        onSelectCameraPreset={handleSelectCameraPreset}
        onExportSnapshot={handleExportSnapshot}
        onOpenImportTdb={() => setImportModalOpen(true)}
        probe={probe}
        probePinned={probePinned}
        onClearPin={handleClearPin}
        collapsed={dockCollapsed}
        onToggleCollapsed={() => setDockCollapsed((v) => !v)}
      />

      {/* Custom .TDB File Upload & Ternary Element Selector Modal */}
      <TdbImportModal
        open={importModalOpen}
        hasReplacedDefaults={hasReplacedDefaults}
        onClose={() => setImportModalOpen(false)}
        onImportSystem={handleImportSystem}
        onRestoreDefaults={handleRestoreDefaults}
      />
    </main>
  );
}
