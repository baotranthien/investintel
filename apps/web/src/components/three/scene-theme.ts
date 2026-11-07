/**
 * InvestIntel Three.js PBR Theme Tokens & Material Factory
 *
 * Strict Art Direction: Premium 3D Financial Intelligence — Minimalist Institutional
 * - Physical solid geometries with thickness, bevels, and tactile surface finishes.
 * - Multi-point studio lighting with ACES Filmic tonemapping.
 * - Solid brushed titanium, machined aluminum, satin champagne, frosted glass, deep graphite.
 * - ZERO wireframes as main shapes, ZERO neon, ZERO gaming RGB.
 */

import * as THREE from "three";

export const THREE_THEME = {
  colors: {
    // Canvas & Studio Backdrop
    canvasLight: 0xf5f5f7,
    canvasDark: 0x121214,
    canvasSubtle: 0xebebef,

    // Deep Charcoal & Graphite (Structural Foundations)
    obsidian: 0x0f1012,
    graphite: 0x16171a,
    charcoal: 0x1f2126,
    gunmetal: 0x2b2e36,
    slate: 0x3d414d,

    // Precious Metallics (Brushed, Machined, Satin)
    platinum: 0xe8e8ee,
    aluminum: 0xd6d6dc,
    silverMuted: 0xbebec6,
    warmSilver: 0xa8a8b2,
    silverDk: 0x767884,

    // Institutional Subtle Accents
    champagneGold: 0xc8a462,
    champagneSoft: 0xdfcaa0,
    calmEmerald: 0x247846,
    calmEmeraldSoft: 0x389b5c,
    mutedCarmine: 0xba322a,
    deepNavy: 0x1a2434,
  },

  materials: {
    // 1. Brushed Titanium / Dark Metal (Primary Structural Bodies)
    createBrushedTitanium: (color = 0x24262d, roughness = 0.35, metalness = 0.88) =>
      new THREE.MeshStandardMaterial({
        color,
        roughness,
        metalness,
      }),

    // 2. Machined / Satin Aluminum (Highlight Rings, Caps & Sliders)
    createSatinAluminum: (color = 0xd6d6dc, roughness = 0.28, metalness = 0.92) =>
      new THREE.MeshStandardMaterial({
        color,
        roughness,
        metalness,
      }),

    // 3. Satin Champagne Gold (Key Financial Telemetry & Focal Markers)
    createSatinChampagne: (color = 0xc8a462, roughness = 0.25, metalness = 0.88) =>
      new THREE.MeshStandardMaterial({
        color,
        roughness,
        metalness,
      }),

    // 4. Frosted Smoked Glass / Optical Translucency (Protective Mantle & Range Shells)
    createFrostedGlass: (
      color = 0xe4e4ec,
      transmission = 0.65,
      roughness = 0.32,
      opacity = 0.85
    ) =>
      new THREE.MeshPhysicalMaterial({
        color,
        transmission,
        opacity,
        transparent: true,
        roughness,
        ior: 1.45,
        depthWrite: false,
      }),

    // 5. Deep Matte Graphite (Base Pedestals & Non-Reflective Chassis)
    createDeepGraphite: (color = 0x16171a, roughness = 0.55, metalness = 0.6) =>
      new THREE.MeshStandardMaterial({
        color,
        roughness,
        metalness,
      }),

    // 6. Calm Financial Emerald (Margin of Safety & Undervalued Tickers)
    createEmeraldAccent: (color = 0x247846, roughness = 0.3, metalness = 0.75) =>
      new THREE.MeshStandardMaterial({
        color,
        roughness,
        metalness,
      }),

    // 7. Volumetric Connecting Tubes (Synaptic pathways, data conduits)
    createTubeMaterial: (color = 0x2e313b, roughness = 0.4, metalness = 0.8) =>
      new THREE.MeshStandardMaterial({
        color,
        roughness,
        metalness,
      }),

    // 8. Contact Ground Shadow (Soft Radial Falloff Disc)
    createContactShadowMesh: (radius = 5.0, opacity = 0.28): THREE.Mesh => {
      const canvas = document.createElement("canvas");
      canvas.width = 128;
      canvas.height = 128;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
        grad.addColorStop(0, `rgba(18, 18, 20, ${opacity})`);
        grad.addColorStop(0.4, `rgba(18, 18, 20, ${opacity * 0.6})`);
        grad.addColorStop(0.75, `rgba(18, 18, 20, ${opacity * 0.18})`);
        grad.addColorStop(1, "rgba(18, 18, 20, 0)");
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 128, 128);
      }
      const texture = new THREE.CanvasTexture(canvas);
      const geom = new THREE.PlaneGeometry(radius * 2, radius * 2);
      const mat = new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true,
        depthWrite: false,
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.rotation.x = -Math.PI / 2;
      return mesh;
    },
  },
};
