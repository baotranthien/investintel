import React, { type JSX } from "react";
import styles from "./page-header.module.css";

export function PageHeader({
  title,
  description,
  meta,
  actions,
  className,
}: {
  title: string;
  description?: string;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}): JSX.Element {
  return (
    <header className={`${styles.container}${className ? ` ${className}` : ""}`}>
      <div className={styles.mainRow}>
        <div className={styles.leftGroup}>
          <h1 className={styles.title}>{title}</h1>
          {meta ? <div className={styles.meta}>{meta}</div> : null}
        </div>
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </div>
      {description ? <p className={styles.description} title={description}>{description}</p> : null}
    </header>
  );
}
