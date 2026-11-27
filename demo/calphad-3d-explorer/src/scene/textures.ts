import * as THREE from 'three';
import { CalphadSystem, ComputedPhaseDiagram } from '../calphad/types';
import { sampleDiagramGrid } from '../calphad/solver';
import { computedStateAt, phaseSetKey } from '../calphad/computedLookup';

/**
 * Generates a high-resolution procedural Gibbs ternary triangle coordinate grid
 * mapped cleanly to UV coordinates where:
 *   Vertex A = (0.05, 0.92)
 *   Vertex B = (0.95, 0.92)
 *   Vertex C = (0.50, 0.140577)  (equilateral proportion in UV space)
 */
export const GIBBS_UV_A: readonly [number, number] = [0.05, 0.92];
export const GIBBS_UV_B: readonly [number, number] = [0.95, 0.92];
export const GIBBS_UV_C: readonly [number, number] = [
  0.5,
  0.92 - 0.9 * (Math.sqrt(3) / 2),
];

function baryToCanvas(
  xA: number,
  xB: number,
  xC: number,
  size: number,
): [number, number] {
  const u = xA * GIBBS_UV_A[0] + xB * GIBBS_UV_B[0] + xC * GIBBS_UV_C[0];
  const v = xA * GIBBS_UV_A[1] + xB * GIBBS_UV_B[1] + xC * GIBBS_UV_C[1];
  // Three.js flipY=true by default -> canvas Y=0 is UV v=1
  return [u * size, (1 - v) * size];
}

export function createGibbsBaseTexture(
  system: CalphadSystem,
  maxAnisotropy: number,
): THREE.CanvasTexture {
  const size = 1024;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;

  // Dark brushed anodized slate plate background
  const grad = ctx.createRadialGradient(
    size * 0.5,
    size * 0.55,
    size * 0.06,
    size * 0.5,
    size * 0.55,
    size * 0.55,
  );
  grad.addColorStop(0, '#161F2E');
  grad.addColorStop(1, '#0E141F');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  // Subtle metallic micro-grain lines
  ctx.strokeStyle = 'rgba(255,255,255,0.018)';
  ctx.lineWidth = 1;
  for (let y = 0; y < size; y += 3) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(size, y);
    ctx.stroke();
  }

  // Draw barycentric grid lines at every 10% mole fraction
  for (let step = 1; step <= 9; step++) {
    const f = step / 10;
    const isMajor = step === 5;
    ctx.strokeStyle = isMajor
      ? 'rgba(148, 163, 184, 0.34)'
      : 'rgba(148, 163, 184, 0.14)';
    ctx.lineWidth = isMajor ? 2 : 1.1;

    // Constant xA
    const [a0x, a0y] = baryToCanvas(f, 1 - f, 0, size);
    const [a1x, a1y] = baryToCanvas(f, 0, 1 - f, size);
    ctx.beginPath();
    ctx.moveTo(a0x, a0y);
    ctx.lineTo(a1x, a1y);
    ctx.stroke();

    // Constant xB
    const [b0x, b0y] = baryToCanvas(1 - f, f, 0, size);
    const [b1x, b1y] = baryToCanvas(0, f, 1 - f, size);
    ctx.beginPath();
    ctx.moveTo(b0x, b0y);
    ctx.lineTo(b1x, b1y);
    ctx.stroke();

    // Constant xC
    const [c0x, c0y] = baryToCanvas(1 - f, 0, f, size);
    const [c1x, c1y] = baryToCanvas(0, 1 - f, f, size);
    ctx.beginPath();
    ctx.moveTo(c0x, c0y);
    ctx.lineTo(c1x, c1y);
    ctx.stroke();
  }

  // Outer triangle precision border
  const [pAx, pAy] = baryToCanvas(1, 0, 0, size);
  const [pBx, pBy] = baryToCanvas(0, 1, 0, size);
  const [pCx, pCy] = baryToCanvas(0, 0, 1, size);

  ctx.strokeStyle = 'rgba(226, 232, 240, 0.55)';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(pAx, pAy);
  ctx.lineTo(pBx, pBy);
  ctx.lineTo(pCx, pCy);
  ctx.closePath();
  ctx.stroke();

  // Numeric mole-fraction labels along edges (0.2, 0.4, 0.6, 0.8)
  ctx.font = '500 22px "IBM Plex Mono", monospace';
  ctx.fillStyle = 'rgba(203, 213, 225, 0.72)';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  for (const step of [2, 4, 6, 8]) {
    const f = step / 10;
    const label = `${step * 10}`;
    // Along A-B edge (increasing B)
    const [abx, aby] = baryToCanvas(1 - f, f, 0, size);
    ctx.fillText(label, abx, aby + 24);
    // Along B-C edge (increasing C)
    const [bcx, bcy] = baryToCanvas(0, 1 - f, f, size);
    ctx.fillText(label, bcx + 26, bcy - 10);
    // Along C-A edge (increasing A)
    const [cax, cay] = baryToCanvas(f, 0, 1 - f, size);
    ctx.fillText(label, cax - 26, cay - 10);
  }

  // Subtle center watermark coordinate crosshair (technical reticle, not text)
  const [cx, cy] = baryToCanvas(1 / 3, 1 / 3, 1 / 3, size);
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.35)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, 12, 0, Math.PI * 2);
  ctx.stroke();

  // Edge binary titles
  ctx.font = '600 20px "Plus Jakarta Sans", sans-serif';
  ctx.fillStyle = 'rgba(148, 163, 184, 0.7)';
  const [e0, e1, e2] = system.elements;
  const [midABx, midABy] = baryToCanvas(0.5, 0.5, 0, size);
  ctx.fillText(`x(${e1.symbol}) at.% →`, midABx, midABy + 52);

  ctx.save();
  const [midBCx, midBCy] = baryToCanvas(0, 0.5, 0.5, size);
  ctx.translate(midBCx + 54, midBCy - 26);
  ctx.rotate(Math.PI / 3);
  ctx.fillText(`← x(${e2.symbol}) at.%`, 0, 0);
  ctx.restore();

  ctx.save();
  const [midCAx, midCAy] = baryToCanvas(0.5, 0, 0.5, size);
  ctx.translate(midCAx - 54, midCAy - 26);
  ctx.rotate(-Math.PI / 3);
  ctx.fillText(`x(${e0.symbol}) at.% →`, 0, 0);
  ctx.restore();

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = maxAnisotropy;
  texture.needsUpdate = true;
  return texture;
}

/**
 * Generates a dynamic 2D CALPHAD isothermal section map rendered directly onto
 * the equilateral triangular wafer at temperature `tempK`.
 */
export function createIsothermSliceTexture(
  diagram: ComputedPhaseDiagram,
  tempK: number,
  maxAnisotropy: number,
): THREE.CanvasTexture {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const imgData = ctx.createImageData(size, size);
  const data = imgData.data;

  // Map phase IDs to calibrated RGB tuples
  const phaseColors = new Map<string, [number, number, number]>();
  for (const p of diagram.system.phases) {
    const c = new THREE.Color(p.color);
    phaseColors.set(p.id, [
      Math.round(c.r * 255),
      Math.round(c.g * 255),
      Math.round(c.b * 255),
    ]);
  }
  const liquidRgb: [number, number, number] = [14, 116, 144]; // Deep liquid teal-cyan

  // Precompute UV->barycentric transform constants
  const uA = GIBBS_UV_A[0];
  const vA = GIBBS_UV_A[1];
  const uB = GIBBS_UV_B[0];
  const vB = GIBBS_UV_B[1];
  const uC = GIBBS_UV_C[0];
  const vC = GIBBS_UV_C[1];
  const det = (vB - vC) * (uA - uC) + (uC - uB) * (vA - vC);

  // Store region codes for crisp boundary edge detection
  const regionCode = new Int16Array(size * size).fill(-1);
  const phaseIdToIdx = new Map<string, number>();
  const phaseSetCodes = new Map<string, number>(); // computed datasets: one region code per phase set
  const liquidPhaseId = diagram.system.phases[0]?.id;
  diagram.system.phases.forEach((p, idx) => phaseIdToIdx.set(p.id, idx));

  for (let py = 0; py < size; py++) {
    const v = 1 - py / (size - 1);
    for (let px = 0; px < size; px++) {
      const u = px / (size - 1);
      const xA = ((vB - vC) * (u - uC) + (uC - uB) * (v - vC)) / det;
      const xB = ((vC - vA) * (u - uC) + (uA - uC) * (v - vC)) / det;
      const xC = 1 - xA - xB;

      const idx4 = (py * size + px) * 4;
      if (xA < -0.002 || xB < -0.002 || xC < -0.002) {
        data[idx4 + 3] = 0;
        continue;
      }

      const cxA = Math.max(0, xA);
      const cxB = Math.max(0, xB);
      const cxC = Math.max(0, xC);
      const sum = cxA + cxB + cxC || 1;
      const computed = diagram.system.computed;
      if (computed) {
        // Real equilibrium at the nearest grid point and temperature: colour by the phase set
        const st = computedStateAt(computed, cxA / sum, cxB / sum, tempK);
        let rr = 100;
        let gg = 100;
        let bb = 110;
        let aa = 90; // grey: pycalphad did not converge here
        let code = 1;
        if (st.phases) {
          const key = phaseSetKey(st.phases);
          if (!phaseSetCodes.has(key)) phaseSetCodes.set(key, phaseSetCodes.size + 2);
          code = phaseSetCodes.get(key)!;
          const parts = Object.entries(st.phases).sort((p1, p2) => p2[1] - p1[1]);
          const rgbOf = (id: string) =>
            id === liquidPhaseId ? liquidRgb : phaseColors.get(id) ?? [148, 163, 184];
          if (parts.length === 1) {
            [rr, gg, bb] = rgbOf(parts[0][0]);
          } else {
            // two or more phases: stripes of the two largest, so phase fields stay readable
            const stripe = ((px + py) % 10) < 5;
            [rr, gg, bb] = rgbOf(stripe ? parts[0][0] : parts[1][0]);
          }
          aa = parts.some(([id]) => id === liquidPhaseId) ? 150 : 215;
        }
        regionCode[py * size + px] = code;
        data[idx4] = rr;
        data[idx4 + 1] = gg;
        data[idx4 + 2] = bb;
        data[idx4 + 3] = aa;
        continue;
      }

      const sample = sampleDiagramGrid(diagram, cxA / sum, cxB / sum, cxC / sum);

      let r = liquidRgb[0];
      let g = liquidRgb[1];
      let b = liquidRgb[2];
      let alpha = 155;
      let code = 0; // 0 = liquid

      if (tempK > sample.tLiquidus) {
        // Liquid phase
        r = liquidRgb[0];
        g = liquidRgb[1];
        b = liquidRgb[2];
        alpha = 115;
        code = 0;
      } else if (tempK >= sample.tSolidus) {
        // Two-phase L + Primary Solid mushy zone with diagonal tie-line stripe cue
        const pRgb = phaseColors.get(sample.primaryPhaseId) ?? [148, 163, 184];
        const fSol =
          (sample.tLiquidus - tempK) /
          Math.max(1, sample.tLiquidus - sample.tSolidus);
        const stripe = ((px + py) % 10) < 2 ? 1.18 : 0.94;
        r = Math.min(255, (liquidRgb[0] * (1 - fSol * 0.65) + pRgb[0] * (fSol * 0.65)) * stripe);
        g = Math.min(255, (liquidRgb[1] * (1 - fSol * 0.65) + pRgb[1] * (fSol * 0.65)) * stripe);
        b = Math.min(255, (liquidRgb[2] * (1 - fSol * 0.65) + pRgb[2] * (fSol * 0.65)) * stripe);
        alpha = 195;
        code = 10 + (phaseIdToIdx.get(sample.primaryPhaseId) ?? 1);
      } else {
        // Fully solid region (check solvus dome)
        const inSolvus = !Number.isNaN(sample.tSolvus) && tempK <= sample.tSolvus;
        const activeId = inSolvus ? sample.solidPhaseId : sample.primaryPhaseId;
        const pRgb = phaseColors.get(activeId) ?? [148, 163, 184];
        const boost = inSolvus ? 1.05 : 0.82;
        r = Math.min(255, pRgb[0] * boost);
        g = Math.min(255, pRgb[1] * boost);
        b = Math.min(255, pRgb[2] * boost);
        alpha = 215;
        code = (inSolvus ? 30 : 20) + (phaseIdToIdx.get(activeId) ?? 1);
      }

      regionCode[py * size + px] = code;
      data[idx4] = r;
      data[idx4 + 1] = g;
      data[idx4 + 2] = b;
      data[idx4 + 3] = alpha;
    }
  }

  // Highlight crisp phase boundaries where adjacent pixels have differing region codes
  for (let py = 1; py < size - 1; py++) {
    for (let px = 1; px < size - 1; px++) {
      const c = regionCode[py * size + px];
      if (c < 0) continue;
      const cR = regionCode[py * size + (px + 1)];
      const cD = regionCode[(py + 1) * size + px];
      if ((cR >= 0 && cR !== c) || (cD >= 0 && cD !== c)) {
        const idx4 = (py * size + px) * 4;
        data[idx4] = 250;
        data[idx4 + 1] = 245;
        data[idx4 + 2] = 230;
        data[idx4 + 3] = 255;
      }
    }
  }

  ctx.putImageData(imgData, 0, 0);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = maxAnisotropy;
  texture.needsUpdate = true;
  return texture;
}

/** Soft radial ambient occlusion contact shadow for grounding the plinth */
export function createContactShadowTexture(): THREE.CanvasTexture {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;

  const grad = ctx.createRadialGradient(
    size * 0.5,
    size * 0.5,
    size * 0.14,
    size * 0.5,
    size * 0.5,
    size * 0.5,
  );
  grad.addColorStop(0, 'rgba(2, 4, 9, 0.92)');
  grad.addColorStop(0.55, 'rgba(2, 4, 9, 0.55)');
  grad.addColorStop(0.82, 'rgba(2, 4, 9, 0.14)');
  grad.addColorStop(1, 'rgba(2, 4, 9, 0.0)');

  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

/** Procedural brushed anodized metal roughness map (linear data space) */
export function createBrushedRoughnessTexture(): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = '#5a5a5a';
  ctx.fillRect(0, 0, size, size);

  // Deterministic pseudo-random brushed lines
  let seed = 4217;
  const rand = () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };

  for (let i = 0; i < 650; i++) {
    const y = Math.floor(rand() * size);
    const v = 72 + Math.floor(rand() * 44);
    ctx.fillStyle = `rgb(${v},${v},${v})`;
    ctx.fillRect(0, y, size, 1);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(3, 3);
  texture.colorSpace = THREE.NoColorSpace;
  texture.needsUpdate = true;
  return texture;
}

/** Crisp billboard label sprite for corner elements & temperature ticks */
export function createLabelSprite(
  primaryText: string,
  secondaryText: string | null,
  accentColor: string,
  scale = 1,
): THREE.Sprite {
  const width = 320;
  const height = secondaryText ? 116 : 76;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d')!;

  // Crisp dark calibrated badge surface
  ctx.fillStyle = 'rgba(11, 16, 24, 0.88)';
  ctx.strokeStyle = 'rgba(148, 163, 184, 0.34)';
  ctx.lineWidth = 2;
  const r = 14;
  ctx.beginPath();
  ctx.roundRect(4, 4, width - 8, height - 8, r);
  ctx.fill();
  ctx.stroke();

  // Small top accent bar inside label
  ctx.fillStyle = accentColor;
  ctx.fillRect(22, 16, 42, 4);

  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.font = '700 38px "Plus Jakarta Sans", sans-serif';
  ctx.fillStyle = '#F8FAFC';
  ctx.fillText(primaryText, 22, secondaryText ? 52 : height / 2 + 4);

  if (secondaryText) {
    ctx.font = '500 22px "IBM Plex Mono", monospace';
    ctx.fillStyle = '#94A3B8';
    ctx.fillText(secondaryText, 22, 88);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;

  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
    depthWrite: false,
  });

  const sprite = new THREE.Sprite(material);
  const aspect = width / height;
  sprite.scale.set(0.68 * aspect * scale, 0.68 * scale, 1);
  sprite.renderOrder = 20;
  return sprite;
}

/** Minimal clean numeric axis tick sprite (no box background) */
export function createTickSprite(text: string): THREE.Sprite {
  const width = 180;
  const height = 56;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d')!;

  ctx.font = '500 28px "IBM Plex Mono", monospace';
  ctx.fillStyle = 'rgba(203, 213, 225, 0.85)';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, width - 10, height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;

  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
  });

  const sprite = new THREE.Sprite(material);
  sprite.scale.set(0.86, 0.27, 1);
  sprite.renderOrder = 15;
  return sprite;
}
