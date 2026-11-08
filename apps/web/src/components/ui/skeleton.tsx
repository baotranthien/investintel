import React, { type JSX } from "react";
import styles from "./skeleton.module.css";

export function Skeleton({
  width = "100%",
  height = 14,
  radius = 6,
  className,
  style,
}: {
  width?: number | string;
  height?: number | string;
  radius?: number | string;
  className?: string;
  style?: React.CSSProperties;
}): JSX.Element {
  const computedStyle: React.CSSProperties = {
    width: typeof width === "number" ? `${width}px` : width,
    height: typeof height === "number" ? `${height}px` : height,
    borderRadius: typeof radius === "number" ? `${radius}px` : radius,
    ...style,
  };

  return (
    <span
      aria-hidden="true"
      className={`${styles.skeleton}${className ? ` ${className}` : ""}`}
      style={computedStyle}
    />
  );
}

export function SkeletonText({
  lines = 3,
  lastLineWidth = "60%",
  lineHeight = 14,
  gap = 8,
}: {
  lines?: number;
  lastLineWidth?: string;
  lineHeight?: number;
  gap?: number;
}): JSX.Element {
  return (
    <div
      role="status"
      aria-label="Đang tải"
      className={styles.textWrapper}
      style={{ gap: `${gap}px` }}
    >
      {Array.from({ length: lines }).map((_, index) => {
        const isLast = index === lines - 1;
        return (
          <Skeleton
            key={index}
            height={lineHeight}
            width={isLast ? lastLineWidth : "100%"}
          />
        );
      })}
    </div>
  );
}

export function SkeletonCard({
  height,
  className,
}: {
  height?: number;
  className?: string;
}): JSX.Element {
  const cardStyle: React.CSSProperties = height !== undefined ? { height: `${height}px` } : {};

  return (
    <div
      role="status"
      aria-label="Đang tải"
      className={`${styles.card}${className ? ` ${className}` : ""}`}
      style={cardStyle}
    >
      <Skeleton width="45%" height={18} radius={6} />
      <SkeletonText lines={2} lastLineWidth="80%" gap={8} />
    </div>
  );
}

export function SkeletonTableRows({
  rows = 8,
  columns,
}: {
  rows?: number;
  columns: number;
}): JSX.Element {
  return (
    <>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={rowIndex}>
          {Array.from({ length: columns }).map((_, colIndex) => (
            <td key={colIndex} className={styles.tableCell}>
              <Skeleton height={12} radius={4} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
