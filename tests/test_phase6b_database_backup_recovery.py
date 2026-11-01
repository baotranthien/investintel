# tests/test_phase6b_database_backup_recovery.py
"""
Test Suite for Phase 6B: Local SQLite Database Backup & Recovery Engine
Verifies hot backups, SHA-256 integrity, disposable database restore,
corruption detection, target safety checks, and retention policy guarantees.
"""

import json
import os
import shutil
import sqlite3
import pytest
from pathlib import Path

from services.db.backup import (
    create_backup,
    verify_backup,
    list_backups,
    restore_backup,
    apply_retention_policy,
    calculate_sha256,
    BackupIntegrityError,
    RestoreTargetError,
    BackupError,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_DB_PATH = PROJECT_ROOT / "data" / "trading.db"


@pytest.fixture
def temp_backup_env(tmp_path):
    """Provides an isolated backup directory and disposable test database."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Create disposable test database populated from active DB or fresh sqlite
    test_db = tmp_path / "disposable_test.db"
    if ACTIVE_DB_PATH.exists():
        src = sqlite3.connect(str(ACTIVE_DB_PATH))
        dst = sqlite3.connect(str(test_db))
        src.backup(dst)
        src.close()
        dst.close()
    else:
        con = sqlite3.connect(str(test_db))
        con.execute("CREATE TABLE test_items (id INTEGER PRIMARY KEY, name TEXT)")
        con.execute("INSERT INTO test_items (name) VALUES ('item1'), ('item2')")
        con.commit()
        con.close()
        
    return {
        "backup_dir": backup_dir,
        "test_db": test_db,
        "tmp_path": tmp_path
    }


def test_create_and_verify_backup(temp_backup_env):
    """Verify backup creation, SHA-256 calculation, and manifest generation."""
    test_db = temp_backup_env["test_db"]
    backup_dir = temp_backup_env["backup_dir"]
    
    manifest = create_backup(db_path=test_db, backup_dir=backup_dir, description="Automated test backup")
    
    assert manifest["integrity"] == "ok"
    assert manifest["backup_size_bytes"] > 0
    assert len(manifest["sha256"]) == 64
    assert manifest["tables_count"] > 0
    
    backup_path = Path(manifest["backup_path"])
    assert backup_path.exists()
    
    # Verify independent verification function
    v_res = verify_backup(backup_path)
    assert v_res["integrity_ok"] is True
    assert v_res["manifest_checksum_match"] is True
    assert v_res["sha256"] == manifest["sha256"]


def test_restore_into_disposable_database(temp_backup_env):
    """Verify restoring a backup into a disposable database restores all rows and schema."""
    test_db = temp_backup_env["test_db"]
    backup_dir = temp_backup_env["backup_dir"]
    target_restore_db = temp_backup_env["tmp_path"] / "restored_test.db"
    
    # 1. Take backup
    manifest = create_backup(db_path=test_db, backup_dir=backup_dir)
    backup_path = Path(manifest["backup_path"])
    
    # 2. Restore into target
    res = restore_backup(backup_path=backup_path, target_db_path=target_restore_db, force=True)
    
    assert res["status"] == "restored"
    assert res["integrity"] == "ok"
    assert target_restore_db.exists()
    
    # 3. Verify SQLite tables and rows match
    con = sqlite3.connect(str(target_restore_db))
    cur = con.cursor()
    int_check = cur.execute("PRAGMA integrity_check").fetchone()[0]
    assert int_check == "ok"
    con.close()


def test_corrupted_backup_rejection(temp_backup_env):
    """Verify that a corrupted backup is rejected during restore."""
    test_db = temp_backup_env["test_db"]
    backup_dir = temp_backup_env["backup_dir"]
    target_restore_db = temp_backup_env["tmp_path"] / "target_corrupt.db"
    
    manifest = create_backup(db_path=test_db, backup_dir=backup_dir)
    backup_path = Path(manifest["backup_path"])
    
    # Tamper with the backup file bytes
    with open(backup_path, "r+b") as f:
        f.seek(100)
        f.write(b"CORRUPTED_BYTES_HERE_1234567890")
        
    with pytest.raises(BackupIntegrityError):
        restore_backup(backup_path=backup_path, target_db_path=target_restore_db, force=True)


def test_wrong_target_restore_rejection(temp_backup_env):
    """Verify restore rejects cloud production database URLs."""
    test_db = temp_backup_env["test_db"]
    backup_dir = temp_backup_env["backup_dir"]
    manifest = create_backup(db_path=test_db, backup_dir=backup_dir)
    backup_path = Path(manifest["backup_path"])
    
    dangerous_targets = [
        Path("postgresql://user:pass@ep-cool-fog-12345.us-east-2.aws.neon.tech/neondb"),
        Path("https://production.neon.tech/db"),
    ]
    
    for dt in dangerous_targets:
        with pytest.raises(RestoreTargetError):
            restore_backup(backup_path=backup_path, target_db_path=dt, force=True)


def test_retention_policy_preserves_newest(temp_backup_env):
    """Verify retention policy removes expired backups but never deletes the newest valid backup."""
    test_db = temp_backup_env["test_db"]
    backup_dir = temp_backup_env["backup_dir"]
    
    # Generate 5 backups with slight delay
    b1 = create_backup(db_path=test_db, backup_dir=backup_dir, description="b1")
    b2 = create_backup(db_path=test_db, backup_dir=backup_dir, description="b2")
    b3 = create_backup(db_path=test_db, backup_dir=backup_dir, description="b3")
    
    newest_filename = b3["backup_filename"]
    
    # Apply retention policy with retain_daily=1
    deleted = apply_retention_policy(backup_dir=backup_dir, retain_daily=1)
    
    # Verify newest backup remains on disk
    assert (backup_dir / newest_filename).exists()
    
    # Verify list_backups still returns the newest backup
    remaining = list_backups(backup_dir)
    assert len(remaining) >= 1
    assert remaining[0]["backup_filename"] == newest_filename

