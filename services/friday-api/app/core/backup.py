import os
import shutil
import json
import glob
from datetime import datetime
from typing import List, Optional
from loguru import logger


def backup_sqlite(db_path: str, backup_dir: str) -> Optional[str]:
    if not os.path.exists(db_path):
        logger.warning(f"SQLite database not found at {db_path}")
        return None
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    basename = os.path.basename(db_path)
    backup_path = os.path.join(backup_dir, f"{basename}.{timestamp}.bak")
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Backed up SQLite: {db_path} → {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup {db_path}: {e}")
        return None


def backup_json(json_path: str, backup_dir: str) -> Optional[str]:
    if not os.path.exists(json_path):
        logger.warning(f"JSON file not found at {json_path}")
        return None
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    basename = os.path.basename(json_path)
    backup_path = os.path.join(backup_dir, f"{basename}.{timestamp}.bak")
    try:
        shutil.copy2(json_path, backup_path)
        logger.info(f"Backed up JSON: {json_path} → {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup {json_path}: {e}")
        return None


def backup_directory(source_dir: str, backup_dir: str, pattern: str = "*") -> Optional[str]:
    if not os.path.exists(source_dir):
        logger.warning(f"Source directory not found at {source_dir}")
        return None
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    basename = os.path.basename(source_dir)
    archive_path = os.path.join(backup_dir, f"{basename}.{timestamp}.tar")
    try:
        import tarfile
        with tarfile.open(archive_path, "w") as tar:
            for file_path in glob.glob(os.path.join(source_dir, pattern)):
                tar.add(file_path, arcname=os.path.relpath(file_path, source_dir))
        logger.info(f"Backed up directory: {source_dir} → {archive_path}")
        return archive_path
    except Exception as e:
        logger.error(f"Failed to backup directory {source_dir}: {e}")
        return None


def restore_file(backup_path: str, target_path: str) -> bool:
    if not os.path.exists(backup_path):
        logger.error(f"Backup file not found: {backup_path}")
        return False
    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy2(backup_path, target_path)
        logger.info(f"Restored: {backup_path} → {target_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to restore {backup_path}: {e}")
        return False


def list_backups(backup_dir: str) -> List[str]:
    if not os.path.exists(backup_dir):
        return []
    return sorted(
        os.path.join(backup_dir, f)
        for f in os.listdir(backup_dir)
        if f.endswith(".bak") or f.endswith(".tar")
    )


def validate_backup(backup_path: str) -> bool:
    if not os.path.exists(backup_path):
        return False
    if backup_path.endswith(".bak"):
        return os.path.getsize(backup_path) > 0
    if backup_path.endswith(".tar"):
        import tarfile
        try:
            with tarfile.open(backup_path, "r") as tar:
                members = tar.getmembers()
            return len(members) > 0
        except Exception:
            return False
    return False
