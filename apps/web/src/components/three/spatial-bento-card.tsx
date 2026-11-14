"use client";

import React, { useRef, useState, useSyncExternalStore, type JSX } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { useTheme } from "@/lib/theme";
import styles from "./spatial-bento-widget.module.css";

export interface SpatialBentoCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  intensity?: number; // Maximum tilt angle in degrees (default: 3)
  spotlightRadius?: number; // Radius in pixels for specular light (default: 350)
  disabled?: boolean;
}

function subscribeReducedMotion(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getReducedMotionSnapshot(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function getServerReducedMotionSnapshot(): boolean {
  return false;
}

export function SpatialBentoCard({
  children,
  className = "",
  intensity = 3,
  spotlightRadius = 350,
  disabled = false,
  style,
}: SpatialBentoCardProps): JSX.Element {
  const cardRef = useRef<HTMLDivElement>(null);
  const { effectiveTheme } = useTheme();
  const isReducedMotion = useSyncExternalStore(
    subscribeReducedMotion,
    getReducedMotionSnapshot,
    getServerReducedMotionSnapshot
  );
  const [isHovered, setIsHovered] = useState(false);

  // Motion values for normalized cursor coordinates [-0.5, 0.5]
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Pixel coordinates for radial gradient spotlight
  const spotlightX = useMotionValue(0);
  const spotlightY = useMotionValue(0);

  // Apple-grade physical spring configurations
  const springConfig = { stiffness: 280, damping: 28, mass: 0.5 };
  const smoothMouseX = useSpring(mouseX, springConfig);
  const smoothMouseY = useSpring(mouseY, springConfig);

  // Rotation: tilt up when mouse top (negative Y -> positive rotateX), tilt right when mouse right (positive X -> positive rotateY)
  const rotateX = useTransform(smoothMouseY, [-0.5, 0.5], [intensity, -intensity]);
  const rotateY = useTransform(smoothMouseX, [-0.5, 0.5], [-intensity, intensity]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled || isReducedMotion || !cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Update pixel coordinates for spotlight
    spotlightX.set(x);
    spotlightY.set(y);

    // Update normalized relative coords [-0.5, 0.5]
    mouseX.set(x / width - 0.5);
    mouseY.set(y / height - 0.5);
  };

  const handleMouseEnter = () => {
    if (disabled || isReducedMotion) return;
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    mouseX.set(0);
    mouseY.set(0);
  };

  const isDark = effectiveTheme === "dark";
  const spotlightColor = isDark
    ? "rgba(255, 255, 255, 0.08)"
    : "rgba(0, 0, 0, 0.035)";

  const spotlightBg = `radial-gradient(circle ${spotlightRadius}px at ${spotlightX.get()}px ${spotlightY.get()}px, ${spotlightColor}, transparent 70%)`;

  return (
    <motion.div
      ref={cardRef}
      className={`${styles.tiltRoot} ${className}`}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        perspective: 1000,
        rotateX: isReducedMotion || disabled ? 0 : rotateX,
        rotateY: isReducedMotion || disabled ? 0 : rotateY,
        ...style,
      }}
    >
      <div className={styles.tiltViewport}>
        {/* 2.5D Specular Spotlight Layer */}
        {!disabled && !isReducedMotion && (
          <div
            className={styles.spotlightOverlay}
            style={{
              background: isHovered ? spotlightBg : "transparent",
            }}
          />
        )}
        <div className={styles.tiltContent}>{children}</div>
      </div>
    </motion.div>
  );
}

export default SpatialBentoCard;
