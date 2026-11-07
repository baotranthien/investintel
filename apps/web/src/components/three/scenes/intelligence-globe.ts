/**
 * Concept 1: AI Intelligence Globe — Ultra-Premium 3D Product Visualization
 * Exclusively active within the dedicated Hero Visual Stage on the Home page ("/").
 *
 * Art Direction: Minimalist Institutional Financial Intelligence / Apple Daylight Minimalist
 * - Solid PBR dual-shell core: Brushed titanium / obsidian core + frosted optical glass mantle.
 * - Precision horology datum rings (Equator, Cancer, Capricorn, Meridian) with champagne accents.
 * - Faceted beveled landmass relief plates catching sharp studio specular highlights.
 * - Multi-axis gyroscopic orbital rings with machined telemetry notches & sensor stations.
 * - Vietnam focal hubs (HCMC & Hanoi) + Global financial capitals with volumetric 3D conduits.
 * - Micro-particle financial data nebula: 280 subtle market telemetry points orbiting in harmony.
 * - 3-point studio lighting (Key, Fill, Rim) + soft contact shadow grounding.
 * - Centered strictly inside its dedicated stage, completely decoupled from text and sidebar.
 */

import * as THREE from "three";
import { THREE_THEME } from "../scene-theme";
import type { InvestIntelScene, SceneContextState } from "./types";

interface HubCoordinate {
  name: string;
  lat: number;
  lon: number;
  isPrimary?: boolean;
}

const FINANCIAL_HUBS: HubCoordinate[] = [
  { name: "Ho Chi Minh City", lat: 10.8231, lon: 106.6297, isPrimary: true },
  { name: "Hanoi", lat: 21.0285, lon: 105.8542, isPrimary: true },
  { name: "Singapore", lat: 1.3521, lon: 103.8198 },
  { name: "Tokyo", lat: 35.6762, lon: 139.6503 },
  { name: "Hong Kong", lat: 22.3193, lon: 114.1694 },
  { name: "London", lat: 51.5074, lon: -0.1278 },
  { name: "Frankfurt", lat: 50.1109, lon: 8.6821 },
  { name: "New York", lat: 40.7128, lon: -74.006 },
];

// Major continental landmass coordinates for solid extruded relief plates
const CONTINENT_CENTROIDS = [
  { lat: 16, lon: 107, sx: 1.1, sy: 0.9, rot: 0.2 }, // Southeast Asia / Indochina
  { lat: 35, lon: 105, sx: 1.6, sy: 1.2, rot: -0.1 }, // East Asia
  { lat: 50, lon: 15, sx: 1.4, sy: 1.0, rot: 0.3 },  // Central Europe
  { lat: 40, lon: -100, sx: 1.7, sy: 1.3, rot: -0.2 }, // North America
  { lat: -15, lon: -60, sx: 1.2, sy: 1.5, rot: 0.1 }, // South America
  { lat: 5, lon: 20, sx: 1.5, sy: 1.6, rot: 0.0 },   // Central Africa
  { lat: -25, lon: 135, sx: 1.2, sy: 1.0, rot: 0.4 }, // Australia
  { lat: 20, lon: 78, sx: 1.1, sy: 1.1, rot: -0.15 }, // South Asia / India
  { lat: 25, lon: 45, sx: 1.0, sy: 0.8, rot: 0.25 }, // Middle East
  { lat: 60, lon: 85, sx: 1.8, sy: 1.0, rot: 0.05 }, // North Eurasia
  { lat: -30, lon: 25, sx: 0.9, sy: 0.9, rot: 0.0 },  // Southern Africa
  { lat: 55, lon: -115, sx: 1.3, sy: 0.9, rot: -0.1 }, // Canada / Pacific Rim
];

function latLonToVector3(lat: number, lon: number, radius: number): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  const x = -(radius * Math.sin(phi) * Math.cos(theta));
  const z = radius * Math.sin(phi) * Math.sin(theta);
  const y = radius * Math.cos(phi);
  return new THREE.Vector3(x, y, z);
}

export class IntelligenceGlobeScene implements InvestIntelScene {
  id = "intelligence-globe";
  title = "AI Intelligence Globe";
  description = "Quả cầu dữ liệu & mạng lưới viễn thám tài chính toàn cầu (Ultra-Premium 3D)";

  private group: THREE.Group = new THREE.Group();
  private globeRadius = 2.15;
  private disposables: { dispose: () => void }[] = [];

  // Animated solid elements
  private coreMesh!: THREE.Mesh;
  private mantleMesh!: THREE.Mesh;
  private orbitTorus1!: THREE.Mesh;
  private orbitTorus2!: THREE.Mesh;
  private orbitTorus3!: THREE.Mesh;
  private particlePoints!: THREE.Points;
  private arcPackets: { mesh: THREE.Mesh; curve: THREE.Curve<THREE.Vector3>; progress: number; speed: number }[] = [];

  // Studio lighting
  private keyLight!: THREE.DirectionalLight;
  private fillLight!: THREE.DirectionalLight;
  private rimLight!: THREE.DirectionalLight;

  // Mouse inertia
  private targetRotX = 0.16;
  private targetRotY = 0.0;
  private currentRotX = 0.16;
  private currentRotY = 0.0;

  init(
    container: HTMLElement,
    scene: THREE.Scene,
    camera: THREE.PerspectiveCamera,
    _renderer: THREE.WebGLRenderer
  ): void {
    this.group = new THREE.Group();
    scene.add(this.group);

    // Studio Camera Perspective: centered on the 3D showcase
    camera.position.set(0, 0.35, 7.6);
    camera.lookAt(0, 0, 0);

    // Group centered inside dedicated frame
    this.group.position.set(0, 0.05, 0);

    const width = container.clientWidth || 460;
    const height = container.clientHeight || 360;
    this.updateResponsiveLayout(width, height);

    // 1. Studio 3-Point Lighting Rig
    this.setupStudioLighting(scene);

    // 2. Solid Dual-Shell Core & Relief Landmass
    this.buildSolidPlanetaryCore();

    // 3. Precision Horology Datum Rings (Equator, Cancer, Capricorn, Meridian)
    this.buildDatumRings();

    // 4. Solid Engineered Multi-Axis Gyro-Orbitals (TorusGeometry) with Telemetry Notches
    this.buildSolidOrbitalRings();

    // 5. Solid Data Hub Pedestals & Volumetric 3D Tubes
    this.buildHubsAndVolumetricTubes();

    // 6. Micro-Particle Financial Data Nebula
    this.buildDataNebula();

    // 7. Studio Ground Contact Shadow
    this.buildContactShadow();
  }

  private updateResponsiveLayout(width: number, height: number): void {
    const minDim = Math.min(width, height);
    if (minDim < 320) {
      this.group.scale.setScalar(0.82);
    } else if (minDim < 380) {
      this.group.scale.setScalar(0.92);
    } else {
      this.group.scale.setScalar(1.0);
    }
  }

  private setupStudioLighting(scene: THREE.Scene): void {
    // Key Light: Overhead front-right, warm white, sculpts primary volume
    this.keyLight = new THREE.DirectionalLight(0xfffdf8, 1.8);
    this.keyLight.position.set(6, 8, 7);
    scene.add(this.keyLight);

    // Fill Light: Soft cool fill from opposite lower quadrant
    this.fillLight = new THREE.DirectionalLight(0xdce5f2, 0.72);
    this.fillLight.position.set(-6, -3, 5);
    scene.add(this.fillLight);

    // Rim Light: High-back kicker light defining the sphere silhouette
    this.rimLight = new THREE.DirectionalLight(0xffffff, 1.55);
    this.rimLight.position.set(0, 7, -8);
    scene.add(this.rimLight);

    // Ambient bounce
    const ambLight = new THREE.AmbientLight(0x1e2026, 0.68);
    scene.add(ambLight);
  }

  private buildSolidPlanetaryCore(): void {
    // 1. Solid Brushed Titanium Inner Core
    const coreGeom = new THREE.SphereGeometry(this.globeRadius, 54, 54);
    const coreMat = THREE_THEME.materials.createBrushedTitanium(
      0x16181d, // Deep obsidian graphite
      0.32,
      0.9
    );
    this.coreMesh = new THREE.Mesh(coreGeom, coreMat);
    this.group.add(this.coreMesh);
    this.disposables.push(coreGeom, coreMat);

    // 2. Solid Relief Landmass Plateaus (Faceted physical geometry with chamfered top)
    const plateGeom = new THREE.CylinderGeometry(0.36, 0.40, 0.06, 12);
    const plateMat = THREE_THEME.materials.createBrushedTitanium(
      0x2c2f38, // Gunmetal titanium with sharp specular sheen
      0.38,
      0.82
    );
    this.disposables.push(plateGeom, plateMat);

    CONTINENT_CENTROIDS.forEach((c) => {
      const pos = latLonToVector3(c.lat, c.lon, this.globeRadius + 0.025);
      const mesh = new THREE.Mesh(plateGeom, plateMat);
      mesh.position.copy(pos);
      // Align cylinder normal with radial vector
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), pos.clone().normalize());
      mesh.scale.set(c.sx, 1, c.sy);
      mesh.rotateY(c.rot);
      this.group.add(mesh);
    });

    // 3. Frosted Optical Glass Mantle (Concentric subtle outer refractive shell)
    const mantleGeom = new THREE.SphereGeometry(this.globeRadius * 1.03, 54, 54);
    const mantleMat = THREE_THEME.materials.createFrostedGlass(
      0xe8e8f2,
      0.72,
      0.24,
      0.8
    );
    this.mantleMesh = new THREE.Mesh(mantleGeom, mantleMat);
    this.group.add(this.mantleMesh);
    this.disposables.push(mantleGeom, mantleMat);
  }

  private buildDatumRings(): void {
    // Precision horology datum rings hugging the core mantle
    // A. Equatorial Datum Ring (Satin Champagne Gold)
    const eqGeom = new THREE.TorusGeometry(this.globeRadius * 1.034, 0.010, 8, 96);
    const eqMat = THREE_THEME.materials.createSatinChampagne(
      THREE_THEME.colors.champagneGold,
      0.22,
      0.92
    );
    const eqMesh = new THREE.Mesh(eqGeom, eqMat);
    eqMesh.rotation.x = Math.PI / 2;
    this.group.add(eqMesh);
    this.disposables.push(eqGeom, eqMat);

    // B. Prime Meridian Datum Ring (Machined Aluminum)
    const merGeom = new THREE.TorusGeometry(this.globeRadius * 1.034, 0.007, 8, 96);
    const merMat = THREE_THEME.materials.createSatinAluminum(
      THREE_THEME.colors.aluminum,
      0.28,
      0.94
    );
    const merMesh = new THREE.Mesh(merGeom, merMat);
    this.group.add(merMesh);
    this.disposables.push(merGeom, merMat);

    // C. 90° Cross Longitude Datum Ring
    const crossGeom = new THREE.TorusGeometry(this.globeRadius * 1.034, 0.007, 8, 96);
    const crossMesh = new THREE.Mesh(crossGeom, merMat);
    crossMesh.rotation.y = Math.PI / 2;
    this.group.add(crossMesh);
    this.disposables.push(crossGeom);
  }

  private buildSolidOrbitalRings(): void {
    // Ring 1: Solid Satin Champagne Gold Torus (Tilted ~22.5°)
    const torus1Geom = new THREE.TorusGeometry(this.globeRadius * 1.38, 0.034, 16, 96);
    const torus1Mat = THREE_THEME.materials.createSatinChampagne(
      THREE_THEME.colors.champagneGold,
      0.22,
      0.92
    );
    this.orbitTorus1 = new THREE.Mesh(torus1Geom, torus1Mat);
    this.orbitTorus1.rotation.x = THREE.MathUtils.degToRad(22.5);
    this.orbitTorus1.rotation.z = THREE.MathUtils.degToRad(15);
    this.group.add(this.orbitTorus1);
    this.disposables.push(torus1Geom, torus1Mat);

    // Ring 2: Solid Machined Aluminum Torus (Tilted ~-42°)
    const torus2Geom = new THREE.TorusGeometry(this.globeRadius * 1.6, 0.026, 16, 96);
    const torus2Mat = THREE_THEME.materials.createSatinAluminum(
      THREE_THEME.colors.aluminum,
      0.25,
      0.95
    );
    this.orbitTorus2 = new THREE.Mesh(torus2Geom, torus2Mat);
    this.orbitTorus2.rotation.x = THREE.MathUtils.degToRad(-42);
    this.orbitTorus2.rotation.y = THREE.MathUtils.degToRad(28);
    this.group.add(this.orbitTorus2);
    this.disposables.push(torus2Geom, torus2Mat);

    // Ring 3: Solid Dark Titanium Polar Accent Ring
    const torus3Geom = new THREE.TorusGeometry(this.globeRadius * 1.78, 0.018, 12, 96);
    const torus3Mat = THREE_THEME.materials.createBrushedTitanium(
      THREE_THEME.colors.gunmetal,
      0.38,
      0.85
    );
    this.orbitTorus3 = new THREE.Mesh(torus3Geom, torus3Mat);
    this.orbitTorus3.rotation.x = THREE.MathUtils.degToRad(74);
    this.orbitTorus3.rotation.z = THREE.MathUtils.degToRad(-35);
    this.group.add(this.orbitTorus3);
    this.disposables.push(torus3Geom, torus3Mat);

    // Machined solid telemetry notch blocks on Ring 1
    const notchGeom = new THREE.BoxGeometry(0.055, 0.055, 0.12);
    const notchMat = THREE_THEME.materials.createSatinAluminum(0xf0f0f5, 0.2, 0.95);
    this.disposables.push(notchGeom, notchMat);

    const notchCount = 16;
    for (let i = 0; i < notchCount; i++) {
      const angle = (i / notchCount) * Math.PI * 2;
      const r = this.globeRadius * 1.38;
      const notch = new THREE.Mesh(notchGeom, notchMat);
      notch.position.set(Math.cos(angle) * r, 0, Math.sin(angle) * r);
      notch.rotation.y = -angle;
      this.orbitTorus1.add(notch);
    }

    // Telemetry Satellite Station on Ring 2
    const satGeom = new THREE.CylinderGeometry(0.08, 0.09, 0.11, 8);
    const satMat = THREE_THEME.materials.createSatinChampagne(
      THREE_THEME.colors.champagneGold,
      0.2,
      0.95
    );
    this.disposables.push(satGeom, satMat);

    const sat1 = new THREE.Mesh(satGeom, satMat);
    sat1.position.set(this.globeRadius * 1.6, 0, 0);
    sat1.rotation.z = Math.PI / 2;
    this.orbitTorus2.add(sat1);

    const sat2 = new THREE.Mesh(satGeom, satMat);
    sat2.position.set(-this.globeRadius * 1.6, 0, 0);
    sat2.rotation.z = Math.PI / 2;
    this.orbitTorus2.add(sat2);
  }

  private buildHubsAndVolumetricTubes(): void {
    const hubPositions = FINANCIAL_HUBS.map((h) => ({
      ...h,
      pos: latLonToVector3(h.lat, h.lon, this.globeRadius + 0.04),
    }));

    // 1. Solid Hub Pedestals (Cylinders with beveled top cap)
    const baseGeom = new THREE.CylinderGeometry(0.09, 0.11, 0.065, 16);
    const baseMat = THREE_THEME.materials.createBrushedTitanium(
      THREE_THEME.colors.charcoal,
      0.3,
      0.85
    );
    const capGeom = new THREE.CylinderGeometry(0.06, 0.06, 0.035, 16);
    const normalCapMat = THREE_THEME.materials.createSatinChampagne(
      THREE_THEME.colors.champagneGold,
      0.22,
      0.92
    );
    // Primary beacon cap for Vietnam nodes (HCMC & Hanoi)
    const primaryCapMat = THREE_THEME.materials.createSatinChampagne(
      0xdcb36a,
      0.18,
      0.96
    );
    this.disposables.push(baseGeom, baseMat, capGeom, normalCapMat, primaryCapMat);

    hubPositions.forEach((hub) => {
      const normal = hub.pos.clone().normalize();
      const baseMesh = new THREE.Mesh(baseGeom, baseMat);
      baseMesh.position.copy(hub.pos);
      baseMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);

      const capMatToUse = hub.isPrimary ? primaryCapMat : normalCapMat;
      const capMesh = new THREE.Mesh(capGeom, capMatToUse);
      capMesh.position.copy(hub.pos.clone().add(normal.clone().multiplyScalar(0.045)));
      capMesh.quaternion.copy(baseMesh.quaternion);

      if (hub.isPrimary) {
        capMesh.scale.set(1.2, 1.4, 1.2);
      }

      this.group.add(baseMesh);
      this.group.add(capMesh);
    });

    // 2. Volumetric 3D Tubes for Inter-Hub Conduits
    const arcPairs = [
      [0, 2], // HCM -> SG
      [1, 2], // HN -> SG
      [2, 3], // SG -> TYO
      [2, 4], // SG -> HK
      [3, 7], // TYO -> NYC
      [2, 5], // SG -> LON
      [5, 6], // LON -> Frankfurt
      [5, 7], // LON -> NYC
    ];

    const tubeMat = THREE_THEME.materials.createTubeMaterial(
      THREE_THEME.colors.gunmetal,
      0.35,
      0.82
    );
    this.disposables.push(tubeMat);

    const packetGeom = new THREE.SphereGeometry(0.048, 12, 12);
    const packetMat = THREE_THEME.materials.createSatinChampagne(
      THREE_THEME.colors.champagneGold,
      0.2,
      0.95
    );
    this.disposables.push(packetGeom, packetMat);

    arcPairs.forEach(([idxA, idxB]) => {
      const start = hubPositions[idxA].pos;
      const end = hubPositions[idxB].pos;

      const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
      const dist = start.distanceTo(end);
      const elevation = dist * 0.38 + this.globeRadius * 0.16;
      mid.normalize().multiplyScalar(this.globeRadius + elevation);

      const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
      const tubeGeom = new THREE.TubeGeometry(curve, 32, 0.020, 8, false);
      const tubeMesh = new THREE.Mesh(tubeGeom, tubeMat);
      this.group.add(tubeMesh);
      this.disposables.push(tubeGeom);

      // Solid metallic traveling packet
      const packet = new THREE.Mesh(packetGeom, packetMat);
      this.group.add(packet);
      this.arcPackets.push({
        mesh: packet,
        curve,
        progress: Math.random(),
        speed: 0.18 + Math.random() * 0.12,
      });
    });
  }

  private buildDataNebula(): void {
    // Micro-Particle Financial Data Nebula: 240 subtle market telemetry points
    const particleCount = 240;
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    const goldColor = new THREE.Color(THREE_THEME.colors.champagneGold);
    const silverColor = new THREE.Color(THREE_THEME.colors.platinum);

    for (let i = 0; i < particleCount; i++) {
      // Toroidal orbital distribution around the equator
      const angle = Math.random() * Math.PI * 2;
      const radius = this.globeRadius * 1.25 + Math.random() * (this.globeRadius * 0.45);
      const height = (Math.random() - 0.5) * 1.3;

      positions[i * 3] = Math.cos(angle) * radius;
      positions[i * 3 + 1] = height;
      positions[i * 3 + 2] = Math.sin(angle) * radius;

      // Subtle metallic color palette
      const c = Math.random() > 0.4 ? goldColor : silverColor;
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
    }

    const nebulaGeom = new THREE.BufferGeometry();
    nebulaGeom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    nebulaGeom.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    // Soft round particle texture
    const canvas = document.createElement("canvas");
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      const grad = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
      grad.addColorStop(0, "rgba(255, 255, 255, 0.95)");
      grad.addColorStop(0.5, "rgba(255, 255, 255, 0.5)");
      grad.addColorStop(1, "rgba(255, 255, 255, 0)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 32, 32);
    }
    const texture = new THREE.CanvasTexture(canvas);

    const nebulaMat = new THREE.PointsMaterial({
      size: 0.10,
      map: texture,
      vertexColors: true,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.particlePoints = new THREE.Points(nebulaGeom, nebulaMat);
    this.group.add(this.particlePoints);
    this.disposables.push(nebulaGeom, nebulaMat, texture);
  }

  private buildContactShadow(): void {
    const shadow = THREE_THEME.materials.createContactShadowMesh(4.4, 0.32);
    shadow.position.y = -2.65;
    this.group.add(shadow);
    this.disposables.push(shadow.geometry, shadow.material as THREE.Material);
  }

  update(deltaTime: number, elapsed: number, context: SceneContextState): void {
    if (context.reducedMotion) return;

    // Smooth studio mouse parallax with silky inertia damping
    this.targetRotY = context.mouseNormalized.x * 0.45;
    this.targetRotX = 0.16 + context.mouseNormalized.y * 0.28;
    this.currentRotY = THREE.MathUtils.lerp(this.currentRotY, this.targetRotY, 0.04);
    this.currentRotX = THREE.MathUtils.lerp(this.currentRotX, this.targetRotX, 0.04);

    // Stately core planetary rotation
    const baseRot = deltaTime * 0.052;
    this.group.rotation.y += baseRot;
    this.group.rotation.x = this.currentRotX;
    this.group.rotation.z = -this.currentRotY * 0.18;

    // Subtle breathing vertical float
    this.group.position.y = 0.05 + Math.sin(elapsed * 0.75) * 0.035;

    // Orbital Torus counter rotations
    if (this.orbitTorus1) this.orbitTorus1.rotation.z += deltaTime * 0.11;
    if (this.orbitTorus2) this.orbitTorus2.rotation.z -= deltaTime * 0.082;
    if (this.orbitTorus3) this.orbitTorus3.rotation.z += deltaTime * 0.055;

    // Data nebula gentle orbital drift
    if (this.particlePoints) {
      this.particlePoints.rotation.y += deltaTime * 0.025;
    }

    // Optical mantle subtle refraction breathing
    if (this.mantleMesh) {
      const breath = 1.0 + Math.sin(elapsed * 1.1) * 0.007;
      this.mantleMesh.scale.set(breath, breath, breath);
    }

    // Packet travelers progression along solid 3D conduits
    for (let i = 0; i < this.arcPackets.length; i++) {
      const pkt = this.arcPackets[i];
      pkt.progress = (pkt.progress + deltaTime * pkt.speed) % 1.0;
      const point = pkt.curve.getPoint(pkt.progress);
      pkt.mesh.position.copy(point);
    }
  }

  onResize(width: number, height: number): void {
    this.updateResponsiveLayout(width, height);
  }

  onPointerMove(normalizedX: number, normalizedY: number): void {
    this.targetRotY = normalizedX * 0.45;
    this.targetRotX = 0.16 + normalizedY * 0.28;
  }

  dispose(): void {
    this.disposables.forEach((d) => d.dispose());
    this.disposables = [];
    this.arcPackets = [];
    if (this.group.parent) {
      this.group.parent.remove(this.group);
    }
  }
}
