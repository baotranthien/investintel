"""
InvestIntel Local SQLite Database Backup & Recovery Engine
Phase 6B: Local Data Durability, Online Hot Backups, Integrity Verification & Point-in-Time Restore
"""

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

DEFAULT_BACKUP_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "backups"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "trading.db"


class BackupError(Exception):
    """Base exception for database backup and restore operations."""
    pass


class BackupIntegrityError(BackupError):
    """Raised when a backup fails PRAGMA integrity check or checksum validation."""
    pass


class RestoreTargetError(BackupError):
    """Raised when an invalid or unsafe database target path is specified for restore."""
    pass


def calculate_sha256(file_path: Path) -> str:
    """Calculates the SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_table_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    """Retrieves row counts for key tables in the database."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]
    counts = {}
    for t in tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{t}"')
            counts[t] = cur.fetchone()[0]
        except Exception:
            counts[t] = -1
    return counts


def create_backup(
    db_path: Optional[Path] = None,
    backup_dir: Optional[Path] = None,
    description: str = "",
) -> Dict[str, Any]:
    """
    Creates an online, non-blocking snapshot of the SQLite database.
    Safe for WAL mode and concurrent reads/writes.
    """
    db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    backup_dir = Path(backup_dir) if backup_dir else DEFAULT_BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        raise BackupError(f"Source database not found at {db_path}")

    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    backup_filename = f"investintel_{timestamp_str}.db"
    backup_path = backup_dir / backup_filename
    manifest_path = backup_dir / f"investintel_{timestamp_str}.manifest.json"

    source_size = db_path.stat().st_size
    t0 = time.time()

    # 1. Perform SQLite online backup (handles WAL & concurrent transactions cleanly)
    src_conn = sqlite3.connect(str(db_path))
    dst_conn = sqlite3.connect(str(backup_path))
    try:
        src_conn.backup(dst_conn, pages=100)
    finally:
        dst_conn.close()
        src_conn.close()

    duration_sec = round(time.time() - t0, 3)
    backup_size = backup_path.stat().st_size
    sha256_hash = calculate_sha256(backup_path)

    # 2. Independent Verification of generated backup
    try:
        check_conn = sqlite3.connect(str(backup_path))
        try:
            cur = check_conn.cursor()
            integrity_rows = cur.execute("PRAGMA integrity_check").fetchall()
            if not integrity_rows or integrity_rows[0][0] != "ok":
                if backup_path.exists():
                    backup_path.unlink()
                raise BackupIntegrityError(f"Backup failed PRAGMA integrity_check: {integrity_rows}")

            # Extract Alembic schema version
            try:
                alembic_ver = cur.execute("SELECT version_num FROM alembic_version").fetchone()
                schema_version = alembic_ver[0] if alembic_ver else "none"
            except Exception:
                schema_version = "unknown"

            table_counts = get_table_counts(check_conn)
            tables_count = len(table_counts)
        finally:
            check_conn.close()
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as exc:
        if backup_path.exists():
            backup_path.unlink()
        raise BackupIntegrityError(f"Generated backup corrupted during creation: {exc}") from exc

    manifest_data = {
        "timestamp": now.isoformat(),
        "timestamp_str": timestamp_str,
        "backup_filename": backup_filename,
        "backup_path": str(backup_path),
        "source_path": str(db_path.resolve()),
        "source_size_bytes": source_size,
        "backup_size_bytes": backup_size,
        "sha256": sha256_hash,
        "duration_sec": duration_sec,
        "schema_version": schema_version,
        "tables_count": tables_count,
        "table_row_counts": table_counts,
        "integrity": "ok",
        "description": description,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    logger.info(f"SQLite backup created: {backup_path.name} ({backup_size} bytes, sha256={sha256_hash[:8]}...) in {duration_sec}s")
    return manifest_data


def verify_backup(backup_path: Path) -> Dict[str, Any]:
    """
    Verifies a backup file against SQLite integrity check and its manifest checksum.
    """
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise BackupError(f"Backup file not found at {backup_path}")

    current_hash = calculate_sha256(backup_path)

    # Check PRAGMA integrity
    try:
        conn = sqlite3.connect(str(backup_path))
        try:
            cur = conn.cursor()
            integrity_res = cur.execute("PRAGMA integrity_check").fetchall()
            is_ok = bool(integrity_res and integrity_res[0][0] == "ok")
            table_counts = get_table_counts(conn)
        finally:
            conn.close()
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as exc:
        logger.warning(f"Integrity check failed with database error: {exc}")
        is_ok = False
        table_counts = {}

    manifest_path = backup_path.with_suffix(".manifest.json")
    manifest_match = None
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            manifest_match = (manifest_data.get("sha256") == current_hash)
        except Exception:
            manifest_match = False

    return {
        "backup_path": str(backup_path),
        "sha256": current_hash,
        "integrity_ok": is_ok,
        "manifest_exists": manifest_path.exists(),
        "manifest_checksum_match": manifest_match,
        "tables_count": len(table_counts),
        "table_row_counts": table_counts,
    }


def list_backups(backup_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Lists all available backups in the backup directory, sorted from newest to oldest.
    """
    backup_dir = Path(backup_dir) if backup_dir else DEFAULT_BACKUP_DIR
    if not backup_dir.exists():
        return []

    manifests = list(backup_dir.glob("*.manifest.json"))
    results = []

    for m_path in manifests:
        try:
            with open(m_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            db_file = Path(data.get("backup_path", ""))
            data["exists_on_disk"] = db_file.exists()
            results.append(data)
        except Exception as e:
            logger.warning(f"Error reading manifest {m_path}: {e}")

    # Fallback for .db files without manifest
    for db_path in backup_dir.glob("*.db"):
        m_check = db_path.with_suffix(".manifest.json")
        if not m_check.exists() and "safety_backup" not in db_path.name:
            results.append({
                "backup_filename": db_path.name,
                "backup_path": str(db_path),
                "timestamp": datetime.fromtimestamp(db_path.stat().st_mtime).isoformat(),
                "backup_size_bytes": db_path.stat().st_size,
                "integrity": "unverified",
                "exists_on_disk": True,
            })

    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return results


def apply_retention_policy(
    backup_dir: Optional[Path] = None,
    retain_daily: int = 7,
    retain_weekly: int = 4,
    retain_monthly: int = 6,
) -> List[str]:
    """
    Applies backup retention policy.
    SAFETY RULE: The newest valid backup is NEVER deleted under any circumstances.
    """
    backup_dir = Path(backup_dir) if backup_dir else DEFAULT_BACKUP_DIR
    backups = list_backups(backup_dir)
    if len(backups) <= 1:
        return []

    # Newest backup is protected
    newest = backups[0]
    kept_files = {newest.get("backup_filename")}
    deleted_files = []

    # Group by daily, weekly (ISO year-week), and monthly (YYYY-MM) buckets
    daily_buckets: Dict[str, Dict[str, Any]] = {}
    weekly_buckets: Dict[str, Dict[str, Any]] = {}
    monthly_buckets: Dict[str, Dict[str, Any]] = {}

    for b in backups:
        ts_str = b.get("timestamp_str", "")
        if not ts_str and "timestamp" in b:
            ts_str = b["timestamp"].replace("-", "").replace(":", "")[:8]

        dt_val: Optional[date] = None
        if len(ts_str) >= 8:
            try:
                dt_val = date(int(ts_str[:4]), int(ts_str[4:6]), int(ts_str[6:8]))
            except ValueError:
                pass
        elif "timestamp" in b:
            try:
                dt_val = datetime.fromisoformat(b["timestamp"]).date()
            except ValueError:
                pass

        if dt_val:
            day_key = dt_val.isoformat()
            iso_year, iso_week, _ = dt_val.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            month_key = f"{dt_val.year}-{dt_val.month:02d}"
        else:
            day_key = ts_str[:8] if len(ts_str) >= 8 else "unknown"
            week_key = day_key
            month_key = day_key[:6] if len(day_key) >= 6 else day_key

        if day_key not in daily_buckets:
            daily_buckets[day_key] = b
        if week_key not in weekly_buckets:
            weekly_buckets[week_key] = b
        if month_key not in monthly_buckets:
            monthly_buckets[month_key] = b

    sorted_days = sorted(daily_buckets.keys(), reverse=True)
    for d in sorted_days[:retain_daily]:
        fn = daily_buckets[d].get("backup_filename")
        if fn:
            kept_files.add(fn)

    sorted_weeks = sorted(weekly_buckets.keys(), reverse=True)
    for w in sorted_weeks[:retain_weekly]:
        fn = weekly_buckets[w].get("backup_filename")
        if fn:
            kept_files.add(fn)

    sorted_months = sorted(monthly_buckets.keys(), reverse=True)
    for m in sorted_months[:retain_monthly]:
        fn = monthly_buckets[m].get("backup_filename")
        if fn:
            kept_files.add(fn)

    # Determine files to delete
    for b in backups:
        fname = b.get("backup_filename")
        if fname and fname not in kept_files:
            b_path = Path(b.get("backup_path", ""))
            m_path = b_path.with_suffix(".manifest.json")
            if b_path.exists():
                b_path.unlink()
                deleted_files.append(fname)
            if m_path.exists():
                m_path.unlink()

    logger.info(f"Backup retention policy applied: kept {len(kept_files)}, deleted {len(deleted_files)}")
    return deleted_files


def restore_backup(
    backup_path: Path,
    target_db_path: Optional[Path] = None,
    force: bool = False,
    create_pre_restore_snapshot: bool = True,
) -> Dict[str, Any]:
    """
    Safely restores a SQLite database from a verified backup.
    1. Pre-flight verification of backup integrity and hash.
    2. Protection: Rejects invalid or production cloud database targets.
    3. Creates a pre-restore safety snapshot of the active target DB.
    4. Performs restore via SQLite online backup API.
    5. Post-restore integrity verification.
    """
    backup_path = Path(backup_path)
    target_db_path = Path(target_db_path) if target_db_path else DEFAULT_DB_PATH

    # Target path safety: Must be a local SQLite file
    target_str = str(target_db_path).lower()
    if "neon.tech" in target_str or "ep-" in target_str or target_str.startswith("postgresql"):
        raise RestoreTargetError(f"Refusing to restore over cloud production target: {target_db_path}")

    if not backup_path.exists():
        raise BackupError(f"Backup file does not exist: {backup_path}")

    # 1. Verify backup integrity
    verify_res = verify_backup(backup_path)
    if not verify_res["integrity_ok"]:
        raise BackupIntegrityError(f"Cannot restore: Backup failed integrity check: {backup_path}")

    if verify_res["manifest_exists"] and verify_res["manifest_checksum_match"] is False:
        raise BackupIntegrityError(f"Cannot restore: Backup checksum does not match manifest!")

    backup_dir = backup_path.parent
    safety_snapshot_path = None

    # 2. Create pre-restore safety snapshot if target currently exists
    if target_db_path.exists() and create_pre_restore_snapshot:
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_snapshot_path = backup_dir / f"investintel_pre_restore_safety_{now_str}.db"
        src_conn = sqlite3.connect(str(target_db_path))
        dst_conn = sqlite3.connect(str(safety_snapshot_path))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()
        logger.info(f"Created pre-restore safety snapshot at {safety_snapshot_path}")

    # 3. Perform atomic online restore into target
    target_db_path.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(str(backup_path))
    dst_conn = sqlite3.connect(str(target_db_path))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    # 4. Post-restore verification
    post_conn = sqlite3.connect(str(target_db_path))
    try:
        cur = post_conn.cursor()
        int_res = cur.execute("PRAGMA integrity_check").fetchall()
        post_ok = bool(int_res and int_res[0][0] == "ok")
        table_counts = get_table_counts(post_conn)
    finally:
        post_conn.close()

    if not post_ok:
        # Rollback to safety snapshot if available
        if safety_snapshot_path and safety_snapshot_path.exists():
            shutil.copy2(safety_snapshot_path, target_db_path)
        raise BackupIntegrityError(f"Post-restore integrity check failed! Target database may be corrupt.")

    return {
        "status": "restored",
        "backup_path": str(backup_path),
        "target_db_path": str(target_db_path),
        "safety_snapshot_path": str(safety_snapshot_path) if safety_snapshot_path else None,
        "tables_count": len(table_counts),
        "table_row_counts": table_counts,
        "integrity": "ok",
    }
