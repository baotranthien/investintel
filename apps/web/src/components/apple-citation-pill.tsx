"use client";

import React, { useState, useRef, useEffect, useId } from "react";
import type { AICitation } from "@/lib/api";
import styles from "./apple-citation-pill.module.css";

const ACTIVE_CITATION_EVENT = "investintel:active-citation-popover";

interface CitationPillProps {
  id: string;
  citation?: AICitation;
}

export default function AppleCitationPill({ id, citation }: CitationPillProps) {
  const [isOpen, setIsOpen] = useState(false);
  const instanceId = useId();
  const containerRef = useRef<HTMLSpanElement>(null);
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Mở popover và thông báo để đóng tất cả các popover khác (Đảm bảo DUY NHẤT 1 popover mở)
  const openPopover = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent(ACTIVE_CITATION_EVENT, { detail: { activeId: instanceId } })
      );
    }
    setIsOpen(true);
  };

  const closePopover = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    setIsOpen(false);
  };

  const handleMouseEnter = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    // Delay 220ms để tránh bão popover khi lướt chuột qua chuỗi pills
    hoverTimeoutRef.current = setTimeout(openPopover, 220);
  };

  const handleMouseLeave = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    hoverTimeoutRef.current = setTimeout(closePopover, 120);
  };

  // Lắng nghe sự kiện toàn cục: Nếu có popover khác mở thì đóng popover này ngay
  useEffect(() => {
    function handleActiveChange(e: Event) {
      const customEvent = e as CustomEvent<{ activeId: string }>;
      if (customEvent.detail?.activeId !== instanceId) {
        setIsOpen(false);
      }
    }

    window.addEventListener(ACTIVE_CITATION_EVENT, handleActiveChange);
    return () => {
      window.removeEventListener(ACTIVE_CITATION_EVENT, handleActiveChange);
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    };
  }, [instanceId]);

  // Click outside và Escape để đóng
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        closePopover();
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closePopover();
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
        document.removeEventListener("keydown", handleKeyDown);
      };
    }
  }, [isOpen]);

  const cleanId = id.toUpperCase().replace(/[\[\]]/g, "").trim();

  const handleToggleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isOpen) {
      closePopover();
    } else {
      openPopover();
    }
  };

  return (
    <span
      className={styles.container}
      ref={containerRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        type="button"
        className={`${styles.pill} ${isOpen ? styles.pillActive : ""}`}
        onClick={handleToggleClick}
        aria-expanded={isOpen}
        title="Xem nguồn dữ liệu kiểm chứng"
      >
        <span className={styles.pillIcon} aria-hidden="true">§</span>
        <span className={`${styles.pillText} tabular-nums`}>{cleanId}</span>
      </button>

      {isOpen && citation && (
        <div
          className={styles.popover}
          role="tooltip"
          onMouseEnter={() => {
            if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
          }}
          onMouseLeave={handleMouseLeave}
        >
          <div className={styles.popoverHeader}>
            <div className={styles.titleGroup}>
              <span className={`${styles.citationBadge} tabular-nums`}>{citation.id}</span>
              <strong className={styles.moduleName}>{citation.responsible_module || "Data Tool"}</strong>
            </div>
            <span
              className={`${styles.freshnessTag} ${
                citation.freshness === "AVAILABLE"
                  ? styles.freshnessAvailable
                  : styles.freshnessWarning
              }`}
            >
              {citation.freshness || "AVAILABLE"}
            </span>
          </div>

          <div className={styles.detailsGrid}>
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Nguồn công bố:</span>
              <span className={styles.detailValue}>
                {citation.source_url ? (
                  <a
                    href={citation.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className={styles.sourceLink}
                  >
                    {citation.source || "Tài liệu đính kèm"} ↗
                  </a>
                ) : (
                  citation.source || "CSDL Chuẩn hóa"
                )}
              </span>
            </div>

            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Nguồn gốc (Origin):</span>
              <span className={styles.detailValue}>{citation.data_origin || "VERIFIED_PRIMARY"}</span>
            </div>

            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Ngày quan sát:</span>
              <span className={`${styles.detailValue} tabular-nums`}>
                {citation.observation_date || "N/A"}
              </span>
            </div>

            {citation.publication_date && (
              <div className={styles.detailRow}>
                <span className={styles.detailLabel}>Ngày công bố:</span>
                <span className={`${styles.detailValue} tabular-nums`}>
                  {citation.publication_date}
                </span>
              </div>
            )}

            {citation.note && (
              <div className={styles.noteBox}>
                <p>{citation.note}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </span>
  );
}
