"use client";

import React, { useRef, useState, useEffect, type JSX } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { MeshDistortMaterial } from "@react-three/drei";
import * as THREE from "three";
import { useTheme } from "@/lib/theme";

export type QuantCoreStatus = "idle" | "checking" | "streaming" | "ready";

export interface QuantCoreOrb3DProps {
  status?: QuantCoreStatus;
  size?: number; // Size in pixels (default: 36)
  className?: string;
  style?: React.CSSProperties;
}

function OrbScene({
  status = "idle",
  effectiveTheme,
}: {
  status: QuantCoreStatus;
  effectiveTheme: string;
}): JSX.Element {
  const outerRef = useRef<THREE.Mesh>(null);
  const innerRef = useRef<THREE.Mesh>(null);

  const isDark = effectiveTheme === "dark";
  const isActive = status === "checking" || status === "streaming";

  // Financial status color tokens
  const emerald = isDark ? "#10b981" : "#059669";
  const cyan = isDark ? "#06b6d4" : "#0891b2";
  const amber = isDark ? "#f59e0b" : "#d97706";
  const indigo = isDark ? "#818cf8" : "#4f46e5";

  const coreColor = isActive ? amber : emerald;
  const wireColor = isActive ? indigo : cyan;

  useFrame((_, delta) => {
    // Battery & CPU saving: pause when tab is hidden
    if (typeof document !== "undefined" && document.hidden) return;

    const speed = isActive ? 2.6 : 0.7;
    if (outerRef.current) {
      outerRef.current.rotation.x += delta * 0.35 * speed;
      outerRef.current.rotation.y += delta * 0.55 * speed;
    }
    if (innerRef.current) {
      innerRef.current.rotation.y -= delta * 0.7 * speed;
      innerRef.current.rotation.z += delta * 0.25 * speed;
    }
  });

  return (
    <group>
      {/* Outer Wireframe Icosahedron */}
      <mesh ref={outerRef}>
        <icosahedronGeometry args={[1.25, 1]} />
        <meshBasicMaterial
          color={wireColor}
          wireframe
          transparent
          opacity={isDark ? 0.6 : 0.4}
        />
      </mesh>

      {/* Inner Distort Core Sphere */}
      <mesh ref={innerRef}>
        <sphereGeometry args={[0.72, 32, 32]} />
        <MeshDistortMaterial
          color={coreColor}
          emissive={coreColor}
          emissiveIntensity={isDark ? 0.4 : 0.2}
          distort={isActive ? 0.36 : 0.1}
          speed={isActive ? 2.5 : 1.0}
          roughness={0.25}
          metalness={0.15}
          transparent
          opacity={isDark ? 0.85 : 0.75}
        />
      </mesh>

      <ambientLight intensity={isDark ? 0.9 : 1.3} />
      <pointLight position={[2, 2, 2]} intensity={isActive ? 2.2 : 1.4} color={coreColor} />
    </group>
  );
}

function QuantCoreOrb3DInner({
  status = "idle",
  size = 36,
  className = "",
  style,
}: QuantCoreOrb3DProps): JSX.Element {
  const { effectiveTheme } = useTheme();
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const isActive = status === "checking" || status === "streaming";
  const glowColor = isActive ? "rgba(245, 158, 11, 0.25)" : "rgba(16, 185, 129, 0.25)";

  return (
    <div
      className={className}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        filter: `drop-shadow(0 0 ${size * 0.25}px ${glowColor})`,
        transition: "filter 0.3s ease",
        ...style,
      }}
      aria-label={`Trạng thái lõi tính toán: ${status}`}
      role="img"
    >
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 3.2], fov: 45 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
        style={{ width: "100%", height: "100%", pointerEvents: "none" }}
      >
        {!reducedMotion && <OrbScene status={status} effectiveTheme={effectiveTheme} />}
      </Canvas>
    </div>
  );
}

// Fallback for zero SSR blocking
function OrbFallback({ size = 36 }: { size?: number }): JSX.Element {
  return (
    <div
      style={{
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: "50%",
        background: "radial-gradient(circle, #10b981 0%, transparent 70%)",
        opacity: 0.6,
        display: "inline-block",
      }}
    />
  );
}

export function QuantCoreOrb3D(props: QuantCoreOrb3DProps): JSX.Element {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <OrbFallback size={props.size} />;
  }

  return <QuantCoreOrb3DInner {...props} />;
}

export default QuantCoreOrb3D;

