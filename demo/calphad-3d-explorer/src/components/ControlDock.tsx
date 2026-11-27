import {
  Camera,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Database,
  Layers,
  Pin,
  PinOff,
  RotateCcw,
  SlidersHorizontal,
  Upload,
} from 'lucide-react';
import { useState } from 'react';
import { formatSystemAsTdb } from '../calphad/systems';
import {
  CameraPresetId,
  ComputedPhaseDiagram,
  LayerVisibility,
  ThermodynamicProbeResult,
} from '../calphad/types';

type DockTab = 'slice' | 'camera' | 'calphad' | 'tdb';

interface ControlDockProps {
  diagram: ComputedPhaseDiagram;
  sliceTempK: number;
  onSliceTempChange: (k: number) => void;
  explodeFactor: number;
  onExplodeChange: (v: number) => void;
  layers: LayerVisibility;
  onToggleLayer: (key: keyof LayerVisibility) => void;
  deltaInteractionJ: number;
  onDeltaInteractionChange: (j: number) => void;
  autoRotate: boolean;
  onToggleAutoRotate: () => void;
  activePreset: CameraPresetId;
  onSelectCameraPreset: (preset: CameraPresetId) => void;
  onExportSnapshot: () => void;
  onOpenImportTdb: () => void;
  probe: ThermodynamicProbeResult | null;
  probePinned: boolean;
  onClearPin: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

export function ControlDock({
  diagram,
  sliceTempK,
  onSliceTempChange,
  explodeFactor,
  onExplodeChange,
  layers,
  onToggleLayer,
  deltaInteractionJ,
  onDeltaInteractionChange,
  autoRotate,
  onToggleAutoRotate,
  activePreset,
  onSelectCameraPreset,
  onExportSnapshot,
  onOpenImportTdb,
  probe,
  probePinned,
  onClearPin,
  collapsed,
  onToggleCollapsed,
}: ControlDockProps) {
  const [activeTab, setActiveTab] = useState<DockTab>('slice');
  const [copiedTdb, setCopiedTdb] = useState(false);

  const { system } = diagram;
  const [e0, e1, e2] = system.elements;

  const tdbText = system.rawTdb ?? formatSystemAsTdb(system, deltaInteractionJ);

  const handleCopyTdb = () => {
    navigator.clipboard?.writeText(tdbText).catch(() => {});
    setCopiedTdb(true);
    window.setTimeout(() => setCopiedTdb(false), 1800);
  };

  const layerItems: Array<{ key: keyof LayerVisibility; label: string }> = [
    { key: 'liquidus', label: 'Liquidus (T₀)' },
    { key: 'solidus', label: 'Solidus (approx.)' },
    { key: 'solvus', label: 'Solvus' },
    { key: 'monovariant', label: 'Valleys' },
    { key: 'isotherm', label: 'Isotherm' },
    { key: 'invariants', label: 'Invariants' },
    { key: 'wireframe', label: 'Mesh' },
  ];

  const cameraButtons: Array<{ id: CameraPresetId; label: string }> = [
    { id: 'iso', label: 'Isometric' },
    { id: 'top', label: 'Top Projection' },
    { id: 'ab', label: `${e0.symbol}–${e1.symbol} Wall` },
    { id: 'bc', label: `${e1.symbol}–${e2.symbol} Wall` },
    { id: 'ca', label: `${e2.symbol}–${e0.symbol} Wall` },
  ];

  return (
    <div
      className="fixed bottom-4 left-1/2 z-20 w-[min(960px,94vw)] transition-transform duration-200 ease-out"
      style={{
        transform: collapsed
          ? 'translate(-50%, calc(100% - 26px))'
          : 'translate(-50%, 0)',
      }}
    >
      {/* Collapse / Expand Handle attached cleanly to top center of dock */}
      <div className="flex justify-center">
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-expanded={!collapsed}
          className="inline-flex items-center gap-1.5 rounded-t-md border border-b-0 border-slate-700/70 bg-[#0E1522] px-3.5 py-1 text-[11px] font-medium text-slate-300 hover:text-white focus-visible:outline-2 focus-visible:outline-amber-500 transition-colors cursor-pointer whitespace-nowrap"
        >
          {collapsed ? (
            <>
              <ChevronUp className="w-3.5 h-3.5" />
              <span>Show Controls</span>
            </>
          ) : (
            <>
              <ChevronDown className="w-3.5 h-3.5" />
              <span>Hide Controls</span>
            </>
          )}
        </button>
      </div>

      {/* Unified Solid-Surface Laboratory Control Dock (zero backdrop-filter over WebGL) */}
      <div className="rounded-lg border border-slate-700/70 bg-[#0E1522]/96 shadow-2xl overflow-hidden">
        {/* Live Thermodynamic Probe Readout Bar */}
        <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-1 border-b border-slate-800 bg-[#0A0F19] px-4 py-2 text-xs">
          {probe ? (
            <>
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className="inline-block w-2.5 h-2.5 rounded-[2px] shrink-0"
                  style={{ backgroundColor: probe.primaryPhaseColor }}
                  aria-hidden="true"
                />
                <span className="font-medium text-slate-100 truncate">
                  {probe.boundaryNote}
                </span>
                <span className="text-slate-600" aria-hidden="true">
                  ·
                </span>
                <span className="font-mono text-amber-400 font-semibold whitespace-nowrap">
                  {probe.tempK.toFixed(1)} K
                  <span className="text-slate-400 font-normal ml-1.5">
                    ({probe.tempC.toFixed(1)} °C)
                  </span>
                </span>
              </div>

              <div className="flex items-center gap-4 font-mono text-[11px] text-slate-300">
                <span className="whitespace-nowrap">
                  {e0.symbol} {(probe.xA * 100).toFixed(1)} · {e1.symbol}{' '}
                  {(probe.xB * 100).toFixed(1)} · {e2.symbol}{' '}
                  {(probe.xC * 100).toFixed(1)}{' '}
                  <span className="text-slate-500">at.%</span>
                </span>
                <span className="hidden sm:inline text-slate-600" aria-hidden="true">
                  /
                </span>
                <span className="hidden sm:inline whitespace-nowrap">
                  Gₘ{' '}
                  <span className="text-slate-100">
                    {probe.gibbsKJ.toFixed(2)}
                  </span>{' '}
                  <span className="text-slate-500">kJ/mol</span>
                </span>
                {probePinned && (
                  <button
                    type="button"
                    onClick={onClearPin}
                    className="inline-flex items-center gap-1 text-amber-400 hover:text-amber-300 cursor-pointer whitespace-nowrap"
                    title="Unpin inspected point"
                  >
                    <PinOff className="w-3.5 h-3.5" />
                    <span>Unpin</span>
                  </button>
                )}
              </div>
            </>
          ) : (
            <div className="flex w-full items-center justify-between gap-4 text-slate-400">
              <span className="truncate">
                Hover a surface to inspect the model Gibbs energies · Click to pin probe
              </span>
              <span className="hidden md:inline font-mono text-[11px] text-slate-500 whitespace-nowrap">
                T range {system.tempMinK}–{system.tempMaxK} K · Drag to orbit · Scroll to zoom
              </span>
            </div>
          )}
        </div>

        {/* Tab Strip & Primary Controls */}
        <div className="px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            {/* Segmented Tab Controls */}
            <div className="inline-flex items-center gap-1 rounded-md bg-[#090D16] p-1 border border-slate-800/90">
              <button
                type="button"
                onClick={() => setActiveTab('slice')}
                className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                  activeTab === 'slice'
                    ? 'bg-slate-800 text-slate-50'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Surfaces &amp; Slice</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('camera')}
                className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                  activeTab === 'camera'
                    ? 'bg-slate-800 text-slate-50'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Camera className="w-3.5 h-3.5" />
                <span>Views</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('calphad')}
                className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                  activeTab === 'calphad'
                    ? 'bg-slate-800 text-slate-50'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                <span>Thermodynamics</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('tdb')}
                className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                  activeTab === 'tdb'
                    ? 'bg-slate-800 text-slate-50'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Database className="w-3.5 h-3.5" />
                <span>TDB Data</span>
              </button>
            </div>

            {/* Quiet unboxed phase legend inline on the right */}
            <div className="hidden lg:flex items-center gap-3.5 text-[11px] text-slate-400">
              {system.phases
                .filter((p) => p.kind !== 'liquid')
                .map((phase) => (
                  <span
                    key={phase.id}
                    className="inline-flex items-center gap-1.5 whitespace-nowrap"
                  >
                    <span
                      className="inline-block w-2 h-2 rounded-[2px]"
                      style={{ backgroundColor: phase.color }}
                      aria-hidden="true"
                    />
                    <span>{phase.shortLabel}</span>
                  </span>
                ))}
            </div>
          </div>

          {/* TAB 1: SURFACES & ISOTHERMAL SLICE */}
          {activeTab === 'slice' && (
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
              {/* Isothermal Temperature Scrubber */}
              <div className="md:col-span-4 flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-xs">
                  <label
                    htmlFor="isotherm-slider"
                    className="text-slate-300 font-medium"
                  >
                    Isothermal Section
                  </label>
                  <span className="font-mono text-amber-400 font-semibold">
                    {sliceTempK.toFixed(0)} K
                    <span className="text-slate-500 font-normal ml-1">
                      ({(sliceTempK - 273.15).toFixed(0)} °C)
                    </span>
                  </span>
                </div>
                <input
                  id="isotherm-slider"
                  type="range"
                  min={system.tempMinK + 10}
                  max={system.tempMaxK - 10}
                  step={5}
                  value={sliceTempK}
                  onChange={(e) => onSliceTempChange(Number(e.target.value))}
                  className="calphad-slider w-full"
                />
              </div>

              {/* Explode Layer Separation Scrubber */}
              <div className="md:col-span-3 flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-xs">
                  <label
                    htmlFor="explode-slider"
                    className="text-slate-300 font-medium"
                  >
                    Explode Layers
                  </label>
                  <span className="font-mono text-slate-300">
                    {Math.round(explodeFactor * 100)}%
                  </span>
                </div>
                <input
                  id="explode-slider"
                  type="range"
                  min={0}
                  max={1}
                  step={0.02}
                  value={explodeFactor}
                  onChange={(e) => onExplodeChange(Number(e.target.value))}
                  className="calphad-slider w-full"
                />
              </div>

              {/* Surface Toggle Matrix */}
              <div className="md:col-span-5 flex flex-wrap items-center gap-1.5 justify-start md:justify-end">
                {layerItems.map((item) => {
                  const active = layers[item.key];
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => onToggleLayer(item.key)}
                      aria-pressed={active}
                      className={`px-2.5 py-1.5 rounded text-xs font-medium border transition-colors cursor-pointer whitespace-nowrap ${
                        active
                          ? 'border-amber-500/70 bg-amber-500/15 text-amber-300'
                          : 'border-slate-700/80 bg-[#0B1018] text-slate-400 hover:text-slate-200 hover:border-slate-600'
                      }`}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 2: CAMERA PRESETS & SNAPSHOT */}
          {activeTab === 'camera' && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-1.5">
                {cameraButtons.map((btn) => (
                  <button
                    key={btn.id}
                    type="button"
                    onClick={() => onSelectCameraPreset(btn.id)}
                    className={`px-3 py-1.5 rounded text-xs font-medium border transition-colors cursor-pointer whitespace-nowrap ${
                      activePreset === btn.id
                        ? 'border-amber-500/70 bg-amber-500/15 text-amber-300'
                        : 'border-slate-700/80 bg-[#0B1018] text-slate-300 hover:border-slate-500 hover:text-white'
                    }`}
                  >
                    {btn.label}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onToggleAutoRotate}
                  aria-pressed={autoRotate}
                  className={`px-3 py-1.5 rounded text-xs font-medium border transition-colors cursor-pointer whitespace-nowrap ${
                    autoRotate
                      ? 'border-cyan-500/70 bg-cyan-500/15 text-cyan-300'
                      : 'border-slate-700/80 bg-[#0B1018] text-slate-300 hover:text-white'
                  }`}
                >
                  {autoRotate ? 'Stop Orbit' : 'Auto Orbit'}
                </button>
                <button
                  type="button"
                  onClick={onExportSnapshot}
                  className="px-3 py-1.5 rounded text-xs font-medium bg-amber-500 text-slate-950 hover:bg-amber-400 transition-colors cursor-pointer whitespace-nowrap"
                >
                  Save PNG
                </button>
              </div>
            </div>
          )}

          {/* TAB 3: THERMODYNAMICS & REDLICH-KISTER INTERACTION TUNER */}
          {activeTab === 'calphad' && (
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
              <div className="md:col-span-5 flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-xs">
                  <label
                    htmlFor="rk-slider"
                    className="text-slate-200 font-medium"
                  >
                    {system.tunableInteraction.label} Offset
                  </label>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-amber-400 font-semibold">
                      {deltaInteractionJ >= 0 ? '+' : ''}
                      {(deltaInteractionJ / 1000).toFixed(1)} kJ/mol
                    </span>
                    {deltaInteractionJ !== 0 && (
                      <button
                        type="button"
                        onClick={() => onDeltaInteractionChange(0)}
                        className="text-slate-400 hover:text-slate-200 cursor-pointer"
                        title="Reset interaction parameter to assessed CALPHAD value"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
                <input
                  id="rk-slider"
                  type="range"
                  min={system.tunableInteraction.minDeltaJ}
                  max={system.tunableInteraction.maxDeltaJ}
                  step={500}
                  value={deltaInteractionJ}
                  onChange={(e) =>
                    onDeltaInteractionChange(Number(e.target.value))
                  }
                  className="calphad-slider w-full"
                />
                <p className="text-[11px] text-slate-400">
                  Perturbs Redlich-Kister excess Gibbs energy and recomputes
                  liquidus &amp; monovariant boundaries live.
                </p>
              </div>

              {/* Pinned / Active Chemical Potentials OR Detected Invariant Points */}
              <div className="md:col-span-7 border-t md:border-t-0 md:border-l border-slate-800 pt-2 md:pt-0 md:pl-4">
                {probe ? (
                  <div className="grid grid-cols-3 gap-3 text-xs">
                    <div>
                      <div className="text-[11px] text-slate-400">
                        Weight Fraction (wt.%)
                      </div>
                      <div className="mt-1 font-mono text-slate-100">
                        {e0.symbol} {(probe.wtA * 100).toFixed(1)} · {e1.symbol}{' '}
                        {(probe.wtB * 100).toFixed(1)} · {e2.symbol}{' '}
                        {(probe.wtC * 100).toFixed(1)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] text-slate-400">
                        Chemical Potentials (kJ/mol)
                      </div>
                      <div className="mt-1 font-mono text-slate-100">
                        μ({e0.symbol}) {probe.chemicalPotentialsKJ[0].toFixed(1)}{' '}
                        · μ({e1.symbol}) {probe.chemicalPotentialsKJ[1].toFixed(1)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] text-slate-400 flex items-center gap-1">
                        {probePinned && <Pin className="w-3 h-3 text-amber-400" />}
                        <span>Phase Fractions</span>
                      </div>
                      <div className="mt-1 font-mono text-slate-100 truncate">
                        {probe.equilibriumPhases
                          .map(
                            (ep) =>
                              `${ep.label.split(' ')[0]} ${(ep.fraction * 100).toFixed(0)}%`,
                          )
                          .join(' + ')}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs">
                    {diagram.invariantPoints.slice(0, 4).map((inv) => (
                      <div key={inv.id} className="flex items-baseline gap-2">
                        <span className="font-medium text-slate-200">
                          {inv.label}
                        </span>
                        <span className="font-mono text-amber-400">
                          {inv.tempK.toFixed(0)} K
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 4: CALPHAD .TDB PARAMETER SOURCE */}
          {activeTab === 'tdb' && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="text-slate-300 truncate">
                  {system.reference}
                </span>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={onOpenImportTdb}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-amber-500/60 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <span>Import .TDB</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleCopyTdb}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-slate-700 bg-[#0B1018] text-slate-200 hover:border-slate-500 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    {copiedTdb ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Copied TDB</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy TDB</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
              <pre className="max-h-28 overflow-y-auto rounded border border-slate-800 bg-[#070B12] p-2.5 font-mono text-[11px] leading-relaxed text-slate-300 select-text">
                {tdbText}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
