"use client";

import React, { useRef, useSyncExternalStore, type JSX } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useTheme } from "@/lib/theme";
import { useLocale, type AppLocale } from "@/lib/i18n";

export type QuantCoreStatus = "idle" | "checking" | "streaming" | "ready";

export interface QuantCoreOrb3DProps {
  status?: QuantCoreStatus;
  size?: number; // Size in pixels (default: 36)
  className?: string;
  style?: React.CSSProperties;
}

function getStatusLabel(status: QuantCoreStatus, locale: AppLocale): string {
  const isEn = locale === "en";
  switch (status) {
    case "idle":
      return isEn ? "Standby" : "Sẵn sàng";
    case "checking":
      return isEn ? "Auditing" : "Đang kiểm tra";
    case "streaming":
      return isEn ? "Streaming" : "Đang xử lý luồng";
    case "ready":
      return isEn ? "Ready" : "Hoàn tất";
    default:
      return status;
  }
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

  useFrame((state, delta) => {
    if (typeof document !== "undefined" && document.hidden) return;

    const speed = isActive ? 2.6 : 0.7;
    if (outerRef.current) {
      outerRef.current.rotation.x += delta * 0.35 * speed;
      outerRef.current.rotation.y += delta * 0.55 * speed;
    }
    if (innerRef.current) {
      innerRef.current.rotation.y -= delta * 0.7 * speed;
      innerRef.current.rotation.z += delta * 0.25 * speed;
      const t = state.clock.getElapsedTime();
      const pulse = 1 + Math.sin(t * (isActive ? 5.2 : 2.1)) * (isActive ? 0.11 : 0.045);
      innerRef.current.scale.set(pulse, pulse * 0.96, pulse);
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

      {/* Inner Luminous Core Sphere */}
      <mesh ref={innerRef}>
        <icosahedronGeometry args={[0.72, 2]} />
        <meshStandardMaterial
          color={coreColor}
          emissive={coreColor}
          emissiveIntensity={isActive ? (isDark ? 0.72 : 0.48) : (isDark ? 0.4 : 0.2)}
          roughness={0.25}
          metalness={0.18}
          transparent
          opacity={isDark ? 0.88 : 0.78}
        />
      </mesh>

      <ambientLight intensity={isDark ? 0.9 : 1.3} />
      <pointLight position={[2, 2, 2]} intensity={isActive ? 2.2 : 1.4} color={coreColor} />
    </group>
  );
}

function subscribeReducedMotion(callback: () => void) {
  if (typeof window === "undefined") return () => {};
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getReducedMotionSnapshot() {
  return typeof window !== "undefined"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

function QuantCoreOrb3DInner({
  status = "idle",
  size = 36,
  className = "",
  style,
}: QuantCoreOrb3DProps): JSX.Element {
  const { effectiveTheme } = useTheme();
  const { locale, t } = useLocale();
  const reducedMotion = useSyncExternalStore(
    subscribeReducedMotion,
    getReducedMotionSnapshot,
    () => false
  );

  const isActive = status === "checking" || status === "streaming";
  const glowColor = isActive ? "rgba(245, 158, 11, 0.25)" : "rgba(16, 185, 129, 0.25)";
  const label = getStatusLabel(status, locale);

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
      aria-label={t(`Trạng thái lõi tính toán: ${label}`, `Quant core engine status: ${label}`)}
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
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );

  if (!mounted) {
    return <OrbFallback size={props.size} />;
  }

  return <QuantCoreOrb3DInner {...props} />;
}

export default QuantCoreOrb3D;
