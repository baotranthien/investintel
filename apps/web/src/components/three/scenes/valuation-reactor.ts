/**
 * Concept 4: Valuation Reactor — Premium 3D Product Visualization
 *
 * Transformed from wireframe gyroscope into an engineered luxury horological reactor:
 * - Solid machined titanium Fair Value core nestled inside a champagne gold gimbal ring.
 * - 4 Solid, beveled Torus valuation method rings (DCF, P/E, P/B, RIM) with machined sliders.
 * - Frosted optical glass valuation shells (Bear, Base, Bull) using MeshPhysicalMaterial.
 * - Solid physical Margin of Safety vector gauge & emerald market price marker.
 * - 3-point studio lighting with ACES Filmic tonemapping & contact ground shadow.
 */

import * as THREE from "three";
import { THREE_THEME } from "../scene-theme";
import type { InvestIntelScene, SceneContextState } from "./types";

interface ValuationMethodRing {
  name: string;
  radius: number;
  tiltX: number;
  tiltZ: number;
  speed: number;
  color: number;
  angle: number;
  torus: THREE.Mesh;
  slider: THREE.Mesh;
}

export class ValuationReactorScene implements InvestIntelScene {
  id = "valuation-reactor";
  title = "Valuation Reactor";
  description = "Lõi định giá tổng hợp, các quỹ đạo mô hình (DCF, P/E, P/B, RIM) & biên an toàn (Premium 3D)";

  private group: THREE.Group = new THREE.Group();
  private disposables: { dispose: () => void }[] = [];

  // Anchor Core & Gimbal
  private coreMesh!: THREE.Mesh;
  private gimbalRing!: THREE.Mesh;

  // Solid Valuation Method Rings
  private rings: ValuationMethodRing[] = [];

  // Solid Frosted Range Shells
  private bearShell!: THREE.Mesh;
  private baseShell!: THREE.Mesh;
  private bullShell!: THREE.Mesh;

  // Margin of Safety Physical Gauge
  private marketPriceMarker!: THREE.Mesh;
  private gaugeRod!: THREE.Mesh;

  // Studio lighting
  private keyLight!: THREE.DirectionalLight;
  private fillLight!: THREE.DirectionalLight;
  private rimLight!: THREE.DirectionalLight;

  // Mouse inertia
  private targetRotX = 0.22;
  private targetRotY = 0.0;
  private currentRotX = 0.22;
  private currentRotY = 0.0;

  init(
    _container: HTMLElement,
    scene: THREE.Scene,
    camera: THREE.PerspectiveCamera,
    _renderer: THREE.WebGLRenderer
  ): void {
    this.group = new THREE.Group();
    scene.add(this.group);

    // Studio Perspective Camera
    camera.position.set(0, 1.6, 9.2);
    camera.lookAt(0, 0, 0);

    // 1. Studio Lighting Rig
    this.setupStudioLighting(scene);

    // 2. Central Machined Fair Value Core & Gimbal
    this.buildCoreAndGimbal();

    // 3. Frosted Optical Glass Range Shells (Bear / Base / Bull)
    this.buildFrostedRangeShells();

    // 4. Solid Engineered Method Rings (TorusGeometry) & Sliders
    this.buildSolidMethodRings();

    // 5. Solid Margin of Safety Gauge Vector
    this.buildMarginOfSafetyGauge();

    // 6. Studio Ground Contact Shadow
    this.buildContactShadow();
  }

  private setupStudioLighting(scene: THREE.Scene): void {
    // Key Light: Overhead front-right, sculpts ring bevels and core facets
    this.keyLight = new THREE.DirectionalLight(0xfffdf6, 1.8);
    this.keyLight.position.set(6, 11, 8);
    scene.add(this.keyLight);

    // Fill Light: Soft cool fill preserving shadow details
    this.fillLight = new THREE.DirectionalLight(0xdbe4f2, 0.65);
    this.fillLight.position.set(-7, -2, 6);
    scene.add(this.fillLight);

    // Rim Light: Kicker defining the circular silhouettes of all 4 rings
    this.rimLight = new THREE.DirectionalLight(0xffffff, 1.4);
    this.rimLight.position.set(0, 9, -9);
    scene.add(this.rimLight);

    // Ambient bounce
    const ambLight = new THREE.AmbientLight(0x22242a, 0.7);
    scene.add(ambLight);
  }

  private buildCoreAndGimbal(): void {
    // 1. Solid Machined Titanium Icosahedron Core
    const coreGeom = new THREE.IcosahedronGeometry(0.85, 1);
    const coreMat = THREE_THEME.materials.createBrushedTitanium(
      THREE_THEME.colors.obsidian,
      0.32,
      0.88
    );
    this.coreMesh = new THREE.Mesh(coreGeom, coreMat);
    this.group.add(this.coreMesh);
    this.disposables.push(coreGeom, coreMat);

    // 2. Interlocking Satin Champagne Gimbal Ring around Core
    const gimbalGeom = new THREE.TorusGeometry(1.15, 0.055, 16, 64);
    const gimbalMat = THREE_THEME.materials.createSatinChampagne(
      THREE_THEME.colors.champagneGold,
      0.22,
      0.9
    );
    this.gimbalRing = new THREE.Mesh(gimbalGeom, gimbalMat);
    this.gimbalRing.rotation.x = Math.PI / 3;
    this.gimbalRing.rotation.y = Math.PI / 6;
    this.group.add(this.gimbalRing);
    this.disposables.push(gimbalGeom, gimbalMat);
  }

  private buildFrostedRangeShells(): void {
    // Bear Shell (Inner: radius 1.7)
    const bearGeom = new THREE.SphereGeometry(1.7, 32, 32);
    const bearMat = THREE_THEME.materials.createFrostedGlass(0xd4d4dc, 0.78, 0.35, 0.25);
    this.bearShell = new THREE.Mesh(bearGeom, bearMat);
    this.group.add(this.bearShell);
    this.disposables.push(bearGeom, bearMat);

    // Base Shell (Mid: radius 2.7)
    const baseGeom = new THREE.SphereGeometry(2.7, 36, 36);
    const baseMat = THREE_THEME.materials.createFrostedGlass(0xe0e0ea, 0.72, 0.3, 0.35);
    this.baseShell = new THREE.Mesh(baseGeom, baseMat);
    this.group.add(this.baseShell);
    this.disposables.push(baseGeom, baseMat);

    // Bull Shell (Outer: radius 3.7)
    const bullGeom = new THREE.SphereGeometry(3.7, 40, 40);
    const bullMat = THREE_THEME.materials.createFrostedGlass(0xeeeef6, 0.82, 0.28, 0.18);
    this.bullShell = new THREE.Mesh(bullGeom, bullMat);
    this.group.add(this.bullShell);
    this.disposables.push(bullGeom, bullMat);
  }

  private buildSolidMethodRings(): void {
    const ringConfigs = [
      { name: "DCF", radius: 2.15, tube: 0.048, tiltX: 24, tiltZ: 14, speed: 0.32, color: THREE_THEME.colors.champagneGold },
      { name: "P/E Relative", radius: 2.55, tube: 0.042, tiltX: -36, tiltZ: 38, speed: 0.26, color: THREE_THEME.colors.gunmetal },
      { name: "P/B Multiple", radius: 3.05, tube: 0.038, tiltX: 48, tiltZ: -22, speed: -0.2, color: THREE_THEME.colors.aluminum },
      { name: "Residual Income", radius: 3.45, tube: 0.034, tiltX: -16, tiltZ: -52, speed: 0.16, color: THREE_THEME.colors.slate },
    ];

    const sliderGeom = new THREE.CylinderGeometry(0.12, 0.12, 0.14, 16);
    this.disposables.push(sliderGeom);

    ringConfigs.forEach((cfg) => {
      // Solid Torus Mesh for Ring
      const torusGeom = new THREE.TorusGeometry(cfg.radius, cfg.tube, 16, 96);
      const torusMat = cfg.name === "DCF"
        ? THREE_THEME.materials.createSatinChampagne(cfg.color, 0.24, 0.88)
        : cfg.name === "P/B Multiple"
        ? THREE_THEME.materials.createSatinAluminum(cfg.color, 0.26, 0.92)
        : THREE_THEME.materials.createBrushedTitanium(cfg.color, 0.35, 0.85);

      const torusMesh = new THREE.Mesh(torusGeom, torusMat);
      torusMesh.rotation.x = THREE.MathUtils.degToRad(cfg.tiltX);
      torusMesh.rotation.z = THREE.MathUtils.degToRad(cfg.tiltZ);
      this.group.add(torusMesh);
      this.disposables.push(torusGeom, torusMat);

      // Machined Solid Slider mounted on Ring
      const sliderMat = new THREE.MeshStandardMaterial({
        color: cfg.color,
        roughness: 0.25,
        metalness: 0.9,
      });
      const slider = new THREE.Mesh(sliderGeom, sliderMat);
      this.group.add(slider);
      this.disposables.push(sliderMat);

      this.rings.push({
        name: cfg.name,
        radius: cfg.radius,
        tiltX: THREE.MathUtils.degToRad(cfg.tiltX),
        tiltZ: THREE.MathUtils.degToRad(cfg.tiltZ),
        speed: cfg.speed,
        color: cfg.color,
        angle: Math.random() * Math.PI * 2,
        torus: torusMesh,
        slider,
      });
    });
  }

  private buildMarginOfSafetyGauge(): void {
    const marketDist = 2.25;

    // Solid Emerald Jewel Marker for Market Price
    const markerGeom = new THREE.OctahedronGeometry(0.24, 0);
    const markerMat = THREE_THEME.materials.createEmeraldAccent(
      THREE_THEME.colors.calmEmerald,
      0.25,
      0.82
    );
    this.marketPriceMarker = new THREE.Mesh(markerGeom, markerMat);
    this.marketPriceMarker.position.set(0, 0, marketDist);
    this.group.add(this.marketPriceMarker);
    this.disposables.push(markerGeom, markerMat);

    // Solid Volumetric Connecting Rod (Gauge Needle)
    const rodGeom = new THREE.CylinderGeometry(0.024, 0.024, marketDist, 12);
    // Align cylinder from origin to target along Z
    rodGeom.rotateX(Math.PI / 2);
    rodGeom.translate(0, 0, marketDist / 2);

    const rodMat = THREE_THEME.materials.createSatinAluminum(
      THREE_THEME.colors.aluminum,
      0.3,
      0.88
    );
    this.gaugeRod = new THREE.Mesh(rodGeom, rodMat);
    this.group.add(this.gaugeRod);
    this.disposables.push(rodGeom, rodMat);
  }

  private buildContactShadow(): void {
    const shadow = THREE_THEME.materials.createContactShadowMesh(7.5, 0.35);
    shadow.position.y = -3.6;
    this.group.add(shadow);
    this.disposables.push(shadow.geometry, shadow.material as THREE.Material);
  }

  update(deltaTime: number, elapsed: number, context: SceneContextState): void {
    if (context.reducedMotion) return;

    // Smooth studio mouse parallax
    this.targetRotY = context.mouseNormalized.x * 0.55;
    this.targetRotX = 0.22 + context.mouseNormalized.y * 0.32;
    this.currentRotY = THREE.MathUtils.lerp(this.currentRotY, this.targetRotY, 0.04);
    this.currentRotX = THREE.MathUtils.lerp(this.currentRotX, this.targetRotX, 0.04);

    this.group.rotation.y = this.currentRotY;
    this.group.rotation.x = this.currentRotX;

    // Core & Gimbal Precision Rotations
    if (this.coreMesh) {
      this.coreMesh.rotation.y += deltaTime * 0.22;
      this.coreMesh.rotation.x += deltaTime * 0.14;
    }
    if (this.gimbalRing) {
      this.gimbalRing.rotation.z -= deltaTime * 0.18;
      this.gimbalRing.rotation.y += deltaTime * 0.12;
      const corePulse = 1.0 + Math.sin(elapsed * 1.8) * 0.025;
      this.gimbalRing.scale.setScalar(corePulse);
    }

    // Frosted Range Shells Gentle Rotation
    if (this.baseShell) {
      this.baseShell.rotation.y += deltaTime * 0.04;
    }

    // Orbiting Machined Sliders on Torus Rings
    this.rings.forEach((ring) => {
      ring.angle += deltaTime * ring.speed;
      const x = Math.cos(ring.angle) * ring.radius;
      const z = Math.sin(ring.angle) * ring.radius;
      const localPos = new THREE.Vector3(x, 0, z);

      // Apply ring tilts
      localPos.applyAxisAngle(new THREE.Vector3(1, 0, 0), ring.tiltX);
      localPos.applyAxisAngle(new THREE.Vector3(0, 0, 1), ring.tiltZ);

      ring.slider.position.copy(localPos);
      ring.slider.rotation.y += deltaTime * 0.8;
    });

    // Market Price Emerald Marker subtle levitation
    if (this.marketPriceMarker) {
      this.marketPriceMarker.rotation.y += deltaTime * 0.65;
      this.marketPriceMarker.rotation.x += deltaTime * 0.35;
      const floatOffset = Math.sin(elapsed * 2.2) * 0.06;
      this.marketPriceMarker.position.y = floatOffset;
      if (this.gaugeRod) {
        this.gaugeRod.position.y = floatOffset * 0.5;
      }
    }
  }

  onResize(_width: number, _height: number): void {}

  onPointerMove(normalizedX: number, normalizedY: number): void {
    this.targetRotY = normalizedX * 0.55;
    this.targetRotX = 0.22 + normalizedY * 0.32;
  }

  dispose(): void {
    this.disposables.forEach((d) => d.dispose());
    this.disposables = [];
    this.rings = [];
    if (this.group.parent) {
      this.group.parent.remove(this.group);
    }
  }
}
