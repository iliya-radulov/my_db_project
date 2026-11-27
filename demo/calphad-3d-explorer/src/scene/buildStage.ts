import * as THREE from 'three';
import {
  PRISM_BASE_Y,
  PRISM_HEIGHT,
  VERTEX_A,
  VERTEX_B,
  VERTEX_C,
  tempToY,
} from '../calphad/solver';
import { CalphadSystem } from '../calphad/types';
import {
  GIBBS_UV_A,
  GIBBS_UV_B,
  GIBBS_UV_C,
  createBrushedRoughnessTexture,
  createContactShadowTexture,
  createGibbsBaseTexture,
  createLabelSprite,
  createTickSprite,
} from './textures';

export interface StageAssembly {
  group: THREE.Group;
  dispose: () => void;
}

/**
 * Builds the composite multi-part scientific ternary spectrometric plinth &
 * calibrated temperature column assembly (grounded flush at y = 0).
 */
export function buildTernaryStage(
  system: CalphadSystem,
  maxAnisotropy: number,
): StageAssembly {
  const group = new THREE.Group();
  group.name = 'TernaryInstrumentStage';

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

  const brushedRough = trackTex(createBrushedRoughnessTexture());

  // 1. Studio floor plane receiving soft shadows (extends to horizon fog)
  const floorGeo = trackGeo(new THREE.CircleGeometry(42, 64));
  floorGeo.rotateX(-Math.PI / 2);
  const floorMat = trackMat(
    new THREE.MeshStandardMaterial({
      color: 0x0b1018,
      roughness: 0.88,
      metalness: 0.08,
    }),
  );
  const floorMesh = new THREE.Mesh(floorGeo, floorMat);
  floorMesh.position.y = -0.34;
  floorMesh.receiveShadow = true;
  group.add(floorMesh);

  // 2. Soft radial contact shadow directly beneath plinth (prevents floating feel)
  const contactTex = trackTex(createContactShadowTexture());
  const contactGeo = trackGeo(new THREE.PlaneGeometry(10.6, 10.6));
  contactGeo.rotateX(-Math.PI / 2);
  const contactMat = trackMat(
    new THREE.MeshBasicMaterial({
      map: contactTex,
      transparent: true,
      opacity: 0.62,
      depthWrite: false,
    }),
  );
  const contactShadow = new THREE.Mesh(contactGeo, contactMat);
  contactShadow.position.y = -0.32;
  group.add(contactShadow);

  // 3. Primary Silhouette: Chamfered triangular-hexagonal machined aluminum plinth
  // Build rounded-corner equilateral triangle shape expanded outward by 0.68 units
  const pad = 1.24;
  const vA = new THREE.Vector2(VERTEX_A[0] * pad, -VERTEX_A[1] * pad);
  const vB = new THREE.Vector2(VERTEX_B[0] * pad, -VERTEX_B[1] * pad);
  const vC = new THREE.Vector2(VERTEX_C[0] * pad, -VERTEX_C[1] * pad);

  const plinthShape = new THREE.Shape();
  const chamfer = 0.12;
  const pts = [vA, vB, vC];
  for (let i = 0; i < 3; i++) {
    const prev = pts[(i + 2) % 3];
    const curr = pts[i];
    const next = pts[(i + 1) % 3];
    const p1 = new THREE.Vector2().lerpVectors(curr, prev, chamfer);
    const p2 = new THREE.Vector2().lerpVectors(curr, next, chamfer);
    if (i === 0) plinthShape.moveTo(p1.x, p1.y);
    else plinthShape.lineTo(p1.x, p1.y);
    plinthShape.quadraticCurveTo(curr.x, curr.y, p2.x, p2.y);
  }
  plinthShape.closePath();

  const plinthGeo = trackGeo(
    new THREE.ExtrudeGeometry(plinthShape, {
      depth: 0.24,
      bevelEnabled: true,
      bevelThickness: 0.05,
      bevelSize: 0.06,
      bevelSegments: 3,
    }),
  );
  plinthGeo.rotateX(-Math.PI / 2);
  // Position so top of plinth sits cleanly at y = 0.05, bottom flush with studio floor (-0.34)
  plinthGeo.translate(0, -0.27, 0);

  const plinthMat = trackMat(
    new THREE.MeshStandardMaterial({
      color: 0x161d29,
      metalness: 0.68,
      roughness: 0.36,
      roughnessMap: brushedRough,
    }),
  );
  const plinthMesh = new THREE.Mesh(plinthGeo, plinthMat);
  plinthMesh.castShadow = true;
  plinthMesh.receiveShadow = true;
  group.add(plinthMesh);

  // Lower stepped foot collar under plinth (material roughness contrast)
  const footGeo = trackGeo(
    new THREE.CylinderGeometry(3.45, 3.62, 0.07, 6),
  );
  const footMat = trackMat(
    new THREE.MeshStandardMaterial({
      color: 0x0f141d,
      metalness: 0.35,
      roughness: 0.68,
    }),
  );
  const footMesh = new THREE.Mesh(footGeo, footMat);
  footMesh.position.y = -0.305;
  footMesh.rotation.y = Math.PI / 6;
  footMesh.receiveShadow = true;
  group.add(footMesh);

  // 4. Secondary Read: Inset Gibbs Ternary Composition Plate (high-res procedural CanvasTexture)
  const gibbsTex = trackTex(createGibbsBaseTexture(system, maxAnisotropy));
  const plateGeo = trackGeo(new THREE.BufferGeometry());
  const platePositions = new Float32Array([
    VERTEX_A[0], PRISM_BASE_Y, VERTEX_A[1],
    VERTEX_B[0], PRISM_BASE_Y, VERTEX_B[1],
    VERTEX_C[0], PRISM_BASE_Y, VERTEX_C[1],
  ]);
  const plateNormals = new Float32Array([0, 1, 0, 0, 1, 0, 0, 1, 0]);
  const plateUvs = new Float32Array([
    GIBBS_UV_A[0], GIBBS_UV_A[1],
    GIBBS_UV_B[0], GIBBS_UV_B[1],
    GIBBS_UV_C[0], GIBBS_UV_C[1],
  ]);
  plateGeo.setAttribute('position', new THREE.BufferAttribute(platePositions, 3));
  plateGeo.setAttribute('normal', new THREE.BufferAttribute(plateNormals, 3));
  plateGeo.setAttribute('uv', new THREE.BufferAttribute(plateUvs, 2));
  plateGeo.setIndex([0, 1, 2]);

  const plateMat = trackMat(
    new THREE.MeshStandardMaterial({
      map: gibbsTex,
      roughness: 0.58,
      metalness: 0.16,
      polygonOffset: true,
      polygonOffsetFactor: -1,
      polygonOffsetUnits: -1,
    }),
  );
  const plateMesh = new THREE.Mesh(plateGeo, plateMat);
  plateMesh.receiveShadow = true;
  group.add(plateMesh);

  // Machined brushed-titanium inner bezel framing the Gibbs triangle
  const bezelPath = new THREE.CatmullRomCurve3(
    [
      new THREE.Vector3(VERTEX_A[0], PRISM_BASE_Y + 0.008, VERTEX_A[1]),
      new THREE.Vector3(VERTEX_B[0], PRISM_BASE_Y + 0.008, VERTEX_B[1]),
      new THREE.Vector3(VERTEX_C[0], PRISM_BASE_Y + 0.008, VERTEX_C[1]),
    ],
    true,
    'catmullrom',
    0.01,
  );
  const bezelGeo = trackGeo(new THREE.TubeGeometry(bezelPath, 96, 0.026, 10, true));
  const titaniumMat = trackMat(
    new THREE.MeshPhysicalMaterial({
      color: 0x94a3b8,
      metalness: 0.92,
      roughness: 0.22,
      clearcoat: 0.25,
    }),
  );
  const bezelMesh = new THREE.Mesh(bezelGeo, titaniumMat);
  group.add(bezelMesh);

  // 5. Three Composite Machined Corner Temperature Vernier Columns
  // Each column: LatheGeometry stepped brass collar + steel rod + top finial cap
  const collarProfile = [
    new THREE.Vector2(0.0, 0.0),
    new THREE.Vector2(0.19, 0.0),
    new THREE.Vector2(0.19, 0.05),
    new THREE.Vector2(0.14, 0.08),
    new THREE.Vector2(0.14, 0.14),
    new THREE.Vector2(0.07, 0.17),
    new THREE.Vector2(0.04, 0.17),
  ];
  const collarGeo = trackGeo(new THREE.LatheGeometry(collarProfile, 24));
  const brassMat = trackMat(
    new THREE.MeshPhysicalMaterial({
      color: 0xd4a456,
      metalness: 0.92,
      roughness: 0.2,
      clearcoat: 0.3,
    }),
  );

  const finialProfile = [
    new THREE.Vector2(0.04, 0.0),
    new THREE.Vector2(0.09, 0.03),
    new THREE.Vector2(0.09, 0.08),
    new THREE.Vector2(0.04, 0.13),
    new THREE.Vector2(0.0, 0.14),
  ];
  const finialGeo = trackGeo(new THREE.LatheGeometry(finialProfile, 20));

  const rodGeo = trackGeo(new THREE.CylinderGeometry(0.024, 0.024, PRISM_HEIGHT, 16));
  const rodMat = trackMat(
    new THREE.MeshStandardMaterial({
      color: 0x64748b,
      metalness: 0.88,
      roughness: 0.28,
    }),
  );

  const corners: Array<readonly [number, number]> = [VERTEX_A, VERTEX_B, VERTEX_C];
  const topY = PRISM_BASE_Y + PRISM_HEIGHT;

  corners.forEach(([cx, cz], idx) => {
    const colGroup = new THREE.Group();
    colGroup.position.set(cx, 0, cz);

    const collar = new THREE.Mesh(collarGeo, brassMat);
    collar.position.y = 0.02;
    collar.castShadow = true;
    colGroup.add(collar);

    const rod = new THREE.Mesh(rodGeo, rodMat);
    rod.position.y = PRISM_BASE_Y + PRISM_HEIGHT / 2;
    colGroup.add(rod);

    const finial = new THREE.Mesh(finialGeo, brassMat);
    finial.position.y = topY;
    colGroup.add(finial);

    // Pure-element melting point precision ring indicator on the column
    const el = system.elements[idx];
    const meltY = tempToY(el.meltingPointK, system.tempMinK, system.tempMaxK);
    const meltRingGeo = trackGeo(new THREE.TorusGeometry(0.082, 0.018, 12, 24));
    meltRingGeo.rotateX(Math.PI / 2);
    const meltRingMat = trackMat(
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(el.color),
        metalness: 0.5,
        roughness: 0.25,
        emissive: new THREE.Color(el.color),
        emissiveIntensity: 0.35,
      }),
    );
    const meltRing = new THREE.Mesh(meltRingGeo, meltRingMat);
    meltRing.position.y = meltY;
    colGroup.add(meltRing);

    // Element corner plaque sprite pushed slightly outward radially
    const radialLen = Math.hypot(cx, cz) || 1;
    const outX = (cx / radialLen) * 0.78;
    const outZ = (cz / radialLen) * 0.78;
    const label = createLabelSprite(
      el.symbol,
      `Tm ${el.meltingPointK.toFixed(0)} K`,
      el.color,
      0.86,
    );
    label.position.set(outX, 0.22, outZ);
    trackMat(label.material);
    if (label.material.map) trackTex(label.material.map);
    colGroup.add(label);

    group.add(colGroup);
  });

  // 6. InstancedMesh Temperature Graduation Tick Rings along all 3 vertical columns (30 instances)
  const tickCountPerCol = 8;
  const totalTicks = tickCountPerCol * 3;
  const tickGeo = trackGeo(new THREE.TorusGeometry(0.052, 0.009, 8, 18));
  tickGeo.rotateX(Math.PI / 2);
  const tickMat = trackMat(
    new THREE.MeshStandardMaterial({
      color: 0xcbd5e1,
      metalness: 0.82,
      roughness: 0.26,
    }),
  );
  const tickInstanced = new THREE.InstancedMesh(tickGeo, tickMat, totalTicks);
  const dummy = new THREE.Object3D();
  let instIdx = 0;
  for (let c = 0; c < 3; c++) {
    const [cx, cz] = corners[c];
    for (let t = 0; t < tickCountPerCol; t++) {
      const frac = (t + 1) / (tickCountPerCol + 1);
      const y = PRISM_BASE_Y + frac * PRISM_HEIGHT;
      dummy.position.set(cx, y, cz);
      dummy.scale.setScalar(t % 2 === 1 ? 1.15 : 0.88);
      dummy.updateMatrix();
      tickInstanced.setMatrixAt(instIdx++, dummy.matrix);
    }
  }
  tickInstanced.instanceMatrix.needsUpdate = true;
  tickInstanced.computeBoundingSphere();
  group.add(tickInstanced);

  // Temperature scale labels along Vertex A column (left-front)
  const tempSteps = 5;
  for (let s = 0; s <= tempSteps; s++) {
    const frac = s / tempSteps;
    const tempVal = system.tempMinK + frac * (system.tempMaxK - system.tempMinK);
    const y = PRISM_BASE_Y + frac * PRISM_HEIGHT;
    const sprite = createTickSprite(`${Math.round(tempVal)} K`);
    sprite.position.set(VERTEX_A[0] - 0.56, y, VERTEX_A[1] + 0.14);
    trackMat(sprite.material);
    if (sprite.material.map) trackTex(sprite.material.map);
    group.add(sprite);
  }

  // 7. Subtle Top Reference Crown Frame (connects column tops)
  const crownPoints = [
    new THREE.Vector3(VERTEX_A[0], topY, VERTEX_A[1]),
    new THREE.Vector3(VERTEX_B[0], topY, VERTEX_B[1]),
    new THREE.Vector3(VERTEX_C[0], topY, VERTEX_C[1]),
    new THREE.Vector3(VERTEX_A[0], topY, VERTEX_A[1]),
  ];
  const crownGeo = trackGeo(new THREE.BufferGeometry().setFromPoints(crownPoints));
  const crownMat = trackMat(
    new THREE.LineBasicMaterial({
      color: 0x475569,
      transparent: true,
      opacity: 0.48,
    }),
  );
  const crownLine = new THREE.Line(crownGeo, crownMat);
  group.add(crownLine);

  const dispose = () => {
    geometries.forEach((g) => g.dispose());
    materials.forEach((m) => m.dispose());
    textures.forEach((t) => t.dispose());
  };

  return { group, dispose };
}
