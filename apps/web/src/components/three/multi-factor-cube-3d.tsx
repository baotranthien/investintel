"use client";

import React, { useRef, useState, useEffect, useMemo, useSyncExternalStore, type JSX } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { useTheme } from "@/lib/theme";
import { useLocale, type AppLocale } from "@/lib/i18n";

function NativeOrbitControls() {
  const { camera, gl } = useThree();
  const controlsRef = useRef<OrbitControls | null>(null);

  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement);
    controls.target.set(0, 0, 0);
    controls.enableZoom = false;
    controls.minDistance = 2.5;
    controls.maxDistance = 7;
    controls.enablePan = false;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.35;
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.rotateSpeed = 0.5;
    controls.update();
    controlsRef.current = controls;
    return () => {
      controls.dispose();
      controlsRef.current = null;
    };
  }, [camera, gl.domElement]);

  useFrame(() => {
    controlsRef.current?.update();
  });

  return null;
}

export interface StockFactorPoint {
  symbol: string;
  name?: string;
  pe: number; // Value axis X (-1 to 1 normalized)
  roe: number; // Quality axis Y (-1 to 1 normalized)
  rs: number; // Momentum axis Z (-1 to 1 normalized)
  score: number; // 0 to 100
  sector?: string | null;
}

export interface MultiFactorCube3DProps {
  data?: StockFactorPoint[];
  variant?: "compact" | "full";
  size?: number; // Size in px
  height?: number; // Custom height if non-square
  className?: string;
  style?: React.CSSProperties;
  onSelectStock?: (symbol: string) => void;
}

const DEFAULT_STOCKS: StockFactorPoint[] = [
  { symbol: "FPT", name: "FPT Corp", pe: 0.6, roe: 0.85, rs: 0.75, score: 88, sector: "Công nghệ" },
  { symbol: "MWG", name: "Thế Giới Di Động", pe: 0.4, roe: 0.65, rs: 0.7, score: 78, sector: "Bán lẻ" },
  { symbol: "VCB", name: "Vietcombank", pe: 0.5, roe: 0.8, rs: 0.6, score: 82, sector: "Ngân hàng" },
  { symbol: "TCB", name: "Techcombank", pe: -0.3, roe: 0.75, rs: 0.65, score: 79, sector: "Ngân hàng" },
  { symbol: "MBB", name: "MB Bank", pe: -0.4, roe: 0.82, rs: 0.55, score: 81, sector: "Ngân hàng" },
  { symbol: "HPG", name: "Hòa Phát", pe: -0.1, roe: 0.5, rs: 0.6, score: 74, sector: "Thép" },
  { symbol: "VNM", name: "Vinamilk", pe: -0.2, roe: 0.6, rs: 0.2, score: 68, sector: "Tiêu dùng" },
  { symbol: "REE", name: "Cơ Điện Lạnh", pe: 0.1, roe: 0.7, rs: 0.5, score: 76, sector: "Hạ tầng" },
  { symbol: "BSR", name: "Lọc Hóa Dầu Bình Sơn", pe: -0.6, roe: 0.55, rs: 0.45, score: 71, sector: "Năng lượng" },
  { symbol: "SSI", name: "Chứng khoán SSI", pe: 0.2, roe: 0.6, rs: 0.7, score: 73, sector: "Tài chính" },
  { symbol: "PNJ", name: "Vàng bạc Đá quý Phú Nhuận", pe: 0.3, roe: 0.78, rs: 0.6, score: 79, sector: "Bán lẻ" },
  { symbol: "DGC", name: "Hóa chất Đức Giang", pe: 0.2, roe: 0.88, rs: 0.65, score: 84, sector: "Hóa chất" },
  { symbol: "KDH", name: "Khang Điền", pe: 0.1, roe: 0.45, rs: 0.4, score: 65, sector: "Bất động sản" },
  { symbol: "VHM", name: "Vinhomes", pe: -0.7, roe: 0.65, rs: 0.3, score: 69, sector: "Bất động sản" },
  { symbol: "GMD", name: "Gemadept", pe: 0.3, roe: 0.72, rs: 0.65, score: 77, sector: "Cảng biển" },
  { symbol: "VRE", name: "Vincom Retail", pe: -0.5, roe: 0.58, rs: 0.35, score: 67, sector: "Bất động sản" },
  { symbol: "PLX", name: "Petrolimex", pe: 0.0, roe: 0.52, rs: 0.4, score: 66, sector: "Năng lượng" },
  { symbol: "STB", name: "Sacombank", pe: -0.2, roe: 0.7, rs: 0.6, score: 75, sector: "Ngân hàng" },
];

function translateSector(sector: string | null | undefined, locale: AppLocale): string {
  if (!sector) return locale === "en" ? "General" : "Chung";
  const map: Record<string, { vi: string; en: string }> = {
    "Công nghệ": { vi: "Công nghệ", en: "Technology" },
    "Bán lẻ": { vi: "Bán lẻ", en: "Retail" },
    "Ngân hàng": { vi: "Ngân hàng", en: "Banking" },
    "Thép": { vi: "Thép", en: "Steel" },
    "Tiêu dùng": { vi: "Tiêu dùng", en: "Consumer Goods" },
    "Hạ tầng": { vi: "Hạ tầng", en: "Infrastructure" },
    "Năng lượng": { vi: "Năng lượng", en: "Energy" },
    "Tài chính": { vi: "Tài chính", en: "Financial Services" },
    "Hóa chất": { vi: "Hóa chất", en: "Chemicals" },
    "Bất động sản": { vi: "Bất động sản", en: "Real Estate" },
    "Cảng biển": { vi: "Cảng biển", en: "Seaports & Logistics" },
  };
  return map[sector]?.[locale] || sector;
}

function AmbientDust({ isDark }: { isDark: boolean }) {
  const pointsRef = useRef<THREE.Points>(null);
  const dustGeo = useMemo(() => {
    const count = 42;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const fx = Math.sin(i * 12.9898 + 1.23) * 43758.5453;
      const fy = Math.sin(i * 78.233 + 4.56) * 24634.6345;
      const fz = Math.sin(i * 39.346 + 7.89) * 19432.1234;
      positions[i * 3] = (fx - Math.floor(fx) - 0.5) * 1.85;
      positions[i * 3 + 1] = (fy - Math.floor(fy) - 0.5) * 1.85;
      positions[i * 3 + 2] = (fz - Math.floor(fz) - 0.5) * 1.85;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geo;
  }, []);

  useFrame((_, delta) => {
    if (pointsRef.current) {
      pointsRef.current.rotation.y += delta * 0.035;
      pointsRef.current.rotation.x += delta * 0.015;
    }
  });

  return (
    <points ref={pointsRef} geometry={dustGeo}>
      <pointsMaterial
        size={0.03}
        color={isDark ? "#34d399" : "#059669"}
        transparent
        opacity={isDark ? 0.38 : 0.22}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

function StockNode({
  stock,
  isSelected,
  isCompact,
  isDark,
  onPointerOver,
  onPointerOut,
  onClick,
}: {
  stock: StockFactorPoint;
  isSelected: boolean;
  isCompact: boolean;
  isDark: boolean;
  onPointerOver: () => void;
  onPointerOut: () => void;
  onClick: () => void;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const scaleRef = useRef<number>(1.0);

  const pointColor =
    stock.score >= 80 ? "#10B981" : stock.score >= 70 ? "#38BDF8" : "#F59E0B";

  const posX = Math.max(-0.88, Math.min(0.88, stock.pe * 0.88));
  const posY = Math.max(-0.88, Math.min(0.88, stock.roe * 0.88));
  const posZ = Math.max(-0.88, Math.min(0.88, stock.rs * 0.88));

  const baseRadius = isCompact ? 0.052 : isSelected ? 0.096 : 0.066;

  const phase = useMemo(() => {
    return stock.symbol.charCodeAt(0) * 0.73 + (stock.symbol.charCodeAt(1) || 0) * 0.41;
  }, [stock.symbol]);

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    const floatY = posY + Math.sin(clock.elapsedTime * 1.5 + phase) * 0.022;
    groupRef.current.position.y = floatY;

    const targetScale = isSelected ? 1.35 : 1.0;
    scaleRef.current = THREE.MathUtils.lerp(scaleRef.current, targetScale, 0.14);
    groupRef.current.scale.setScalar(scaleRef.current);
  });

  const dropToFloor = useMemo(
    () => new Float32Array([posX, -1.0, posZ, posX, posY, posZ]),
    [posX, posY, posZ]
  );
  const projToBack = useMemo(
    () => new Float32Array([posX, posY, -1.0, posX, posY, posZ]),
    [posX, posY, posZ]
  );
  const projToSide = useMemo(
    () => new Float32Array([-1.0, posY, posZ, posX, posY, posZ]),
    [posX, posY, posZ]
  );

  return (
    <>
      {!isCompact && (
        <lineSegments>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[dropToFloor, 3]} />
          </bufferGeometry>
          <lineBasicMaterial
            color={isSelected ? pointColor : isDark ? "rgba(255,255,255,0.18)" : "rgba(0,0,0,0.12)"}
            transparent
            opacity={isSelected ? 0.85 : 0.22}
          />
        </lineSegments>
      )}

      {isSelected && !isCompact && (
        <>
          <lineSegments>
            <bufferGeometry>
              <bufferAttribute attach="attributes-position" args={[projToBack, 3]} />
            </bufferGeometry>
            <lineBasicMaterial color={pointColor} transparent opacity={0.65} />
          </lineSegments>
          <lineSegments>
            <bufferGeometry>
              <bufferAttribute attach="attributes-position" args={[projToSide, 3]} />
            </bufferGeometry>
            <lineBasicMaterial color={pointColor} transparent opacity={0.65} />
          </lineSegments>

          <mesh position={[posX, -0.99, posZ]} rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[0.025, 0.045, 16]} />
            <meshBasicMaterial color={pointColor} transparent opacity={0.75} side={THREE.DoubleSide} />
          </mesh>
          <mesh position={[posX, posY, -0.99]}>
            <ringGeometry args={[0.025, 0.045, 16]} />
            <meshBasicMaterial color={pointColor} transparent opacity={0.75} side={THREE.DoubleSide} />
          </mesh>
          <mesh position={[-0.99, posY, posZ]} rotation={[0, Math.PI / 2, 0]}>
            <ringGeometry args={[0.025, 0.045, 16]} />
            <meshBasicMaterial color={pointColor} transparent opacity={0.75} side={THREE.DoubleSide} />
          </mesh>
        </>
      )}

      <group ref={groupRef} position={[posX, posY, posZ]}>
        <mesh
          onPointerOver={(e) => {
            e.stopPropagation();
            onPointerOver();
          }}
          onPointerOut={(e) => {
            e.stopPropagation();
            onPointerOut();
          }}
          onClick={(e) => {
            e.stopPropagation();
            onClick();
          }}
        >
          <sphereGeometry args={[baseRadius, 32, 32]} />
          <meshPhysicalMaterial
            color={pointColor}
            emissive={pointColor}
            emissiveIntensity={isSelected ? (isDark ? 1.6 : 1.2) : isDark ? 0.45 : 0.28}
            roughness={0.12}
            metalness={0.22}
            clearcoat={1.0}
            clearcoatRoughness={0.06}
            transmission={0.35}
            thickness={0.5}
            ior={1.52}
            reflectivity={1.0}
            transparent
            opacity={0.96}
          />
        </mesh>

        <mesh scale={1.55}>
          <sphereGeometry args={[baseRadius, 16, 16]} />
          <meshBasicMaterial
            color={pointColor}
            transparent
            opacity={isSelected ? 0.38 : isDark ? 0.16 : 0.1}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            side={THREE.BackSide}
          />
        </mesh>
      </group>
    </>
  );
}

function CubeScene({
  stocks,
  variant,
  effectiveTheme,
  activeStock,
  setHoveredStock,
  setSelectedStock,
}: {
  stocks: StockFactorPoint[];
  variant: "compact" | "full";
  effectiveTheme: string;
  activeStock: StockFactorPoint | null;
  setHoveredStock: React.Dispatch<React.SetStateAction<StockFactorPoint | null>>;
  setSelectedStock: React.Dispatch<React.SetStateAction<StockFactorPoint | null>>;
}) {
  const isDark = effectiveTheme === "dark";
  const groupRef = useRef<THREE.Group>(null);
  const { invalidate } = useThree();

  const isCompact = variant === "compact";

  useFrame((_, delta) => {
    if (typeof document !== "undefined" && document.hidden) return;
    if (isCompact && groupRef.current) {
      groupRef.current.rotation.y += delta * 0.25;
      groupRef.current.rotation.x += delta * 0.12;
      invalidate();
    }
  });

  const wireColor = isDark ? "rgba(255,255,255,0.22)" : "rgba(0,0,0,0.18)";
  const boxEdges = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(2.0, 2.0, 2.0)), []);

  const xAxis = useMemo(() => new Float32Array([-1.0, 0, 0, 1.0, 0, 0]), []);
  const yAxis = useMemo(() => new Float32Array([0, -1.0, 0, 0, 1.0, 0]), []);
  const zAxis = useMemo(() => new Float32Array([0, 0, -1.0, 0, 0, 1.0]), []);

  return (
    <>
      <ambientLight intensity={isDark ? 0.95 : 1.3} />
      <directionalLight position={[4, 6, 5]} intensity={isDark ? 2.2 : 2.6} />
      <pointLight position={[-4, 3, -4]} intensity={1.4} color="#10B981" />
      <pointLight position={[3, -2, 4]} intensity={0.9} color="#38BDF8" />

      {!isCompact && <NativeOrbitControls />}

      <group ref={groupRef} scale={1.0}>
        <lineSegments geometry={boxEdges}>
          <lineBasicMaterial color={wireColor} transparent opacity={isDark ? 0.45 : 0.3} />
        </lineSegments>

        {!isCompact && <AmbientDust isDark={isDark} />}

        {!isCompact && (
          <gridHelper
            args={[
              2.0,
              4,
              isDark ? "rgba(255,255,255,0.14)" : "rgba(0,0,0,0.12)",
              isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)",
            ]}
            position={[0, -1.0, 0]}
          />
        )}

        {/* X Axis: Value P/E */}
        <lineSegments>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[xAxis, 3]} />
          </bufferGeometry>
          <lineBasicMaterial color="#3b82f6" transparent opacity={isDark ? 0.6 : 0.45} />
        </lineSegments>

        {/* Y Axis: Quality ROE */}
        <lineSegments>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[yAxis, 3]} />
          </bufferGeometry>
          <lineBasicMaterial color="#10b981" transparent opacity={isDark ? 0.6 : 0.45} />
        </lineSegments>

        {/* Z Axis: Momentum RS */}
        <lineSegments>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[zAxis, 3]} />
          </bufferGeometry>
          <lineBasicMaterial color="#f59e0b" transparent opacity={isDark ? 0.6 : 0.45} />
        </lineSegments>

        {stocks.map((stock) => (
          <StockNode
            key={stock.symbol}
            stock={stock}
            isSelected={activeStock?.symbol === stock.symbol}
            isCompact={isCompact}
            isDark={isDark}
            onPointerOver={() => {
              setHoveredStock(stock);
              invalidate();
            }}
            onPointerOut={() => {
              setHoveredStock(null);
              invalidate();
            }}
            onClick={() => {
              setSelectedStock((prev) => (prev?.symbol === stock.symbol ? null : stock));
              invalidate();
            }}
          />
        ))}
      </group>
    </>
  );
}

function MultiFactorCube3DInner({
  data = DEFAULT_STOCKS,
  variant = "full",
  size,
  height,
  className = "",
  style,
  onSelectStock,
}: MultiFactorCube3DProps): JSX.Element {
  const { effectiveTheme } = useTheme();
  const { locale, t } = useLocale();
  const [hoveredStock, setHoveredStock] = useState<StockFactorPoint | null>(null);
  const [selectedStock, setSelectedStock] = useState<StockFactorPoint | null>(null);
  const activeStock = selectedStock ?? hoveredStock;

  const isCompact = variant === "compact";
  const defaultDim = isCompact ? 160 : "100%";
  const targetWidth = size ?? defaultDim;
  const targetHeight = height ?? (isCompact ? 160 : 420);

  return (
    <div
      className={className}
      style={{
        width: typeof targetWidth === "number" ? `${targetWidth}px` : targetWidth,
        height: typeof targetHeight === "number" ? `${targetHeight}px` : targetHeight,
        position: "relative",
        display: isCompact ? "inline-flex" : "flex",
        alignItems: "center",
        justifyContent: "center",
        ...style,
      }}
      aria-label={t("Biểu đồ đa nhân tố không gian 3D", "3D Multi-Factor Space Chart")}
      role="img"
    >
      <Canvas
        frameloop="always"
        dpr={[1, 1.5]}
        camera={{ position: [3.4, 2.8, 3.9], fov: 36 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
        style={{ width: "100%", height: "100%" }}
        onPointerMissed={() => setSelectedStock(null)}
      >
        <CubeScene
          stocks={data}
          variant={variant}
          effectiveTheme={effectiveTheme}
          activeStock={activeStock}
          setHoveredStock={setHoveredStock}
          setSelectedStock={setSelectedStock}
        />
      </Canvas>

      {/* Axis Legend HUD Overlay */}
      {!isCompact && (
        <div
          style={{
            position: "absolute",
            bottom: 10,
            left: 12,
            pointerEvents: "none",
            display: "flex",
            gap: "14px",
            whiteSpace: "nowrap",
            fontSize: "11px",
            fontWeight: 650,
            color: "var(--ink-secondary)",
            backgroundColor: "var(--surface-elevated, rgba(255,255,255,0.92))",
            backdropFilter: "blur(12px)",
            padding: "6px 14px",
            borderRadius: "10px",
            border: "1px solid var(--line)",
            zIndex: 5,
            boxShadow: "0 2px 10px rgba(0,0,0,0.06)",
          }}
        >
          <span>
            <strong style={{ color: "#3b82f6" }}>X:</strong>{" "}
            {t("P/E (Trái: Đắt → Phải: Rẻ)", "P/E (Left: Expensive → Right: Value)")}
          </span>
          <span>
            <strong style={{ color: "#10b981" }}>Y:</strong>{" "}
            {t("ROE (Dưới: Thấp → Trên: Cao)", "ROE (Bottom: Low → Top: High Quality)")}
          </span>
          <span>
            <strong style={{ color: "#f59e0b" }}>Z:</strong>{" "}
            {t("RS (Gần: Yếu → Sâu: Khỏe)", "RS (Near: Low Momentum → Deep: Strong)")}
          </span>
        </div>
      )}

      {/* Active (Hovered or Selected) Stock Tooltip HUD Overlay */}
      {activeStock && !isCompact && (
        <div
          style={{
            position: "absolute",
            top: 12,
            right: 14,
            pointerEvents: "auto",
            backgroundColor: "var(--surface-elevated, #ffffff)",
            color: "var(--ink, #1d1d1f)",
            padding: "8px 14px",
            borderRadius: "10px",
            fontSize: "12px",
            boxShadow: "0 6px 20px rgba(0,0,0,0.15)",
            border: "1px solid var(--line)",
            backdropFilter: "blur(14px)",
            zIndex: 10,
            display: "flex",
            flexDirection: "column",
            gap: "3px",
            minWidth: "170px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong
              style={{
                fontSize: "14px",
                color:
                  activeStock.score >= 80
                    ? "#10b981"
                    : activeStock.score >= 70
                    ? "#3b82f6"
                    : "#f59e0b",
              }}
            >
              {activeStock.symbol}
            </strong>
            <span
              style={{
                fontSize: "11px",
                fontWeight: 700,
                padding: "2px 6px",
                borderRadius: "5px",
                background: "var(--surface-muted)",
              }}
            >
              {activeStock.score}/100
            </span>
          </div>
          {activeStock.name && (
            <div style={{ fontSize: "11px", color: "var(--ink-secondary)" }}>
              {activeStock.name} · {translateSector(activeStock.sector, locale)}
            </div>
          )}
          <div style={{ fontSize: "11px", color: "var(--ink-muted)", marginTop: "2px" }}>
            P/E: {activeStock.pe > 0 ? t("Hấp dẫn (Rẻ)", "Attractive (Value)") : t("Định giá cao", "Elevated")} · ROE:{" "}
            {activeStock.roe > 0 ? t("Chất lượng cao", "High Quality") : t("Trung bình", "Moderate")}
          </div>
          {onSelectStock && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSelectStock(activeStock.symbol);
              }}
              style={{
                marginTop: "6px",
                padding: "6px 10px",
                borderRadius: "7px",
                border: "1px solid color-mix(in srgb, var(--accent-apple, #0071e3) 35%, transparent)",
                background: "color-mix(in srgb, var(--accent-apple, #0071e3) 12%, transparent)",
                color: "var(--accent-apple, #0071e3)",
                fontSize: "11px",
                fontWeight: 650,
                cursor: "pointer",
                textAlign: "center",
                width: "100%",
              }}
            >
              {t("✦ Nhấp để mở AI Analyst →", "✦ Click to see AI Analyst →")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function CubeFallback({ size = 160, label }: { size?: number; label: string }): JSX.Element {
  return (
    <div
      style={{
        width: `${size}px`,
        height: `${size}px`,
        border: "1px dashed var(--line, #e5e5ea)",
        borderRadius: "12px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "11px",
        color: "var(--ink-secondary)",
      }}
    >
      {label}
    </div>
  );
}

export function MultiFactorCube3D(props: MultiFactorCube3DProps): JSX.Element {
  const { t } = useLocale();
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );

  if (!mounted) {
    const fallbackSize = props.variant === "full" ? (props.height ?? 420) : (props.size ?? 160);
    return <CubeFallback size={fallbackSize} label={t("Đang tải biểu đồ 3D...", "Loading 3D visualization...")} />;
  }

  return <MultiFactorCube3DInner {...props} />;
}

export default MultiFactorCube3D;
