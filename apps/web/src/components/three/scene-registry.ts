/**
 * InvestIntel Three.js Scene Registry
 * Exclusively serves the ultra-premium AI Intelligence Globe on the Home page ("/").
 */

import type { InvestIntelScene } from "./scenes/types";
import { IntelligenceGlobeScene } from "./scenes/intelligence-globe";

export type SceneId = "intelligence-globe";

export function getSceneIdForPath(_pathname: string): SceneId {
  return "intelligence-globe";
}

export function createSceneInstance(_sceneId: SceneId): InvestIntelScene {
  return new IntelligenceGlobeScene();
}

