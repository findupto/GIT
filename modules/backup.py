from pathlib import Path
from datetime import datetime
import sqlite3


def backup_database(db, target=None):
    """Create a consistent SQLite backup using the SQLite backup API."""
    target = Path(target) if target else Path('backups') / f"fastfood_{datetime.now():%Y%m%d_%H%M%S}.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    dest = sqlite3.connect(target)
    try:
        db.conn.backup(dest)
        dest.commit()
    finally:
        dest.close()
    return target


def restore_database(target, db_path):
    """Restore a backup into a new database file. Caller should restart the POS."""
    src = sqlite3.connect(target)
    dest = sqlite3.connect(db_path)
    try:
        src.backup(dest)
        dest.commit()
    finally:
        src.close(); dest.close()
    return Path(db_path)
