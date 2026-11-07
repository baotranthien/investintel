/**
 * Concept 3: Neural Intelligence — Premium 3D Product Visualization
 *
 * Transformed from thin line diagram to a volumetric synaptic sculpture:
 * - Nodes have solid geometry (chamfered cylinders, faceted polyhedra).
 * - Central Synthesis Core: Multi-faceted geodesic focal sculpture.
 * - Synaptic connections are solid 3D volumetric tubes (TubeGeometry / CylinderGeometry).
 * - Volumetric traveling signal capsules with physical specular highlights.
 * - State-reactive animation synchronized directly with SSE streaming phases.
 * - 3-point studio lighting with ACES Filmic tonemapping.
 */

import * as THREE from "three";
import { THREE_THEME } from "../scene-theme";
import type { AIStreamingState, InvestIntelScene, SceneContextState } from "./types";

interface NeuralNode {
  index: number;
  layer: number;
  position: THREE.Vector3;
  baseScale: number;
  pulsePhase: number;
}

interface SynapticLink {
  from: number;
  to: number;
  start: THREE.Vector3;
  end: THREE.Vector3;
  curve: THREE.LineCurve3;
}

export class NeuralIntelligenceScene implements InvestIntelScene {
  id = "neural-intelligence";
  title = "Neural Intelligence";
  description = "Mạng nơ-ron đa tầng & trạng thái suy luận AI theo thời gian thực (Premium 3D)";

  private group: THREE.Group = new THREE.Group();
  private disposables: { dispose: () => void }[] = [];

  private nodes: NeuralNode[] = [];
  private links: SynapticLink[] = [];
  private nodeInstancedMesh!: THREE.InstancedMesh;
  private synthesisCoreMesh!: THREE.Mesh;
  private synthesisGimbalRing!: THREE.Mesh;
  private dummy = new THREE.Object3D();

  // Traveling Signal Packets (Solid Metallic Capsules)
  private packetMesh!: THREE.InstancedMesh;
  private packetStates: { linkIdx: number; progress: number; speed: number }[] = [];
  private totalPackets = 42;

  // Real-time AI state
  private currentAiState: AIStreamingState = "idle";
  private excitationLevel = 0.0;

  // Studio lighting
  private keyLight!: THREE.DirectionalLight;
  private fillLight!: THREE.DirectionalLight;
  private rimLight!: THREE.DirectionalLight;

  // Mouse inertia
  private targetRotX = 0.12;
  private targetRotY = 0.0;
  private currentRotX = 0.12;
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
    camera.position.set(0, 0.8, 9.8);
    camera.lookAt(0, 0, 0);

    // 1. Studio Lighting Rig
    this.setupStudioLighting(scene);

    // 2. Build Volumetric Synaptic Topology & Central Synthesis Focal Core
    this.buildVolumetricTopology();

    // 3. Build Volumetric 3D Tubes for Synapses
    this.buildVolumetricSynapses();

    // 4. Build Volumetric Signal Packets
    this.buildVolumetricPackets();

    // 5. Studio Ground Contact Shadow
    this.buildContactShadow();
  }

  private setupStudioLighting(scene: THREE.Scene): void {
    // Key Light: Overhead front-right, sculpts node facets and tube cylinders
    this.keyLight = new THREE.DirectionalLight(0xfffdf6, 1.8);
    this.keyLight.position.set(6, 9, 8);
    scene.add(this.keyLight);

    // Fill Light: Soft cool fill keeping shaded recesses readable
    this.fillLight = new THREE.DirectionalLight(0xdbe4f2, 0.65);
    this.fillLight.position.set(-7, -2, 6);
    scene.add(this.fillLight);

    // Rim Light: Kicker defining node edges and the synthesis core silhouette
    this.rimLight = new THREE.DirectionalLight(0xffffff, 1.4);
    this.rimLight.position.set(0, 8, -9);
    scene.add(this.rimLight);

    // Ambient bounce
    const ambLight = new THREE.AmbientLight(0x22242a, 0.7);
    scene.add(ambLight);
  }

  private buildVolumetricTopology(): void {
    const layerConfigs = [
      { layer: 0, x: -4.6, count: 5, spreadY: 4.0, spreadZ: 2.6, label: "Ingestion" },
      { layer: 1, x: -1.8, count: 7, spreadY: 4.6, spreadZ: 3.0, label: "Quant Engines" },
      { layer: 2, x: 1.4, count: 6, spreadY: 4.2, spreadZ: 2.8, label: "Audit & Validation" },
      { layer: 3, x: 4.2, count: 1, spreadY: 0.0, spreadZ: 0.0, label: "Synthesis Core" },
    ];

    let nodeIdx = 0;
    layerConfigs.forEach((cfg) => {
      for (let i = 0; i < cfg.count; i++) {
        const norm = cfg.count > 1 ? i / (cfg.count - 1) - 0.5 : 0;
        const py = norm * cfg.spreadY + Math.sin(i * 1.5) * 0.25;
        const pz = (Math.cos(i * 2.1) - 0.5) * cfg.spreadZ;
        const pos = new THREE.Vector3(cfg.x, py, pz);

        this.nodes.push({
          index: nodeIdx,
          layer: cfg.layer,
          position: pos,
          baseScale: cfg.layer === 3 ? 1.0 : 0.35,
          pulsePhase: Math.random() * Math.PI * 2,
        });
        nodeIdx++;
      }
    });

    // 1. Central Synthesis Focal Core (Sculpted Geodesic Polyhedron + Gimbal Ring)
    const focalNode = this.nodes[this.nodes.length - 1];
    const coreGeom = new THREE.IcosahedronGeometry(0.72, 1);
    const coreMat = THREE_THEME.materials.createSatinChampagne(
      THREE_THEME.colors.champagneGold,
      0.22,
      0.9
    );
    this.synthesisCoreMesh = new THREE.Mesh(coreGeom, coreMat);
    this.synthesisCoreMesh.position.copy(focalNode.position);
    this.group.add(this.synthesisCoreMesh);
    this.disposables.push(coreGeom, coreMat);

    // Beveled Gimbal Ring around Synthesis Core
    const gimbalGeom = new THREE.TorusGeometry(1.05, 0.045, 16, 64);
    const gimbalMat = THREE_THEME.materials.createSatinAluminum(
      THREE_THEME.colors.aluminum,
      0.25,
      0.92
    );
    this.synthesisGimbalRing = new THREE.Mesh(gimbalGeom, gimbalMat);
    this.synthesisGimbalRing.position.copy(focalNode.position);
    this.synthesisGimbalRing.rotation.x = Math.PI / 4;
    this.group.add(this.synthesisGimbalRing);
    this.disposables.push(gimbalGeom, gimbalMat);

    // 2. Solid Chamfered Cylinders for Intermediate Nodes (Layer 0, 1, 2)
    const intermediateCount = this.nodes.length - 1;
    const nodeGeom = new THREE.CylinderGeometry(0.7, 0.75, 0.5, 10);
    const nodeMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.3,
      metalness: 0.85,
    });
    this.nodeInstancedMesh = new THREE.InstancedMesh(nodeGeom, nodeMat, intermediateCount);
    this.nodeInstancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

    for (let i = 0; i < intermediateCount; i++) {
      const n = this.nodes[i];
      this.dummy.position.copy(n.position);
      this.dummy.scale.setScalar(n.baseScale);
      this.dummy.rotation.set(0.3, n.pulsePhase, 0.2);
      this.dummy.updateMatrix();
      this.nodeInstancedMesh.setMatrixAt(i, this.dummy.matrix);

      // Color scheme based on institutional layer
      const color = new THREE.Color(
        n.layer === 0
          ? THREE_THEME.colors.slate
          : n.layer === 1
          ? THREE_THEME.colors.gunmetal
          : THREE_THEME.colors.warmSilver
      );
      this.nodeInstancedMesh.setColorAt(i, color);
    }

    if (this.nodeInstancedMesh.instanceColor) {
      this.nodeInstancedMesh.instanceColor.needsUpdate = true;
    }
    this.nodeInstancedMesh.instanceMatrix.needsUpdate = true;
    this.group.add(this.nodeInstancedMesh);
    this.disposables.push(nodeGeom, nodeMat);
  }

  private buildVolumetricSynapses(): void {
    // Generate inter-layer synaptic pairs
    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = 0; j < this.nodes.length; j++) {
        const nA = this.nodes[i];
        const nB = this.nodes[j];
        if (nB.layer === nA.layer + 1) {
          const dist = nA.position.distanceTo(nB.position);
          if (dist < 4.4) {
            const curve = new THREE.LineCurve3(nA.position, nB.position);
            this.links.push({
              from: nA.index,
              to: nB.index,
              start: nA.position,
              end: nB.position,
              curve,
            });
          }
        }
      }
    }

    // Solid Volumetric 3D Tubes for Synapses
    const tubeMat = THREE_THEME.materials.createTubeMaterial(
      THREE_THEME.colors.gunmetal,
      0.38,
      0.82
    );
    this.disposables.push(tubeMat);

    this.links.forEach((l) => {
      const tubeGeom = new THREE.TubeGeometry(l.curve, 8, 0.032, 6, false);
      const tubeMesh = new THREE.Mesh(tubeGeom, tubeMat);
      this.group.add(tubeMesh);
      this.disposables.push(tubeGeom);
    });
  }

  private buildVolumetricPackets(): void {
    const packetGeom = new THREE.SphereGeometry(0.09, 12, 12);
    const packetMat = THREE_THEME.materials.createSatinChampagne(
      THREE_THEME.colors.champagneGold,
      0.2,
      0.95
    );

    this.packetMesh = new THREE.InstancedMesh(packetGeom, packetMat, this.totalPackets);
    this.packetMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

    for (let i = 0; i < this.totalPackets; i++) {
      const linkIdx = Math.floor(Math.random() * this.links.length);
      this.packetStates.push({
        linkIdx,
        progress: Math.random(),
        speed: 0.35 + Math.random() * 0.4,
      });

      this.dummy.position.set(0, 0, 0);
      this.dummy.scale.setScalar(1);
      this.dummy.updateMatrix();
      this.packetMesh.setMatrixAt(i, this.dummy.matrix);
    }
    this.packetMesh.instanceMatrix.needsUpdate = true;
    this.group.add(this.packetMesh);
    this.disposables.push(packetGeom, packetMat);
  }

  private buildContactShadow(): void {
    const shadow = THREE_THEME.materials.createContactShadowMesh(8.0, 0.32);
    shadow.position.y = -3.2;
    this.group.add(shadow);
    this.disposables.push(shadow.geometry, shadow.material as THREE.Material);
  }

  update(deltaTime: number, elapsed: number, context: SceneContextState): void {
    if (context.reducedMotion) return;

    if (context.aiState) {
      this.currentAiState = context.aiState;
    }

    // Target excitation level based on live AI stream state
    let targetExcitation = 0.15;
    if (this.currentAiState === "fetching_data") targetExcitation = 0.55;
    else if (this.currentAiState === "llm_reasoning") targetExcitation = 1.0;
    else if (this.currentAiState === "validating") targetExcitation = 0.75;
    else if (this.currentAiState === "completed") targetExcitation = 0.25;
    else if (this.currentAiState === "error") targetExcitation = 0.05;

    this.excitationLevel = THREE.MathUtils.lerp(this.excitationLevel, targetExcitation, 0.08);

    // Smooth studio mouse parallax
    this.targetRotY = context.mouseNormalized.x * 0.45;
    this.targetRotX = 0.12 + context.mouseNormalized.y * 0.28;
    this.currentRotY = THREE.MathUtils.lerp(this.currentRotY, this.targetRotY, 0.04);
    this.currentRotX = THREE.MathUtils.lerp(this.currentRotX, this.targetRotX, 0.04);

    this.group.rotation.y = this.currentRotY;
    this.group.rotation.x = this.currentRotX;

    // Synthesis Focal Core Stately Rotation & Pulse
    if (this.synthesisCoreMesh) {
      this.synthesisCoreMesh.rotation.y += deltaTime * 0.35 * (1 + this.excitationLevel);
      this.synthesisCoreMesh.rotation.x += deltaTime * 0.2;
      const coreBreath = 1.0 + Math.sin(elapsed * 2.2) * 0.04 * (1 + this.excitationLevel);
      this.synthesisCoreMesh.scale.set(coreBreath, coreBreath, coreBreath);
    }
    if (this.synthesisGimbalRing) {
      this.synthesisGimbalRing.rotation.z -= deltaTime * 0.25;
      this.synthesisGimbalRing.rotation.y += deltaTime * 0.15;
    }

    // Intermediate Node Micro-Breathing
    const intermediateCount = this.nodes.length - 1;
    const speedMult = 1.0 + this.excitationLevel * 2.2;
    for (let i = 0; i < intermediateCount; i++) {
      const n = this.nodes[i];
      const pulse = Math.sin(elapsed * 2.2 * speedMult + n.pulsePhase) * 0.05 * (1 + this.excitationLevel);
      const scale = Math.max(0.2, n.baseScale + pulse);

      this.dummy.position.copy(n.position);
      this.dummy.scale.setScalar(scale);
      this.dummy.rotation.set(0.3 + pulse * 2, n.pulsePhase + elapsed * 0.2, 0.2);
      this.dummy.updateMatrix();
      this.nodeInstancedMesh.setMatrixAt(i, this.dummy.matrix);
    }
    this.nodeInstancedMesh.instanceMatrix.needsUpdate = true;

    // Volumetric Synaptic Packets Flow along 3D tubes
    const packetSpeedMult = 0.8 + this.excitationLevel * 2.0;
    for (let i = 0; i < this.totalPackets; i++) {
      const p = this.packetStates[i];
      const link = this.links[p.linkIdx];

      p.progress += deltaTime * p.speed * packetSpeedMult;
      if (p.progress >= 1.0) {
        p.progress = 0.0;
        p.linkIdx = Math.floor(Math.random() * this.links.length);
      }

      const currentLink = this.links[p.linkIdx];
      const pos = currentLink.curve.getPoint(p.progress);

      this.dummy.position.copy(pos);
      const packetScale = 0.8 + this.excitationLevel * 0.5;
      this.dummy.scale.setScalar(packetScale);
      this.dummy.updateMatrix();
      this.packetMesh.setMatrixAt(i, this.dummy.matrix);
    }
    this.packetMesh.instanceMatrix.needsUpdate = true;
  }

  onResize(_width: number, _height: number): void {}

  onPointerMove(normalizedX: number, normalizedY: number): void {
    this.targetRotY = normalizedX * 0.45;
    this.targetRotX = 0.12 + normalizedY * 0.28;
  }

  dispose(): void {
    this.disposables.forEach((d) => d.dispose());
    this.disposables = [];
    this.nodes = [];
    this.links = [];
    this.packetStates = [];
    if (this.group.parent) {
      this.group.parent.remove(this.group);
    }
  }
}
