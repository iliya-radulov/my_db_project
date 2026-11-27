import * as THREE from 'three';
import {
  PRISM_BASE_Y,
  PRISM_HEIGHT,
  VERTEX_A,
  VERTEX_B,
  VERTEX_C,
  baryToWorld,
  tempToY,
} from '../calphad/solver';
import { ComputedPhaseDiagram } from '../calphad/types';
import {
  GIBBS_UV_A,
  GIBBS_UV_B,
  GIBBS_UV_C,
  createIsothermSliceTexture,
  createLabelSprite,
} from './textures';

export interface PhaseSurfacesAssembly {
  root: THREE.Group;
  liquidusGroup: THREE.Group;
  solidusGroup: THREE.Group;
  solvusGroup: THREE.Group;
  monovariantGroup: THREE.Group;
  invariantsGroup: THREE.Group;
  wireframeLine: THREE.LineSegments;
  isothermGroup: THREE.Group;
  isothermWaferMat: THREE.MeshBasicMaterial;
  raycastTargets: THREE.Object3D[];
  updateIsothermTexture: (tempK: number, maxAnisotropy: number) => void;
  dispose: () => void;
}

/**
 * Builds all CALPHAD thermodynamic 3D surfaces (Liquidus with PBR contour-line shader
 * extension, translucent Solidus shell, Subsolidus Solvus dome, metallic TubeGeometry
 * monovariant curves, composite invariant reaction markers, and the sliding Isothermal
 * section assembly).
 */
export function buildPhaseSurfaces(
  diagram: ComputedPhaseDiagram,
  initialSliceK: number,
  maxAnisotropy: number,
  isSoftwareGl: boolean,
): PhaseSurfacesAssembly {
  const root = new THREE.Group();
  root.name = 'PhaseDiagramSurfaces';

  const geometries: THREE.BufferGeometry[] = [];
  const materials: THREE.Material[] = [];
  const textures: THREE.Texture[] = [];

  const trackGeo = <T extends THREE.BufferGeometry>(g: T): T => {
    geometries.push(g);
    return g;
  };
  const trackMat = <T extends THREE.Material>(m: T): T => {
    materials.push(m);
    return m;
  };
  const trackTex = <T extends THREE.Texture>(t: T): T => {
    textures.push(t);
    return t;
  };

  const { system, nodes, triangles } = diagram;
  const phaseColorMap = new Map<string, THREE.Color>();
  for (const p of system.phases) {
    phaseColorMap.set(p.id, new THREE.Color(p.color));
  }

  const raycastTargets: THREE.Object3D[] = [];

  // =========================================================================
  // 1. LIQUIDUS SURFACE (High-resolution indexed BufferGeometry + PBR Contours)
  // =========================================================================
  const liquidusGroup = new THREE.Group();
  const liqPos = new Float32Array(nodes.length * 3);
  const liqCol = new Float32Array(nodes.length * 3);
  const tmpColor = new THREE.Color();
  const warmHighlight = new THREE.Color('#FFF7ED');

  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    const [wx, wy, wz] = baryToWorld(
      n.xA,
      n.xB,
      n.xC,
      n.tLiquidus,
      system.tempMinK,
      system.tempMaxK,
    );
    liqPos[i * 3] = wx;
    liqPos[i * 3 + 1] = wy;
    liqPos[i * 3 + 2] = wz;

    const base = phaseColorMap.get(n.primaryPhaseId) ?? new THREE.Color('#60A5FA');
    const tFrac =
      (n.tLiquidus - diagram.minLiquidusK) /
      Math.max(1, diagram.maxLiquidusK - diagram.minLiquidusK);
    // Subtle luminance lift toward high-temperature melting peaks
    tmpColor.copy(base).lerp(warmHighlight, tFrac * 0.24);
    liqCol[i * 3] = tmpColor.r;
    liqCol[i * 3 + 1] = tmpColor.g;
    liqCol[i * 3 + 2] = tmpColor.b;
  }

  const liqGeo = trackGeo(new THREE.BufferGeometry());
  liqGeo.setAttribute('position', new THREE.BufferAttribute(liqPos, 3));
  liqGeo.setAttribute('color', new THREE.BufferAttribute(liqCol, 3));
  liqGeo.setIndex(new THREE.BufferAttribute(triangles, 1));
  liqGeo.computeVertexNormals();

  // Extend MeshPhysicalMaterial with razor-sharp isothermal contour lines via onBeforeCompile
  const liqMat = trackMat(
    new THREE.MeshPhysicalMaterial({
      vertexColors: true,
      roughness: 0.32,
      metalness: 0.24,
      clearcoat: 0.42,
      clearcoatRoughness: 0.24,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.92,
    }),
  );

  liqMat.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader
      .replace(
        '#include <common>',
        `#include <common>
        varying float vWorldHeight;`,
      )
      .replace(
        '#include <begin_vertex>',
        `#include <begin_vertex>
        vWorldHeight = position.y;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
        varying float vWorldHeight;`,
      )
      .replace(
        '#include <color_fragment>',
        `#include <color_fragment>
        // Calibrated isothermal elevation contour lines every ~10% of temperature span
        float hNorm = (vWorldHeight - ${PRISM_BASE_Y.toFixed(3)}) / ${PRISM_HEIGHT.toFixed(3)};
        float contourFreq = 12.0;
        float dist = abs(fract(hNorm * contourFreq + 0.5) - 0.5);
        float fw = max(fwidth(hNorm * contourFreq), 0.015);
        float lineMask = 1.0 - smoothstep(0.025, 0.025 + fw * 1.35, dist);
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.98, 0.99, 1.0), lineMask * 0.28);`,
      );
  };

  const liqMesh = new THREE.Mesh(liqGeo, liqMat);
  liqMesh.castShadow = !isSoftwareGl;
  liqMesh.receiveShadow = true;
  liqMesh.layers.enable(1);
  liqMesh.userData = { surface: 'liquidus' };
  liquidusGroup.add(liqMesh);
  raycastTargets.push(liqMesh);

  // Subtle translucent binary-edge side curtains on the Liquidus surface perimeter
  const wireframeGeo = trackGeo(new THREE.WireframeGeometry(liqGeo));
  const wireframeMat = trackMat(
    new THREE.LineBasicMaterial({
      color: 0xe2e8f0,
      transparent: true,
      opacity: 0.24,
    }),
  );
  const wireframeLine = new THREE.LineSegments(wireframeGeo, wireframeMat);
  wireframeLine.position.y = 0.004;
  wireframeLine.visible = false;
  liquidusGroup.add(wireframeLine);

  root.add(liquidusGroup);

  // =========================================================================
  // 2. SOLIDUS SURFACE (Translucent structural shell + edge outline)
  // =========================================================================
  const solidusGroup = new THREE.Group();
  const solPos = new Float32Array(nodes.length * 3);
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    const [wx, wy, wz] = baryToWorld(
      n.xA,
      n.xB,
      n.xC,
      n.tSolidus,
      system.tempMinK,
      system.tempMaxK,
    );
    solPos[i * 3] = wx;
    solPos[i * 3 + 1] = wy;
    solPos[i * 3 + 2] = wz;
  }

  const solGeo = trackGeo(new THREE.BufferGeometry());
  solGeo.setAttribute('position', new THREE.BufferAttribute(solPos, 3));
  solGeo.setIndex(new THREE.BufferAttribute(triangles, 1));
  solGeo.computeVertexNormals();

  const solMat = trackMat(
    new THREE.MeshPhysicalMaterial({
      color: 0x38bdf8,
      roughness: 0.22,
      metalness: 0.14,
      clearcoat: 0.55,
      transparent: true,
      opacity: 0.34,
      depthWrite: false,
      side: THREE.DoubleSide,
    }),
  );
  const solMesh = new THREE.Mesh(solGeo, solMat);
  solMesh.renderOrder = 2;
  solMesh.layers.enable(1);
  solMesh.userData = { surface: 'solidus' };
  solidusGroup.add(solMesh);
  raycastTargets.push(solMesh);

  // Crisp perimeter rim of the Solidus surface along the 3 binary walls
  const solidusBorderEdges = buildPerimeterLine(
    diagram,
    (n) => n.tSolidus,
    0x7dd3fc,
    0.72,
    trackGeo,
    trackMat,
  );
  solidusGroup.add(solidusBorderEdges);
  root.add(solidusGroup);

  // =========================================================================
  // 3. SUBSOLIDUS SOLVUS / INTERMETALLIC DOME
  // =========================================================================
  const solvusGroup = new THREE.Group();
  const solvusTriIndices: number[] = [];
  for (let t = 0; t < triangles.length; t += 3) {
    const a = triangles[t];
    const b = triangles[t + 1];
    const c = triangles[t + 2];
    if (
      !Number.isNaN(nodes[a].tSolvus) &&
      !Number.isNaN(nodes[b].tSolvus) &&
      !Number.isNaN(nodes[c].tSolvus)
    ) {
      solvusTriIndices.push(a, b, c);
    }
  }

  if (solvusTriIndices.length > 0) {
    const solvPos = new Float32Array(nodes.length * 3);
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i];
      const tVal = Number.isNaN(n.tSolvus) ? system.tempMinK : n.tSolvus;
      const [wx, wy, wz] = baryToWorld(
        n.xA,
        n.xB,
        n.xC,
        tVal,
        system.tempMinK,
        system.tempMaxK,
      );
      solvPos[i * 3] = wx;
      solvPos[i * 3 + 1] = wy;
      solvPos[i * 3 + 2] = wz;
    }

    const solvGeo = trackGeo(new THREE.BufferGeometry());
    solvGeo.setAttribute('position', new THREE.BufferAttribute(solvPos, 3));
    solvGeo.setIndex(solvusTriIndices);
    solvGeo.computeVertexNormals();

    const domeColor = system.id === 'fe-cr-ni' ? 0xe11d48 : 0x6366f1;
    const solvMat = trackMat(
      new THREE.MeshStandardMaterial({
        color: domeColor,
        roughness: 0.34,
        metalness: 0.36,
        transparent: true,
        opacity: 0.72,
        side: THREE.DoubleSide,
      }),
    );
    const solvMesh = new THREE.Mesh(solvGeo, solvMat);
    solvMesh.renderOrder = 1;
    solvMesh.layers.enable(1);
    solvMesh.userData = { surface: 'solvus' };
    solvusGroup.add(solvMesh);
    raycastTargets.push(solvMesh);
  }
  root.add(solvusGroup);

  // =========================================================================
  // 4. MONOVARIANT PHASE BOUNDARY CURVES (Metallic TubeGeometry valleys)
  // =========================================================================
  const monovariantGroup = new THREE.Group();
  const monoMat = trackMat(
    new THREE.MeshPhysicalMaterial({
      color: 0xf59e0b,
      emissive: 0x92400e,
      emissiveIntensity: 0.32,
      metalness: 0.88,
      roughness: 0.18,
      clearcoat: 0.4,
    }),
  );

  for (const curve of diagram.monovariantCurves) {
    const pts = curve.points.map((p) => {
      const [wx, wy, wz] = baryToWorld(
        p.xA,
        p.xB,
        p.xC,
        p.tempK,
        system.tempMinK,
        system.tempMaxK,
      );
      return new THREE.Vector3(wx, wy + 0.016, wz);
    });

    if (pts.length < 3) continue;
    const spline = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
    const tubularSegs = Math.min(96, Math.max(18, pts.length * 3));
    const tubeGeo = trackGeo(new THREE.TubeGeometry(spline, tubularSegs, 0.026, 8, false));
    const tubeMesh = new THREE.Mesh(tubeGeo, monoMat);
    tubeMesh.layers.enable(1);
    tubeMesh.userData = {
      surface: 'monovariant',
      phasePair: curve.phasePair,
    };
    monovariantGroup.add(tubeMesh);
    raycastTargets.push(tubeMesh);
  }
  root.add(monovariantGroup);

  // =========================================================================
  // 5. INVARIANT REACTION MARKERS (Composite 3-Part Precision Beacons)
  // =========================================================================
  const invariantsGroup = new THREE.Group();
  const beaconCoreGeo = trackGeo(new THREE.OctahedronGeometry(0.075, 0));
  const beaconRingGeo = trackGeo(new THREE.TorusGeometry(0.115, 0.016, 10, 24));
  beaconRingGeo.rotateX(Math.PI / 2);

  const eutecticMat = trackMat(
    new THREE.MeshPhysicalMaterial({
      color: 0xfbbf24,
      emissive: 0xd97706,
      emissiveIntensity: 0.45,
      metalness: 0.85,
      roughness: 0.16,
    }),
  );
  const congruentMat = trackMat(
    new THREE.MeshPhysicalMaterial({
      color: 0xf43f5e,
      emissive: 0x9f1239,
      emissiveIntensity: 0.4,
      metalness: 0.82,
      roughness: 0.2,
    }),
  );
  const plumbMat = trackMat(
    new THREE.LineDashedMaterial({
      color: 0xfbbf24,
      dashSize: 0.09,
      gapSize: 0.07,
      transparent: true,
      opacity: 0.65,
    }),
  );

  for (const inv of diagram.invariantPoints) {
    const [wx, wy, wz] = baryToWorld(
      inv.xA,
      inv.xB,
      inv.xC,
      inv.tempK,
      system.tempMinK,
      system.tempMaxK,
    );
    const invNode = new THREE.Group();
    const mat = inv.kind === 'congruent' ? congruentMat : eutecticMat;

    const core = new THREE.Mesh(beaconCoreGeo, mat);
    core.position.set(wx, wy + 0.04, wz);
    invNode.add(core);

    const ring = new THREE.Mesh(beaconRingGeo, mat);
    ring.position.set(wx, wy + 0.04, wz);
    invNode.add(ring);

    const plumbGeo = trackGeo(
      new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(wx, PRISM_BASE_Y + 0.01, wz),
        new THREE.Vector3(wx, wy + 0.02, wz),
      ]),
    );
    const plumb = new THREE.Line(plumbGeo, plumbMat);
    plumb.computeLineDistances();
    invNode.add(plumb);

    const badge = createLabelSprite(
      inv.label,
      `${inv.tempK.toFixed(0)} K (${(inv.tempK - 273.15).toFixed(0)} °C)`,
      inv.kind === 'congruent' ? '#F43F5E' : '#F59E0B',
      0.66,
    );
    badge.position.set(wx, wy + 0.34, wz);
    trackMat(badge.material);
    if (badge.material.map) trackTex(badge.material.map);
    invNode.add(badge);

    invariantsGroup.add(invNode);
  }
  root.add(invariantsGroup);

  // =========================================================================
  // 6. INTERACTIVE ISOTHERMAL CUTTING PLANE ASSEMBLY
  // =========================================================================
  const isothermGroup = new THREE.Group();
  const initialY = tempToY(initialSliceK, system.tempMinK, system.tempMaxK);
  isothermGroup.position.y = initialY;

  // Machined outer hollow bezel ring surrounding the isothermal wafer
  const outerPad = 1.035;
  const frameShape = new THREE.Shape();
  frameShape.moveTo(VERTEX_A[0] * outerPad, -VERTEX_A[1] * outerPad);
  frameShape.lineTo(VERTEX_B[0] * outerPad, -VERTEX_B[1] * outerPad);
  frameShape.lineTo(VERTEX_C[0] * outerPad, -VERTEX_C[1] * outerPad);
  frameShape.closePath();

  const innerHole = new THREE.Path();
  innerHole.moveTo(VERTEX_A[0], -VERTEX_A[1]);
  innerHole.lineTo(VERTEX_B[0], -VERTEX_B[1]);
  innerHole.lineTo(VERTEX_C[0], -VERTEX_C[1]);
  innerHole.closePath();
  frameShape.holes.push(innerHole);

  const frameGeo = trackGeo(
    new THREE.ExtrudeGeometry(frameShape, {
      depth: 0.036,
      bevelEnabled: true,
      bevelThickness: 0.012,
      bevelSize: 0.012,
      bevelSegments: 2,
    }),
  );
  frameGeo.rotateX(-Math.PI / 2);
  frameGeo.translate(0, -0.018, 0);

  const frameMat = trackMat(
    new THREE.MeshPhysicalMaterial({
      color: 0xf59e0b,
      metalness: 0.86,
      roughness: 0.22,
      clearcoat: 0.35,
    }),
  );
  const frameMesh = new THREE.Mesh(frameGeo, frameMat);
  isothermGroup.add(frameMesh);

  // Equilateral optical phase-map wafer inside bezel
  const waferGeo = trackGeo(new THREE.BufferGeometry());
  waferGeo.setAttribute(
    'position',
    new THREE.BufferAttribute(
      new Float32Array([
        VERTEX_A[0], 0, VERTEX_A[1],
        VERTEX_B[0], 0, VERTEX_B[1],
        VERTEX_C[0], 0, VERTEX_C[1],
      ]),
      3,
    ),
  );
  waferGeo.setAttribute(
    'normal',
    new THREE.BufferAttribute(new Float32Array([0, 1, 0, 0, 1, 0, 0, 1, 0]), 3),
  );
  waferGeo.setAttribute(
    'uv',
    new THREE.BufferAttribute(
      new Float32Array([
        GIBBS_UV_A[0], GIBBS_UV_A[1],
        GIBBS_UV_B[0], GIBBS_UV_B[1],
        GIBBS_UV_C[0], GIBBS_UV_C[1],
      ]),
      2,
    ),
  );
  waferGeo.setIndex([0, 1, 2]);

  let currentIsoTex = createIsothermSliceTexture(diagram, initialSliceK, maxAnisotropy);
  const isothermWaferMat = trackMat(
    new THREE.MeshBasicMaterial({
      map: currentIsoTex,
      transparent: true,
      opacity: 0.84,
      depthWrite: false,
      side: THREE.DoubleSide,
    }),
  );
  const waferMesh = new THREE.Mesh(waferGeo, isothermWaferMat);
  waferMesh.renderOrder = 5;
  waferMesh.layers.enable(1);
  waferMesh.userData = { surface: 'isotherm' };
  isothermGroup.add(waferMesh);
  raycastTargets.push(waferMesh);

  root.add(isothermGroup);

  const updateIsothermTexture = (tempK: number, aniso: number) => {
    const nextTex = createIsothermSliceTexture(diagram, tempK, aniso);
    isothermWaferMat.map = nextTex;
    isothermWaferMat.needsUpdate = true;
    currentIsoTex.dispose();
    currentIsoTex = nextTex;
  };

  const dispose = () => {
    currentIsoTex.dispose();
    geometries.forEach((g) => g.dispose());
    materials.forEach((m) => m.dispose());
    textures.forEach((t) => t.dispose());
  };

  return {
    root,
    liquidusGroup,
    solidusGroup,
    solvusGroup,
    monovariantGroup,
    invariantsGroup,
    wireframeLine,
    isothermGroup,
    isothermWaferMat,
    raycastTargets,
    updateIsothermTexture,
    dispose,
  };
}

/** Builds a clean perimeter curve tracing the 3 binary edge walls of a surface */
function buildPerimeterLine(
  diagram: ComputedPhaseDiagram,
  getTemp: (n: ComputedPhaseDiagram['nodes'][number]) => number,
  colorHex: number,
  opacity: number,
  trackGeo: <T extends THREE.BufferGeometry>(g: T) => T,
  trackMat: <T extends THREE.Material>(m: T) => T,
): THREE.Line {
  const { system, subdivisions: N, nodeIndexMap, nodes } = diagram;
  const stride = N + 1;
  const pts: THREE.Vector3[] = [];

  const pushNode = (i: number, j: number) => {
    const idx = nodeIndexMap[i * stride + j];
    if (idx < 0) return;
    const n = nodes[idx];
    const [wx, wy, wz] = baryToWorld(
      n.xA,
      n.xB,
      n.xC,
      getTemp(n),
      system.tempMinK,
      system.tempMaxK,
    );
    pts.push(new THREE.Vector3(wx, wy + 0.006, wz));
  };

  // Edge A -> B (k = 0 -> i + j = N)
  for (let s = 0; s <= N; s++) pushNode(N - s, s);
  // Edge B -> C (i = 0)
  for (let s = 1; s <= N; s++) pushNode(0, N - s);
  // Edge C -> A (j = 0)
  for (let s = 1; s <= N; s++) pushNode(s, 0);

  const geo = trackGeo(new THREE.BufferGeometry().setFromPoints(pts));
  const mat = trackMat(
    new THREE.LineBasicMaterial({
      color: colorHex,
      transparent: true,
      opacity,
    }),
  );
  return new THREE.Line(geo, mat);
}

/**
 * Composite 3D surface probe reticle with vertical drop-line and 3 barycentric
 * composition projection rays on the Gibbs base plate.
 */
export interface ProbeAssembly {
  group: THREE.Group;
  setPoint: (
    worldPos: THREE.Vector3,
    xA: number,
    xB: number,
    xC: number,
    accentHex: string,
  ) => void;
  setVisible: (v: boolean) => void;
  dispose: () => void;
}

export function buildProbeAssembly(): ProbeAssembly {
  const group = new THREE.Group();
  group.visible = false;

  const sphereGeo = new THREE.SphereGeometry(0.058, 16, 16);
  const sphereMat = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    emissive: 0xf59e0b,
    emissiveIntensity: 0.85,
    roughness: 0.15,
    metalness: 0.3,
  });
  const coreSphere = new THREE.Mesh(sphereGeo, sphereMat);
  coreSphere.renderOrder = 10;
  group.add(coreSphere);

  const ringGeo = new THREE.TorusGeometry(0.11, 0.014, 10, 28);
  ringGeo.rotateX(Math.PI / 2);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0xf8fafc,
    transparent: true,
    opacity: 0.9,
  });
  const outerRing = new THREE.Mesh(ringGeo, ringMat);
  outerRing.renderOrder = 10;
  group.add(outerRing);

  // Vertical plumb line down to Gibbs base
  const plumbPositions = new Float32Array(6);
  const plumbGeo = new THREE.BufferGeometry();
  plumbGeo.setAttribute('position', new THREE.BufferAttribute(plumbPositions, 3));
  const plumbMat = new THREE.LineBasicMaterial({
    color: 0xf8fafc,
    transparent: true,
    opacity: 0.72,
  });
  const plumbLine = new THREE.Line(plumbGeo, plumbMat);
  group.add(plumbLine);

  // 3 Barycentric projection guide lines on the base plane (6 vertices = 3 segments)
  const rayPositions = new Float32Array(18);
  const rayGeo = new THREE.BufferGeometry();
  rayGeo.setAttribute('position', new THREE.BufferAttribute(rayPositions, 3));
  const rayMat = new THREE.LineBasicMaterial({
    color: 0xf59e0b,
    transparent: true,
    opacity: 0.78,
  });
  const baryRays = new THREE.LineSegments(rayGeo, rayMat);
  group.add(baryRays);

  const baseDotGeo = new THREE.CircleGeometry(0.055, 20);
  baseDotGeo.rotateX(-Math.PI / 2);
  const baseDotMat = new THREE.MeshBasicMaterial({
    color: 0xf59e0b,
    transparent: true,
    opacity: 0.9,
    depthWrite: false,
  });
  const baseDot = new THREE.Mesh(baseDotGeo, baseDotMat);
  baseDot.renderOrder = 8;
  group.add(baseDot);

  const setPoint = (
    worldPos: THREE.Vector3,
    xA: number,
    xB: number,
    xC: number,
    accentHex: string,
  ) => {
    coreSphere.position.copy(worldPos);
    outerRing.position.copy(worldPos);
    sphereMat.emissive.set(accentHex);

    const baseY = PRISM_BASE_Y + 0.018;
    baseDot.position.set(worldPos.x, baseY, worldPos.z);

    // Update vertical plumb line
    const pArr = plumbGeo.attributes.position.array as Float32Array;
    pArr[0] = worldPos.x;
    pArr[1] = baseY;
    pArr[2] = worldPos.z;
    pArr[3] = worldPos.x;
    pArr[4] = worldPos.y;
    pArr[5] = worldPos.z;
    plumbGeo.attributes.position.needsUpdate = true;

    // Update 3 barycentric composition projection rays parallel to opposite edges
    // Constant xA projected to edge C-A (xB=0)
    const pA_x = xA * VERTEX_A[0] + (1 - xA) * VERTEX_C[0];
    const pA_z = xA * VERTEX_A[1] + (1 - xA) * VERTEX_C[1];
    // Constant xB projected to edge A-B (xC=0)
    const pB_x = (1 - xB) * VERTEX_A[0] + xB * VERTEX_B[0];
    const pB_z = (1 - xB) * VERTEX_A[1] + xB * VERTEX_B[1];
    // Constant xC projected to edge B-C (xA=0)
    const pC_x = (1 - xC) * VERTEX_B[0] + xC * VERTEX_C[0];
    const pC_z = (1 - xC) * VERTEX_B[1] + xC * VERTEX_C[1];

    const rArr = rayGeo.attributes.position.array as Float32Array;
    // Ray 1 (to A-C scale)
    rArr[0] = worldPos.x;
    rArr[1] = baseY;
    rArr[2] = worldPos.z;
    rArr[3] = pA_x;
    rArr[4] = baseY;
    rArr[5] = pA_z;
    // Ray 2 (to A-B scale)
    rArr[6] = worldPos.x;
    rArr[7] = baseY;
    rArr[8] = worldPos.z;
    rArr[9] = pB_x;
    rArr[10] = baseY;
    rArr[11] = pB_z;
    // Ray 3 (to B-C scale)
    rArr[12] = worldPos.x;
    rArr[13] = baseY;
    rArr[14] = worldPos.z;
    rArr[15] = pC_x;
    rArr[16] = baseY;
    rArr[17] = pC_z;
    rayGeo.attributes.position.needsUpdate = true;

    group.visible = true;
  };

  const setVisible = (v: boolean) => {
    group.visible = v;
  };

  const dispose = () => {
    sphereGeo.dispose();
    sphereMat.dispose();
    ringGeo.dispose();
    ringMat.dispose();
    plumbGeo.dispose();
    plumbMat.dispose();
    rayGeo.dispose();
    rayMat.dispose();
    baseDotGeo.dispose();
    baseDotMat.dispose();
  };

  return { group, setPoint, setVisible, dispose };
}
