import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import {
  PRISM_BASE_Y,
  PRISM_HEIGHT,
  probeThermodynamics,
  tempToY,
  worldToBary,
  yToTemp,
} from '../calphad/solver';
import {
  CameraPresetId,
  ComputedPhaseDiagram,
  LayerVisibility,
  ThermodynamicProbeResult,
} from '../calphad/types';
import {
  PhaseSurfacesAssembly,
  ProbeAssembly,
  buildPhaseSurfaces,
  buildProbeAssembly,
} from '../scene/buildPhaseSurfaces';
import { StageAssembly, buildTernaryStage } from '../scene/buildStage';

export interface PhaseDiagramCanvasHandle {
  setCameraPreset: (preset: CameraPresetId) => void;
  captureSnapshot: () => string | null;
  clearPin: () => void;
}

interface PhaseDiagramCanvasProps {
  diagram: ComputedPhaseDiagram;
  deltaInteractionJ: number;
  sliceTempK: number;
  explodeFactor: number;
  layers: LayerVisibility;
  autoRotate: boolean;
  onProbeChange: (probe: ThermodynamicProbeResult | null, pinned: boolean) => void;
}

// Pre-allocated module-scope scratch objects (zero GC in render/raycast loops)
const _mouse = new THREE.Vector2();
const _raycaster = new THREE.Raycaster();
const _targetCamPos = new THREE.Vector3();
const _targetControlsPos = new THREE.Vector3();
const _hitPos = new THREE.Vector3();

function detectSoftwareWebGL(): boolean {
  try {
    const gl = document.createElement('canvas').getContext('webgl2');
    if (!gl) return true;
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    const param = ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER;
    const gpu = String(gl.getParameter(param) ?? '');
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return /SwiftShader|llvmpipe|softpipe|Software|Basic Render/i.test(gpu);
  } catch {
    return true;
  }
}

const CAMERA_PRESETS: Record<
  CameraPresetId,
  { pos: [number, number, number]; target: [number, number, number] }
> = {
  iso: { pos: [7.6, 5.8, 7.6], target: [0, 1.9, 0] },
  top: { pos: [0.01, 10.6, 0.08], target: [0, 1.6, 0] },
  ab: { pos: [0, 2.5, 9.6], target: [0, 2.0, 0] },
  bc: { pos: [8.3, 2.5, -4.8], target: [0, 2.0, 0] },
  ca: { pos: [-8.3, 2.5, -4.8], target: [0, 2.0, 0] },
};

export const PhaseDiagramCanvas = forwardRef<
  PhaseDiagramCanvasHandle,
  PhaseDiagramCanvasProps
>(function PhaseDiagramCanvas(
  {
    diagram,
    deltaInteractionJ,
    sliceTempK,
    explodeFactor,
    layers,
    autoRotate,
    onProbeChange,
  },
  ref,
) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [contextLost, setContextLost] = useState(false);

  // Latest props stored in refs so WebGL lifecycle never tears down on UI state changes
  const diagramRef = useRef(diagram);
  const deltaRef = useRef(deltaInteractionJ);
  const sliceTempRef = useRef(sliceTempK);
  const explodeRef = useRef(explodeFactor);
  const layersRef = useRef(layers);
  const autoRotateRef = useRef(autoRotate);
  const onProbeRef = useRef(onProbeChange);

  diagramRef.current = diagram;
  deltaRef.current = deltaInteractionJ;
  sliceTempRef.current = sliceTempK;
  explodeRef.current = explodeFactor;
  layersRef.current = layers;
  autoRotateRef.current = autoRotate;
  onProbeRef.current = onProbeChange;

  // Imperative scene refs
  const engineRef = useRef<{
    renderer: THREE.WebGLRenderer;
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    isSoftwareGl: boolean;
    stage: StageAssembly | null;
    surfaces: PhaseSurfacesAssembly | null;
    probe: ProbeAssembly;
    requestRender: () => void;
    triggerCameraPreset: (preset: CameraPresetId) => void;
    clearPin: () => void;
    pinned: boolean;
    pinnedData: {
      xA: number;
      xB: number;
      xC: number;
      tempK: number;
      surface: ThermodynamicProbeResult['surface'];
      worldPos: THREE.Vector3;
    } | null;
  } | null>(null);

  useImperativeHandle(ref, () => ({
    setCameraPreset(preset: CameraPresetId) {
      engineRef.current?.triggerCameraPreset(preset);
    },
    captureSnapshot() {
      const eng = engineRef.current;
      if (!eng) return null;
      // Render immediately before capture so drawing buffer is fresh
      eng.renderer.render(eng.scene, eng.camera);
      return eng.renderer.domElement.toDataURL('image/png');
    },
    clearPin() {
      engineRef.current?.clearPin();
    },
  }));

  // 1. Mount Three.js renderer, lighting rig, studio environment & coalesced loop ONCE
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const isSoftwareGl = detectSoftwareWebGL();
    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    const renderer = new THREE.WebGLRenderer({
      antialias: !isSoftwareGl,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(isSoftwareGl ? 1 : Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.shadowMap.enabled = !isSoftwareGl;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const bgHex = 0x0b1018;
    scene.background = new THREE.Color(bgHex);
    scene.fog = new THREE.FogExp2(bgHex, 0.024);

    // Mandatory procedural studio RoomEnvironment reflections on every device
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    const roomEnv = new RoomEnvironment();
    const envTarget = pmremGenerator.fromScene(roomEnv, 0.04);
    scene.environment = envTarget.texture;
    roomEnv.dispose();
    pmremGenerator.dispose();

    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 120);
    camera.position.set(...CAMERA_PRESETS.iso.pos);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(...CAMERA_PRESETS.iso.target);
    controls.enableDamping = !isSoftwareGl;
    controls.dampingFactor = 0.065;
    controls.minDistance = 4.2;
    controls.maxDistance = 24;
    controls.maxPolarAngle = Math.PI * 0.495;
    controls.autoRotate = false;
    controls.autoRotateSpeed = 0.85;
    controls.update();

    // 3-Point Warm/Cool Calibrated Studio Lighting Rig (<= 3 shadow casters)
    const keyLight = new THREE.DirectionalLight(0xfff4e6, 1.95);
    keyLight.position.set(7.5, 11.5, 6.5);
    keyLight.castShadow = !isSoftwareGl;
    keyLight.shadow.mapSize.width = 2048;
    keyLight.shadow.mapSize.height = 2048;
    keyLight.shadow.camera.near = 1;
    keyLight.shadow.camera.far = 28;
    const d = 6.5;
    keyLight.shadow.camera.left = -d;
    keyLight.shadow.camera.right = d;
    keyLight.shadow.camera.top = d;
    keyLight.shadow.camera.bottom = -d;
    keyLight.shadow.bias = -0.0005;
    keyLight.shadow.normalBias = 0.02;
    scene.add(keyLight);

    // Cool sky/ground hemisphere fill for warm/cool contrast
    const hemiLight = new THREE.HemisphereLight(0x9cc3e8, 0x1a2232, 0.8);
    scene.add(hemiLight);

    // Cool rear rim directional light to cleanly separate metallic edges
    const rimLight = new THREE.DirectionalLight(0xb8d8ff, 0.95);
    rimLight.position.set(-7.0, 6.0, -7.5);
    scene.add(rimLight);

    // Overhead studio softbox for smooth elongated specular highlights (skip on software GL)
    if (!isSoftwareGl) {
      RectAreaLightUniformsLib.init();
      const softbox = new THREE.RectAreaLight(0xe2eeff, 2.2, 6.5, 3.5);
      softbox.position.set(0, 8.2, 2.0);
      softbox.lookAt(0, 1.8, 0);
      scene.add(softbox);
    }

    // Precision 3D probe reticle
    const probe = buildProbeAssembly();
    scene.add(probe.group);

    // Transition animation state
    let camTransitionActive = false;
    let currentExplode = explodeRef.current;
    let currentSliceY = tempToY(
      sliceTempRef.current,
      diagramRef.current.system.tempMinK,
      diagramRef.current.system.tempMaxK,
    );
    let lastTime = performance.now();

    // Coalesced on-demand render loop with software-WebGL fenceSync pacing
    let frameId = 0;
    let renderBusy = false;
    let renderDirty = false;
    let disposed = false;

    function afterDraw(cb: () => void) {
      const gl = renderer.getContext() as WebGL2RenderingContext;
      const sync = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
      gl.flush();
      const poll = () => {
        if (disposed) return;
        const state = sync && gl.getSyncParameter(sync, gl.SYNC_STATUS);
        if (state === gl.UNSIGNALED) {
          frameId = window.setTimeout(poll, 5);
        } else {
          if (sync) gl.deleteSync(sync);
          frameId = window.setTimeout(cb, 80);
        }
      };
      frameId = window.setTimeout(poll, 5);
    }

    function requestRender() {
      if (disposed) return;
      if (renderBusy) {
        renderDirty = true;
        return;
      }
      renderBusy = true;
      frameId = requestAnimationFrame(() => {
        if (disposed) return;
        renderDirty = false;

        const now = performance.now();
        const dt = Math.min(0.05, Math.max(0.001, (now - lastTime) / 1000));
        lastTime = now;

        let needsFollowUp = false;

        // 1. Damped camera preset glide (cancels on arrival or user drag)
        if (camTransitionActive) {
          if (isSoftwareGl) {
            camera.position.copy(_targetCamPos);
            controls.target.copy(_targetControlsPos);
            camTransitionActive = false;
          } else {
            const alpha = 1 - Math.exp(-7.5 * dt);
            camera.position.lerp(_targetCamPos, alpha);
            controls.target.lerp(_targetControlsPos, alpha);
            if (
              camera.position.distanceToSquared(_targetCamPos) < 0.0004 &&
              controls.target.distanceToSquared(_targetControlsPos) < 0.0004
            ) {
              camera.position.copy(_targetCamPos);
              controls.target.copy(_targetControlsPos);
              camTransitionActive = false;
            } else {
              needsFollowUp = true;
            }
          }
        }

        // 2. Smoothly damped vertical exploded layer separation & isothermal plane glide
        const eng = engineRef.current;
        if (eng?.surfaces) {
          const targetExplode = explodeRef.current;
          const targetSliceY = tempToY(
            sliceTempRef.current,
            diagramRef.current.system.tempMinK,
            diagramRef.current.system.tempMaxK,
          );

          if (isSoftwareGl) {
            currentExplode = targetExplode;
            currentSliceY = targetSliceY;
          } else {
            if (Math.abs(currentExplode - targetExplode) > 0.001) {
              currentExplode = THREE.MathUtils.damp(
                currentExplode,
                targetExplode,
                9.0,
                dt,
              );
              needsFollowUp = true;
            } else {
              currentExplode = targetExplode;
            }

            if (Math.abs(currentSliceY - targetSliceY) > 0.001) {
              currentSliceY = THREE.MathUtils.damp(
                currentSliceY,
                targetSliceY,
                11.0,
                dt,
              );
              needsFollowUp = true;
            } else {
              currentSliceY = targetSliceY;
            }
          }

          eng.surfaces.liquidusGroup.position.y = currentExplode * 1.45;
          eng.surfaces.monovariantGroup.position.y = currentExplode * 1.45;
          eng.surfaces.invariantsGroup.position.y = currentExplode * 1.45;
          eng.surfaces.solidusGroup.position.y = currentExplode * 0.52;
          eng.surfaces.solvusGroup.position.y = 0;
          eng.surfaces.isothermGroup.position.y = currentSliceY;
        }

        // 3. OrbitControls update (damping + optional auto-rotate on GPU)
        controls.autoRotate = !isSoftwareGl && autoRotateRef.current;
        const controlsMoved = controls.update();
        if (controlsMoved || (!isSoftwareGl && autoRotateRef.current)) {
          needsFollowUp = true;
        }

        renderer.render(scene, camera);

        const done = () => {
          renderBusy = false;
          if (!disposed && (renderDirty || needsFollowUp)) {
            requestRender();
          }
        };
        if (isSoftwareGl) afterDraw(done);
        else done();
      });
    }

    const triggerCameraPreset = (preset: CameraPresetId) => {
      const cfg = CAMERA_PRESETS[preset];
      _targetCamPos.set(...cfg.pos);
      _targetControlsPos.set(...cfg.target);
      camTransitionActive = true;
      requestRender();
    };

    // Cancel camera glide immediately when user interacts with OrbitControls
    const onControlsStart = () => {
      camTransitionActive = false;
    };
    const onControlsChange = () => {
      requestRender();
    };
    controls.addEventListener('start', onControlsStart);
    controls.addEventListener('change', onControlsChange);

    // WebGL context loss / restoration safety
    const onContextLost = (e: Event) => {
      e.preventDefault();
      setContextLost(true);
    };
    const onContextRestored = () => {
      setContextLost(false);
      requestRender();
    };
    renderer.domElement.addEventListener('webglcontextlost', onContextLost);
    renderer.domElement.addEventListener('webglcontextrestored', onContextRestored);

    // ResizeObserver for crisp responsive full-bleed viewport
    const resizeObserver = new ResizeObserver(() => {
      const w = container.clientWidth || window.innerWidth;
      const h = container.clientHeight || window.innerHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      requestRender();
    });
    resizeObserver.observe(container);

    // Throttled pointer raycasting on layer 1 (phase surfaces & monovariant curves)
    _raycaster.layers.set(1);
    let lastRaycastMs = 0;
    let pointerDownPos = { x: 0, y: 0 };

    const performRaycast = (
      clientX: number,
      clientY: number,
    ): {
      point: THREE.Vector3;
      xA: number;
      xB: number;
      xC: number;
      tempK: number;
      surface: ThermodynamicProbeResult['surface'];
    } | null => {
      const eng = engineRef.current;
      if (!eng?.surfaces) return null;

      const rect = renderer.domElement.getBoundingClientRect();
      _mouse.x = ((clientX - rect.left) / rect.width) * 2 - 1;
      _mouse.y = -((clientY - rect.top) / rect.height) * 2 + 1;

      _raycaster.setFromCamera(_mouse, camera);
      const visibleTargets = eng.surfaces.raycastTargets.filter((obj) => {
        let cur: THREE.Object3D | null = obj;
        while (cur) {
          if (!cur.visible) return false;
          cur = cur.parent;
        }
        return true;
      });

      const hits = _raycaster.intersectObjects(visibleTargets, false);
      if (hits.length === 0) return null;

      const hit = hits[0];
      const surface = (hit.object.userData.surface ??
        'liquidus') as ThermodynamicProbeResult['surface'];

      // Subtract vertical exploded offset so temperature reading remains physically exact
      let yOffset = 0;
      if (surface === 'liquidus' || surface === 'monovariant') {
        yOffset = eng.surfaces.liquidusGroup.position.y;
      } else if (surface === 'solidus') {
        yOffset = eng.surfaces.solidusGroup.position.y;
      }

      const [xA, xB, xC] = worldToBary(hit.point.x, hit.point.z);
      const diag = diagramRef.current;
      const tempK =
        surface === 'isotherm'
          ? sliceTempRef.current
          : yToTemp(hit.point.y - yOffset, diag.system.tempMinK, diag.system.tempMaxK);

      return {
        point: _hitPos.copy(hit.point),
        xA,
        xB,
        xC,
        tempK,
        surface,
      };
    };

    const onPointerDown = (e: PointerEvent) => {
      pointerDownPos = { x: e.clientX, y: e.clientY };
    };

    const onPointerUp = (e: PointerEvent) => {
      const dist = Math.hypot(
        e.clientX - pointerDownPos.x,
        e.clientY - pointerDownPos.y,
      );
      if (dist > 5) return; // User was orbiting, not clicking

      const eng = engineRef.current;
      if (!eng) return;

      const hit = performRaycast(e.clientX, e.clientY);
      if (hit) {
        const result = probeThermodynamics(
          diagramRef.current,
          deltaRef.current,
          hit.xA,
          hit.xB,
          hit.xC,
          hit.tempK,
          hit.surface,
        );
        eng.pinned = true;
        eng.pinnedData = {
          xA: hit.xA,
          xB: hit.xB,
          xC: hit.xC,
          tempK: hit.tempK,
          surface: hit.surface,
          worldPos: hit.point.clone(),
        };
        probe.setPoint(
          hit.point,
          hit.xA,
          hit.xB,
          hit.xC,
          result.primaryPhaseColor,
        );
        onProbeRef.current(result, true);
        requestRender();
      } else if (eng.pinned) {
        eng.pinned = false;
        eng.pinnedData = null;
        probe.setVisible(false);
        onProbeRef.current(null, false);
        requestRender();
      }
    };

    const onPointerMove = (e: PointerEvent) => {
      const eng = engineRef.current;
      if (!eng || eng.pinned) return;
      if (e.buttons !== 0) return; // Don't raycast while orbiting

      const now = performance.now();
      if (now - lastRaycastMs < 42) return;
      lastRaycastMs = now;

      const hit = performRaycast(e.clientX, e.clientY);
      if (hit) {
        renderer.domElement.style.cursor = 'crosshair';
        const result = probeThermodynamics(
          diagramRef.current,
          deltaRef.current,
          hit.xA,
          hit.xB,
          hit.xC,
          hit.tempK,
          hit.surface,
        );
        probe.setPoint(
          hit.point,
          hit.xA,
          hit.xB,
          hit.xC,
          result.primaryPhaseColor,
        );
        onProbeRef.current(result, false);
        requestRender();
      } else {
        renderer.domElement.style.cursor = 'grab';
        if (probe.group.visible) {
          probe.setVisible(false);
          onProbeRef.current(null, false);
          requestRender();
        }
      }
    };

    const onPointerLeave = () => {
      const eng = engineRef.current;
      if (!eng || eng.pinned) return;
      if (probe.group.visible) {
        probe.setVisible(false);
        onProbeRef.current(null, false);
        requestRender();
      }
    };

    renderer.domElement.style.cursor = 'grab';
    renderer.domElement.addEventListener('pointerdown', onPointerDown);
    renderer.domElement.addEventListener('pointerup', onPointerUp);
    renderer.domElement.addEventListener('pointermove', onPointerMove);
    renderer.domElement.addEventListener('pointerleave', onPointerLeave);

    const clearPin = () => {
      const eng = engineRef.current;
      if (!eng) return;
      eng.pinned = false;
      eng.pinnedData = null;
      probe.setVisible(false);
      onProbeRef.current(null, false);
      requestRender();
    };

    engineRef.current = {
      renderer,
      scene,
      camera,
      controls,
      isSoftwareGl,
      stage: null,
      surfaces: null,
      probe,
      requestRender,
      triggerCameraPreset,
      clearPin,
      pinned: false,
      pinnedData: null,
    };

    return () => {
      disposed = true;
      cancelAnimationFrame(frameId);
      clearTimeout(frameId);
      resizeObserver.disconnect();
      controls.removeEventListener('start', onControlsStart);
      controls.removeEventListener('change', onControlsChange);
      controls.dispose();
      renderer.domElement.removeEventListener('webglcontextlost', onContextLost);
      renderer.domElement.removeEventListener('webglcontextrestored', onContextRestored);
      renderer.domElement.removeEventListener('pointerdown', onPointerDown);
      renderer.domElement.removeEventListener('pointerup', onPointerUp);
      renderer.domElement.removeEventListener('pointermove', onPointerMove);
      renderer.domElement.removeEventListener('pointerleave', onPointerLeave);

      if (engineRef.current?.stage) {
        scene.remove(engineRef.current.stage.group);
        engineRef.current.stage.dispose();
      }
      if (engineRef.current?.surfaces) {
        scene.remove(engineRef.current.surfaces.root);
        engineRef.current.surfaces.dispose();
      }
      probe.dispose();
      envTarget.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
      engineRef.current = null;
    };
  }, []);

  // 2. Rebuild stage + phase surfaces whenever the CALPHAD diagram changes (system switch or L0 delta)
  useEffect(() => {
    const eng = engineRef.current;
    if (!eng) return;

    const maxAniso = eng.renderer.capabilities.getMaxAnisotropy();

    // Rebuild instrument stage if system changed
    if (eng.stage) {
      eng.scene.remove(eng.stage.group);
      eng.stage.dispose();
      eng.stage = null;
    }
    const nextStage = buildTernaryStage(diagram.system, maxAniso);
    eng.scene.add(nextStage.group);
    eng.stage = nextStage;

    // Rebuild 3D CALPHAD phase surfaces
    if (eng.surfaces) {
      eng.scene.remove(eng.surfaces.root);
      eng.surfaces.dispose();
      eng.surfaces = null;
    }
    const nextSurfaces = buildPhaseSurfaces(
      diagram,
      sliceTempRef.current,
      maxAniso,
      eng.isSoftwareGl,
    );
    // Apply current visibility immediately
    nextSurfaces.liquidusGroup.visible = layersRef.current.liquidus;
    nextSurfaces.solidusGroup.visible = layersRef.current.solidus;
    nextSurfaces.solvusGroup.visible = layersRef.current.solvus;
    nextSurfaces.monovariantGroup.visible = layersRef.current.monovariant;
    nextSurfaces.invariantsGroup.visible = layersRef.current.invariants;
    nextSurfaces.wireframeLine.visible = layersRef.current.wireframe;
    nextSurfaces.isothermGroup.visible = layersRef.current.isotherm;

    // Apply current explode offset immediately
    nextSurfaces.liquidusGroup.position.y = explodeRef.current * 1.45;
    nextSurfaces.monovariantGroup.position.y = explodeRef.current * 1.45;
    nextSurfaces.invariantsGroup.position.y = explodeRef.current * 1.45;
    nextSurfaces.solidusGroup.position.y = explodeRef.current * 0.52;

    eng.scene.add(nextSurfaces.root);
    eng.surfaces = nextSurfaces;

    // Clear stale pin when system or parameters change
    eng.pinned = false;
    eng.pinnedData = null;
    eng.probe.setVisible(false);
    onProbeRef.current(null, false);

    // Pre-warm shaders once on hardware GPUs
    if (!eng.isSoftwareGl) {
      eng.renderer.compile(eng.scene, eng.camera);
    }

    eng.requestRender();
  }, [diagram]);

  // 3. Update isothermal slice texture + glide target height when sliceTempK changes
  useEffect(() => {
    const eng = engineRef.current;
    if (!eng?.surfaces) return;
    const maxAniso = eng.renderer.capabilities.getMaxAnisotropy();
    eng.surfaces.updateIsothermTexture(sliceTempK, maxAniso);
    eng.requestRender();
  }, [sliceTempK]);

  // 4. Sync layer visibility, explode factor, and auto-rotate without re-mounting
  useEffect(() => {
    const eng = engineRef.current;
    if (!eng?.surfaces) return;
    eng.surfaces.liquidusGroup.visible = layers.liquidus;
    eng.surfaces.solidusGroup.visible = layers.solidus;
    eng.surfaces.solvusGroup.visible = layers.solvus;
    eng.surfaces.monovariantGroup.visible = layers.monovariant;
    eng.surfaces.invariantsGroup.visible = layers.invariants;
    eng.surfaces.wireframeLine.visible = layers.wireframe;
    eng.surfaces.isothermGroup.visible = layers.isotherm;
    eng.requestRender();
  }, [layers, explodeFactor, autoRotate]);

  return (
    <div className="relative w-full h-full">
      {/* Dedicated empty container for Three.js WebGL canvas */}
      <div ref={mountRef} className="w-full h-full" />

      {contextLost && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#0B1018] text-slate-200 z-30">
          <div className="max-w-sm border border-slate-700 bg-[#111827] px-6 py-5 rounded-lg text-center">
            <h2 className="text-base font-semibold text-slate-100">
              WebGL Context Interrupted
            </h2>
            <p className="mt-2 text-xs text-slate-400">
              Graphics hardware context was suspended. Waiting for automatic
              restoration or reload the viewport.
            </p>
          </div>
        </div>
      )}
    </div>
  );
});

export { PRISM_BASE_Y, PRISM_HEIGHT };
