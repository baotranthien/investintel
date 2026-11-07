"use client";

import type { AIStreamingState } from "./scenes/types";

type Listener = (state: AIBridgeState) => void;

export interface AIBridgeState {
  aiState: AIStreamingState;
  isAiBusy: boolean;
  symbol: string;
}

class AISceneBridge {
  private state: AIBridgeState = {
    aiState: "idle",
    isAiBusy: false,
    symbol: "FPT",
  };

  private listeners: Set<Listener> = new Set();

  getState(): AIBridgeState {
    return { ...this.state };
  }

  setAIState(aiState: AIStreamingState, isAiBusy = false) {
    this.state = {
      ...this.state,
      aiState,
      isAiBusy,
    };
    this.notify();
  }

  setSymbol(symbol: string) {
    this.state = {
      ...this.state,
      symbol: symbol.toUpperCase(),
    };
    this.notify();
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener(this.state);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify() {
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }
}

export const aiSceneBridge = new AISceneBridge();

