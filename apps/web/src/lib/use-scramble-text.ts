"use client";

import { useEffect, useState, useRef } from "react";

const CIPHER_GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789//[]_#%<>=+*";

/**
 * Hook to create a cyber-terminal scramble/decipher effect on text.
 * When `trigger` is true, text scrambles rapidly and resolves character by character.
 */
export function useScrambleText(
  targetText: string,
  trigger: boolean,
  duration = 360
): string {
  const [displayText, setDisplayText] = useState<string>(targetText);
  const animRef = useRef<number | null>(null);

  useEffect(() => {
    if (!trigger) {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      return;
    }

    const startTime = performance.now();
    const length = targetText.length;

    const frame = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);

      // Number of resolved characters from the left
      const resolvedCount = Math.floor(progress * length);

      let result = "";
      for (let i = 0; i < length; i++) {
        const char = targetText[i];
        if (char === " " || char === "\n") {
          result += char;
        } else if (i < resolvedCount || progress >= 1) {
          result += char;
        } else {
          // Random glyph
          const randIdx = Math.floor(Math.random() * CIPHER_GLYPHS.length);
          result += CIPHER_GLYPHS[randIdx];
        }
      }

      setDisplayText(result);

      if (progress < 1) {
        animRef.current = requestAnimationFrame(frame);
      } else {
        setDisplayText(targetText);
      }
    };

    animRef.current = requestAnimationFrame(frame);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [trigger, targetText, duration]);

  return trigger ? displayText : targetText;
}

export default useScrambleText;
