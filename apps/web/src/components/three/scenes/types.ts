import * as THREE from "three";

export type AIStreamingState =
  | "idle"
  | "fetching_data"
  | "llm_reasoning"
  | "validating"
  | "completed"
  | "error";

export interface SceneContextState {
  activeRoute: string;
  symbol?: string;
  aiState?: AIStreamingState;
  isAiBusy?: boolean;
  mouseNormalized: { x: number; y: number };
  qualityTier: "HIGH" | "BALANCED" | "LOW" | "OFF";
  reducedMotion: boolean;
}

export interface InvestIntelScene {
  id: string;
  title: string;
  description: string;
  init(
    container: HTMLElement,
    scene: THREE.Scene,
    camera: THREE.PerspectiveCamera,
    renderer: THREE.WebGLRenderer
  ): void;
  update(deltaTime: number, elapsed: number, context: SceneContextState): void;
  onResize(width: number, height: number): void;
  onPointerMove?(normalizedX: number, normalizedY: number): void;
  dispose(): void;
}

