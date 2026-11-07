"use client";

import React, { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import * as THREE from "three";
import { createSceneInstance, getSceneIdForPath, type SceneId } from "./scene-registry";
import { performanceController, type PerformanceMetrics } from "./performance-controller";
import { aiSceneBridge, type AIBridgeState } from "./ai-scene-bridge";
import type { InvestIntelScene, SceneContextState } from "./scenes/types";
import styles from "./investintel-scene-host.module.css";

export default function InvestIntelSceneHost() {
  const pathname = usePathname();
  const isHomePage = pathname === "/";

  const containerRef = useRef<HTMLDivElement>(null);

  const [metrics, setMetrics] = useState<PerformanceMetrics>(() => performanceController.getMetrics());
  const [activeSceneName, setActiveSceneName] = useState<string>("AI Intelligence Globe");
  const [isAiStreaming, setIsAiStreaming] = useState<boolean>(false);

  // Three.js instances held in refs to avoid re-renders
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const currentSceneInstanceRef = useRef<InvestIntelScene | null>(null);
  const currentSceneIdRef = useRef<SceneId | null>(null);
  const animationFrameIdRef = useRef<number | null>(null);

  const mouseNormRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const aiStateRef = useRef<AIBridgeState>(aiSceneBridge.getState());
  const clockRef = useRef<THREE.Clock>(new THREE.Clock());

  // 1. Subscribe to performance metrics & AI bridge
  useEffect(() => {
    if (!isHomePage) return;
    const unsubPerf = performanceController.subscribe((m) => {
      setMetrics(m);
      if (rendererRef.current) {
        rendererRef.current.setPixelRatio(m.dpr);
      }
    });

    const unsubAi = aiSceneBridge.subscribe((ai) => {
      aiStateRef.current = ai;
      setIsAiStreaming(ai.isAiBusy);
      performanceController.setAiThrottling(ai.isAiBusy);
    });

    return () => {
      unsubPerf();
      unsubAi();
    };
  }, [isHomePage]);

  // 2. Initialize Single WebGL Renderer & Scene Loop
  useEffect(() => {
    if (!isHomePage) return;
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    const scene = new THREE.Scene();
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(performanceController.getDpr());
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    rendererRef.current = renderer;

    const canvas = renderer.domElement;
    canvas.setAttribute("data-testid", "investintel-3d-canvas");
    canvas.className = styles.canvas;
    container.appendChild(canvas);

    // WebGL Context Lost & Restored handlers
    const handleContextLost = (e: Event) => {
      e.preventDefault();
      if (animationFrameIdRef.current) {
        cancelAnimationFrame(animationFrameIdRef.current);
        animationFrameIdRef.current = null;
      }
    };

    const handleContextRestored = () => {
      if (currentSceneIdRef.current) {
        switchScene(currentSceneIdRef.current);
      }
      startLoop();
    };

    canvas.addEventListener("webglcontextlost", handleContextLost, false);
    canvas.addEventListener("webglcontextrestored", handleContextRestored, false);

    // Mouse movement tracker (relative to the 3D stage container)
    const handleMouseMove = (e: MouseEvent) => {
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const ny = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      const clampedX = Math.max(-1.5, Math.min(1.5, nx));
      const clampedY = Math.max(-1.5, Math.min(1.5, ny));
      mouseNormRef.current = { x: clampedX, y: clampedY };
      if (currentSceneInstanceRef.current?.onPointerMove) {
        currentSceneInstanceRef.current.onPointerMove(clampedX, clampedY);
      }
    };
    window.addEventListener("mousemove", handleMouseMove, { passive: true });

    // Resize handler
    const handleResize = () => {
      if (!container || !rendererRef.current || !cameraRef.current) return;
      const w = container.clientWidth || window.innerWidth;
      const h = container.clientHeight || window.innerHeight;
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(w, h);
      rendererRef.current.setPixelRatio(performanceController.getDpr());
      currentSceneInstanceRef.current?.onResize(w, h);
    };
    window.addEventListener("resize", handleResize, { passive: true });

    // Switch scene helper
    function switchScene(sceneId: SceneId) {
      if (currentSceneInstanceRef.current) {
        currentSceneInstanceRef.current.dispose();
        // Remove children from scene
        while (scene.children.length > 0) {
          scene.remove(scene.children[0]);
        }
      }

      const instance = createSceneInstance(sceneId);
      currentSceneInstanceRef.current = instance;
      currentSceneIdRef.current = sceneId;
      setActiveSceneName(instance.title);

      if (container && rendererRef.current && cameraRef.current) {
        instance.init(container, scene, cameraRef.current, rendererRef.current);
      }
    }

    // Animation Loop with FPS Limiter & AI Throttling
    function startLoop() {
      const render = (now: number) => {
        animationFrameIdRef.current = requestAnimationFrame(render);

        if (!performanceController.shouldRender(now)) {
          return;
        }

        const delta = clockRef.current.getDelta();
        const elapsed = clockRef.current.getElapsedTime();

        const contextState: SceneContextState = {
          activeRoute: pathname,
          symbol: aiStateRef.current.symbol,
          aiState: aiStateRef.current.aiState,
          isAiBusy: aiStateRef.current.isAiBusy,
          mouseNormalized: mouseNormRef.current,
          qualityTier: metrics.effectiveTier,
          reducedMotion: metrics.effectiveTier === "OFF",
        };

        if (currentSceneInstanceRef.current) {
          currentSceneInstanceRef.current.update(delta, elapsed, contextState);
        }

        if (rendererRef.current && sceneRef.current && cameraRef.current) {
          rendererRef.current.render(sceneRef.current, cameraRef.current);
        }
      };

      animationFrameIdRef.current = requestAnimationFrame(render);
    }

    // Initial scene
    const initialSceneId = getSceneIdForPath(pathname);
    switchScene(initialSceneId);
    startLoop();

    return () => {
      if (animationFrameIdRef.current) {
        cancelAnimationFrame(animationFrameIdRef.current);
      }
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("resize", handleResize);
      canvas.removeEventListener("webglcontextlost", handleContextLost);
      canvas.removeEventListener("webglcontextrestored", handleContextRestored);

      if (currentSceneInstanceRef.current) {
        currentSceneInstanceRef.current.dispose();
      }

      renderer.dispose();
      if (canvas.parentElement) {
        canvas.parentElement.removeChild(canvas);
      }
    };
  }, []);

  // 3. React to Route Changes: Transition Scene without recreating WebGL context
  useEffect(() => {
    const nextSceneId = getSceneIdForPath(pathname);
    if (nextSceneId !== currentSceneIdRef.current && sceneRef.current) {
      if (currentSceneInstanceRef.current) {
        currentSceneInstanceRef.current.dispose();
        while (sceneRef.current.children.length > 0) {
          sceneRef.current.remove(sceneRef.current.children[0]);
        }
      }

      const instance = createSceneInstance(nextSceneId);
      currentSceneInstanceRef.current = instance;
      currentSceneIdRef.current = nextSceneId;
      setActiveSceneName(instance.title);

      if (containerRef.current && rendererRef.current && cameraRef.current) {
        instance.init(
          containerRef.current,
          sceneRef.current,
          cameraRef.current,
          rendererRef.current
        );
      }
    }
  }, [pathname]);

  if (!isHomePage || metrics.effectiveTier === "OFF") {
    return null;
  }

  return (
    <div className={styles.hostContainer} ref={containerRef} aria-hidden="true">
      {/* Subtle Institutional 3D Telemetry Indicator in Lower Right */}
      <div className={styles.telemetryTag}>
        <span className={styles.pulseDot} data-streaming={isAiStreaming} />
        <span className={styles.sceneTitle}>{activeSceneName}</span>
        <span className={styles.separator}>·</span>
        <span className={styles.fps}>{metrics.fps} FPS</span>
        {isAiStreaming && <span className={styles.aiThrottlePill}>AI THROTTLE (15 FPS)</span>}
      </div>
    </div>
  );
}

