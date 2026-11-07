"use client";

export type QualityTier = "AUTO" | "HIGH" | "BALANCED" | "LOW" | "OFF";

export interface PerformanceMetrics {
  fps: number;
  qualityTier: QualityTier;
  effectiveTier: "HIGH" | "BALANCED" | "LOW" | "OFF";
  isAiThrottled: boolean;
  isVisible: boolean;
  dpr: number;
  frameBudgetMs: number;
}

type PerformanceListener = (metrics: PerformanceMetrics) => void;

class PerformanceController {
  private qualityTier: QualityTier = "BALANCED";
  private effectiveTier: "HIGH" | "BALANCED" | "LOW" | "OFF" = "BALANCED";
  private isAiThrottled = false;
  private isVisible = true;
  private reducedMotion = false;
  private listeners: Set<PerformanceListener> = new Set();

  private lastFrameTime = 0;
  private frameCount = 0;
  private lastFpsUpdate = 0;
  private currentFps = 30;

  constructor() {
    if (typeof window !== "undefined") {
      this.initFromStorage();
      this.initListeners();
    }
  }

  private initFromStorage() {
    try {
      const saved = localStorage.getItem("investintel_three_quality") as QualityTier;
      if (saved && ["AUTO", "HIGH", "BALANCED", "LOW", "OFF"].includes(saved)) {
        this.qualityTier = saved;
      }
    } catch {
      this.qualityTier = "BALANCED";
    }

    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    this.reducedMotion = mq.matches;
    this.resolveEffectiveTier();
  }

  private initListeners() {
    document.addEventListener("visibilitychange", () => {
      this.isVisible = !document.hidden;
      this.notify();
    });

    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    mq.addEventListener("change", (e) => {
      this.reducedMotion = e.matches;
      this.resolveEffectiveTier();
    });
  }

  private resolveEffectiveTier() {
    if (this.qualityTier === "OFF" || (this.qualityTier === "AUTO" && this.reducedMotion)) {
      this.effectiveTier = "OFF";
    } else if (this.qualityTier === "HIGH") {
      this.effectiveTier = "HIGH";
    } else if (this.qualityTier === "LOW") {
      this.effectiveTier = "LOW";
    } else {
      // Default & Balanced
      this.effectiveTier = "BALANCED";
    }
    this.notify();
  }

  setQuality(tier: QualityTier) {
    this.qualityTier = tier;
    try {
      localStorage.setItem("investintel_three_quality", tier);
    } catch {
      // ignore localstorage failure
    }
    this.resolveEffectiveTier();
  }

  setAiThrottling(isBusy: boolean) {
    if (this.isAiThrottled !== isBusy) {
      this.isAiThrottled = isBusy;
      this.notify();
    }
  }

  getTargetFps(): number {
    if (this.effectiveTier === "OFF" || !this.isVisible) return 0;
    if (this.isAiThrottled) return 15; // Strict 15 FPS throttle during local LLM generation
    if (this.effectiveTier === "HIGH") return 60;
    if (this.effectiveTier === "LOW") return 15;
    return 30; // Default Balanced
  }

  getDpr(): number {
    if (typeof window === "undefined") return 1.0;
    const deviceDpr = window.devicePixelRatio || 1;
    if (this.effectiveTier === "HIGH") return Math.min(deviceDpr, 1.25);
    return 1.0; // Balanced and Low clamp strictly at 1.0
  }

  getMetrics(): PerformanceMetrics {
    const targetFps = this.getTargetFps();
    return {
      fps: this.currentFps,
      qualityTier: this.qualityTier,
      effectiveTier: this.effectiveTier,
      isAiThrottled: this.isAiThrottled,
      isVisible: this.isVisible,
      dpr: this.getDpr(),
      frameBudgetMs: targetFps > 0 ? 1000 / targetFps : 0,
    };
  }

  /**
   * Called on every animation loop tick.
   * Returns true if enough delta time has passed to render this frame according to target FPS.
   */
  shouldRender(now: number): boolean {
    if (!this.isVisible || this.effectiveTier === "OFF") return false;

    const targetFps = this.getTargetFps();
    if (targetFps <= 0) return false;

    const minInterval = 1000 / targetFps;
    const elapsed = now - this.lastFrameTime;

    if (elapsed < minInterval - 1) {
      return false;
    }

    this.lastFrameTime = now - (elapsed % minInterval);

    // Track FPS
    this.frameCount++;
    if (now - this.lastFpsUpdate >= 1000) {
      this.currentFps = Math.round((this.frameCount * 1000) / (now - this.lastFpsUpdate));
      this.frameCount = 0;
      this.lastFpsUpdate = now;
      this.notify();
    }

    return true;
  }

  subscribe(listener: PerformanceListener): () => void {
    this.listeners.add(listener);
    listener(this.getMetrics());
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify() {
    const metrics = this.getMetrics();
    for (const listener of this.listeners) {
      listener(metrics);
    }
  }
}

export const performanceController = new PerformanceController();

