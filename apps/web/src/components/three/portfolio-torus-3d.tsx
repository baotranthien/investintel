"use client";

import React, { useRef, useState, useEffect, useMemo, useSyncExternalStore, type JSX } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { useTheme } from "@/lib/theme";
import { useLocale, type AppLocale } from "@/lib/i18n";

export interface TorusAllocationItem {
  id?: string;
  label: string;
  value: number; // Percentage 0 - 100
  color?: string;
  role?: string;
}

export interface PortfolioTorus3DProps {
  data?: TorusAllocationItem[];
  size?: number; // Size in px (default: 200)
  interactive?: boolean;
  activeSegment?: number | null;
  onHoverSegment?: (index: number | null) => void;
  className?: string;
  style?: React.CSSProperties;
}

const DEFAULT_ALLOCATION: TorusAllocationItem[] = [
  { id: "growth", label: "Tăng trưởng", value: 45, color: "#3b82f6", role: "CORE" },
  { id: "defense", label: "Phòng thủ & Cổ tức", value: 35, color: "#10b981", role: "CORE" },
  { id: "cash", label: "Dự trữ thanh khoản", value: 20, color: "#f59e0b", role: "LIQUIDITY" },
];

function translateAllocationLabel(item: TorusAllocationItem, locale: AppLocale): string {
  const isEn = locale === "en";
  if (item.id === "growth" || item.label === "Tăng trưởng") {
    return isEn ? "Growth" : "Tăng trưởng";
  }
  if (item.id === "defense" || item.label.includes("Phòng thủ") || item.label.includes("Cổ tức")) {
    return isEn ? "Defensive & Dividend" : "Phòng thủ & Cổ tức";
  }
  if (item.id === "cash" || item.label.includes("thanh khoản") || item.label.includes("Dự trữ")) {
    return isEn ? "Liquidity Reserve" : "Dự trữ thanh khoản";
  }
  return item.label;
}

function InvalidateOnChange({ triggerKey }: { triggerKey: string }) {
  const invalidate = useThree((state) => state.invalidate);
  useEffect(() => {
    invalidate();
  }, [invalidate, triggerKey]);
  return null;
}

function TorusSegment({
  startAngle,
  arcAngle,
  item,
  isHovered,
  onPointerOver,
  onPointerOut,
  effectiveTheme,
}: {
  startAngle: number;
  arcAngle: number;
  item: TorusAllocationItem;
  isHovered: boolean;
  onPointerOver: () => void;
  onPointerOut: () => void;
  effectiveTheme: string;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const isDark = effectiveTheme === "dark";

  const radius = 0.88;
  const tube = 0.22;
  const segmentColor = item.color || (isDark ? "#3b82f6" : "#2563eb");

  const midAngle = startAngle + arcAngle / 2;
  const dirX = Math.cos(midAngle);
  const dirY = Math.sin(midAngle);

  const scaleRef = useRef<number>(1.0);
  const currentDisplace = useRef<number>(0);

  useFrame(() => {
    if (!meshRef.current) return;
    const targetDisplace = isHovered ? 0.08 : 0;
    const targetScale = isHovered ? 1.05 : 1.0;
    currentDisplace.current = THREE.MathUtils.lerp(currentDisplace.current, targetDisplace, 0.14);
    scaleRef.current = THREE.MathUtils.lerp(scaleRef.current, targetScale, 0.14);

    meshRef.current.position.x = dirX * currentDisplace.current;
    meshRef.current.position.y = dirY * currentDisplace.current;
    meshRef.current.position.z = isHovered ? 0.14 : 0;
    meshRef.current.scale.setScalar(scaleRef.current);
  });

  return (
    <group rotation={[0, 0, startAngle]}>
      <mesh
        ref={meshRef}
        onPointerOver={(e) => {
          e.stopPropagation();
          onPointerOver();
        }}
        onPointerOut={(e) => {
          e.stopPropagation();
          onPointerOut();
        }}
      >
        <torusGeometry args={[radius, tube, 36, 72, arcAngle]} />
        <meshPhysicalMaterial
          color={segmentColor}
          emissive={segmentColor}
          emissiveIntensity={isHovered ? (isDark ? 0.75 : 0.45) : isDark ? 0.22 : 0.1}
          roughness={0.14}
          metalness={0.24}
          clearcoat={1.0}
          clearcoatRoughness={0.06}
          transmission={0.42}
          thickness={0.7}
          ior={1.48}
          transparent
          opacity={isHovered ? 1.0 : 0.94}
        />
      </mesh>
    </group>
  );
}

function PortfolioTorusScene({
  data,
  hoveredIdx,
  setHoveredIdx,
  effectiveTheme,
}: {
  data: TorusAllocationItem[];
  hoveredIdx: number | null;
  setHoveredIdx: (idx: number | null) => void;
  effectiveTheme: string;
}) {
  const isDark = effectiveTheme === "dark";
  const sceneRef = useRef<THREE.Group>(null);
  const { pointer } = useThree();

  useFrame(() => {
    if (!sceneRef.current) return;
    const targetRotX = -Math.PI / 8 - pointer.y * 0.18;
    const targetRotY = pointer.x * 0.25;
    sceneRef.current.rotation.x = THREE.MathUtils.lerp(sceneRef.current.rotation.x, targetRotX, 0.08);
    sceneRef.current.rotation.y = THREE.MathUtils.lerp(sceneRef.current.rotation.y, targetRotY, 0.08);
  });

  const segments = useMemo(() => {
    const total = data.reduce((sum, d) => sum + d.value, 0) || 100;
    const gapAngle = 0.04;
    const list: Array<{
      item: TorusAllocationItem;
      idx: number;
      startAngle: number;
      arcAngle: number;
    }> = [];

    let angleCursor = 0;
    for (let idx = 0; idx < data.length; idx++) {
      const item = data[idx];
      const proportion = item.value / total;
      const rawAngle = proportion * Math.PI * 2;
      const arcAngle = Math.max(0.1, rawAngle - gapAngle);
      const startAngle = angleCursor + gapAngle / 2;
      angleCursor += rawAngle;

      list.push({
        item,
        idx,
        startAngle,
        arcAngle,
      });
    }
    return list;
  }, [data]);

  const triggerKey = `${hoveredIdx ?? "none"}-${effectiveTheme}-${data.length}`;

  return (
    <group ref={sceneRef} position={[0, 0, 0]} rotation={[-Math.PI / 8, 0, 0]}>
      <InvalidateOnChange triggerKey={triggerKey} />

      <ambientLight intensity={isDark ? 0.95 : 1.3} />
      <directionalLight position={[3, 5, 5]} intensity={isDark ? 2.2 : 2.5} />
      <pointLight position={[-3, -2, 2]} intensity={1.2} color={isDark ? "#10B981" : "#38BDF8"} />

      <mesh rotation={[0, 0, 0]}>
        <torusGeometry args={[0.58, 0.014, 16, 64]} />
        <meshBasicMaterial
          color={isDark ? "#10B981" : "#059669"}
          transparent
          opacity={0.35}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {segments.map(({ item, idx, startAngle, arcAngle }) => (
        <TorusSegment
          key={item.id || idx}
          startAngle={startAngle}
          arcAngle={arcAngle}
          item={item}
          isHovered={hoveredIdx === idx}
          onPointerOver={() => setHoveredIdx(idx)}
          onPointerOut={() => setHoveredIdx(null)}
          effectiveTheme={effectiveTheme}
        />
      ))}
    </group>
  );
}

function PortfolioTorus3DInner({
  data = DEFAULT_ALLOCATION,
  size = 200,
  interactive = true,
  activeSegment = null,
  onHoverSegment,
  className = "",
  style,
}: PortfolioTorus3DProps): JSX.Element {
  const { effectiveTheme } = useTheme();
  const { locale, t } = useLocale();
  const [internalHovered, setInternalHovered] = useState<number | null>(null);

  const hoveredIdx = activeSegment !== null ? activeSegment : internalHovered;
  const hoveredItem = hoveredIdx !== null && hoveredIdx >= 0 && hoveredIdx < data.length ? data[hoveredIdx] : null;

  const handleHoverChange = (idx: number | null) => {
    if (!interactive) return;
    setInternalHovered(idx);
    if (onHoverSegment) {
      onHoverSegment(idx);
    }
  };

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
        ...style,
      }}
      aria-label={t("Biểu đồ tỷ trọng phân bổ danh mục 3D", "3D Portfolio Asset Allocation Torus")}
      role="img"
    >
      <Canvas
        frameloop="always"
        dpr={[1, 1.5]}
        camera={{ position: [0, 0.05, 5.2], fov: 36 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
        style={{ width: "100%", height: "100%" }}
      >
        <PortfolioTorusScene
          data={data}
          hoveredIdx={hoveredIdx}
          setHoveredIdx={handleHoverChange}
          effectiveTheme={effectiveTheme}
        />
      </Canvas>

      {/* Donut Center Info HUD */}
      <div
        style={{
          position: "absolute",
          pointerEvents: "none",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          padding: "4px 8px",
          borderRadius: "50%",
          zIndex: 10,
        }}
      >
        <div
          style={{
            fontSize: "18px",
            fontWeight: 800,
            color: hoveredItem ? hoveredItem.color || "var(--ink)" : "var(--ink)",
            lineHeight: 1.1,
            letterSpacing: "-0.02em",
          }}
        >
          {hoveredItem ? `${hoveredItem.value}%` : "100%"}
        </div>
        <div
          style={{
            fontSize: "11px",
            fontWeight: 650,
            color: "var(--ink-secondary)",
            maxWidth: "85px",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            marginTop: "3px",
            letterSpacing: "0.02em",
          }}
        >
          {hoveredItem ? translateAllocationLabel(hoveredItem, locale) : t("PHÂN BỔ", "ALLOCATION")}
        </div>
      </div>
    </div>
  );
}

function TorusFallback({ size = 200 }: { size?: number }): JSX.Element {
  return (
    <div
      style={{
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: "50%",
        border: "12px solid var(--line, #e5e5ea)",
        borderTopColor: "#3b82f6",
        borderRightColor: "#10b981",
        borderBottomColor: "#f59e0b",
        opacity: 0.6,
        display: "inline-block",
      }}
    />
  );
}

export function PortfolioTorus3D(props: PortfolioTorus3DProps): JSX.Element {
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );

  if (!mounted) {
    return <TorusFallback size={props.size} />;
  }

  return <PortfolioTorus3DInner {...props} />;
}

export default PortfolioTorus3D;
