"""
SmartOrganize — Automated File Organizer
=========================================
Automatically organizes files in any folder by:
  • Extension-based sorting into categorized subfolders
  • Duplicate detection using MD5 hashing
  • Detailed activity logging with timestamps
  • Dry-run mode (preview without moving anything)
  • JSON summary report after each run

Usage:
  python organizer.py <folder_path> [--dry-run] [--report]

Examples:
  python organizer.py ~/Downloads
  python organizer.py ~/Desktop --dry-run
  python organizer.py C:\\Users\\You\\Downloads --report
"""

import os
import sys
import shutil
import hashlib
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────
# FILE TYPE CATEGORIES
# ─────────────────────────────────────────────
CATEGORIES = {
    "Images":     [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico", ".heic"],
    "Videos":     [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpeg"],
    "Audio":      [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus"],
    "Documents":  [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".txt", ".rtf", ".md"],
    "Code":       [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".cs", ".go", ".rs",
                   ".php", ".rb", ".sh", ".bat", ".json", ".xml", ".yaml", ".yml", ".sql", ".ipynb"],
    "Archives":   [".zip", ".rar", ".tar", ".gz", ".7z", ".bz2", ".xz", ".tar.gz"],
    "Executables":[".exe", ".msi", ".dmg", ".apk", ".deb", ".rpm"],
    "Fonts":      [".ttf", ".otf", ".woff", ".woff2"],
    "Data":       [".csv", ".tsv", ".db", ".sqlite", ".parquet", ".feather"],
    "Others":     [],  # Catch-all for unrecognized types
}

# Build reverse lookup: extension → category
EXT_MAP = {}
for category, extensions in CATEGORIES.items():
    for ext in extensions:
        EXT_MAP[ext.lower()] = category


# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────
def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"organizer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logger = logging.getLogger("SmartOrganize")
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    # Console handler (colorized)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(ConsoleFormatter())

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger, log_file


class ConsoleFormatter(logging.Formatter):
    COLORS = {
        "DEBUG":    "\033[90m",   # Gray
        "INFO":     "\033[97m",   # White
        "WARNING":  "\033[93m",   # Yellow
        "ERROR":    "\033[91m",   # Red
        "CRITICAL": "\033[95m",   # Magenta
    }
    RESET = "\033[0m"
    BOLD  = "\033[1m"

    ICONS = {
        "DEBUG":    "·",
        "INFO":     "→",
        "WARNING":  "⚠",
        "ERROR":    "✗",
        "CRITICAL": "!!",
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        icon  = self.ICONS.get(record.levelname, "")
        msg   = record.getMessage()
        return f"{color}{icon}  {msg}{self.RESET}"


# ─────────────────────────────────────────────
# FILE HASHING (Duplicate Detection)
# ─────────────────────────────────────────────
def file_md5(filepath: Path, chunk_size: int = 65536) -> str:
    """Compute MD5 hash of a file for duplicate detection."""
    hasher = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (IOError, PermissionError):
        return None


# ─────────────────────────────────────────────
# CATEGORY RESOLVER
# ─────────────────────────────────────────────
def get_category(file: Path) -> str:
    suffix = file.suffix.lower()
    # Handle compound extensions like .tar.gz
    if file.name.endswith(".tar.gz"):
        return "Archives"
    return EXT_MAP.get(suffix, "Others")


# ─────────────────────────────────────────────
# CONFLICT RESOLVER (avoid overwriting files)
# ─────────────────────────────────────────────
def resolve_conflict(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    counter = 1
    while True:
        new_dest = parent / f"{stem}_({counter}){suffix}"
        if not new_dest.exists():
            return new_dest
        counter += 1


# ─────────────────────────────────────────────
# CORE ORGANIZER CLASS
# ─────────────────────────────────────────────
class SmartOrganize:
    def __init__(self, target_dir: str, dry_run: bool = False, generate_report: bool = False):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.dry_run = dry_run
        self.generate_report = generate_report

        if not self.target_dir.exists():
            print(f"\n✗  Directory not found: {self.target_dir}\n")
            sys.exit(1)

        log_dir = self.target_dir / "_SmartOrganize_Logs"
        self.logger, self.log_file = setup_logger(log_dir)

        # Stats tracking
        self.stats = {
            "scanned": 0,
            "moved": 0,
            "skipped_duplicates": 0,
            "skipped_errors": 0,
            "by_category": defaultdict(int),
            "duplicates": [],
            "errors": [],
        }
        self.seen_hashes = {}  # hash → first file path

    def scan(self) -> list[Path]:
        """Collect all files in target dir (non-recursive, skip hidden & log folder)."""
        files = []
        skip_dirs = {"_SmartOrganize_Logs"}
        for item in self.target_dir.iterdir():
            if item.is_file() and not item.name.startswith("."):
                files.append(item)
        return files

    def process(self):
        mode_label = "DRY RUN — no files will be moved" if self.dry_run else "LIVE RUN"
        self.logger.info("=" * 60)
        self.logger.info(f"SmartOrganize  |  {mode_label}")
        self.logger.info(f"Target : {self.target_dir}")
        self.logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 60)

        files = self.scan()
        self.stats["scanned"] = len(files)
        self.logger.info(f"Found {len(files)} files to process\n")

        for file in files:
            self._process_file(file)

        self._print_summary()
        if self.generate_report:
            self._save_report()

    def _process_file(self, file: Path):
        category = get_category(file)
        dest_dir = self.target_dir / category

        # Duplicate detection
        file_hash = file_md5(file)
        if file_hash and file_hash in self.seen_hashes:
            original = self.seen_hashes[file_hash]
            self.logger.warning(f"DUPLICATE: '{file.name}'  →  same as '{original}'")
            self.stats["skipped_duplicates"] += 1
            self.stats["duplicates"].append({
                "file": str(file),
                "duplicate_of": str(original)
            })
            return

        if file_hash:
            self.seen_hashes[file_hash] = file.name

        # Resolve destination
        dest_file = resolve_conflict(dest_dir / file.name)

        # Move (or simulate)
        if self.dry_run:
            self.logger.info(f"[DRY] '{file.name}'  →  {category}/")
            self.stats["moved"] += 1
            self.stats["by_category"][category] += 1
        else:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file), str(dest_file))
                moved_name = dest_file.name
                note = f" (renamed: {moved_name})" if moved_name != file.name else ""
                self.logger.info(f"Moved '{file.name}'  →  {category}/{note}")
                self.stats["moved"] += 1
                self.stats["by_category"][category] += 1
            except (PermissionError, shutil.Error, OSError) as e:
                self.logger.error(f"Failed to move '{file.name}': {e}")
                self.stats["skipped_errors"] += 1
                self.stats["errors"].append({"file": str(file), "error": str(e)})

    def _print_summary(self):
        s = self.stats
        self.logger.info("\n" + "=" * 60)
        self.logger.info("SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Files scanned   : {s['scanned']}")
        self.logger.info(f"Files moved     : {s['moved']}")
        self.logger.info(f"Duplicates      : {s['skipped_duplicates']}")
        self.logger.info(f"Errors skipped  : {s['skipped_errors']}")

        if s["by_category"]:
            self.logger.info("\nBy Category:")
            for cat, count in sorted(s["by_category"].items(), key=lambda x: -x[1]):
                bar = "█" * min(count, 20)
                self.logger.info(f"  {cat:<15} {bar} {count}")

        self.logger.info(f"\nLog saved to: {self.log_file}")

    def _save_report(self):
        report = {
            "run_date": datetime.now().isoformat(),
            "target_directory": str(self.target_dir),
            "dry_run": self.dry_run,
            "stats": {
                "scanned": self.stats["scanned"],
                "moved": self.stats["moved"],
                "skipped_duplicates": self.stats["skipped_duplicates"],
                "skipped_errors": self.stats["skipped_errors"],
                "by_category": dict(self.stats["by_category"]),
            },
            "duplicates": self.stats["duplicates"],
            "errors": self.stats["errors"],
        }
        report_path = self.target_dir / "_SmartOrganize_Logs" / \
            f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        self.logger.info(f"JSON report saved: {report_path}")


# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="SmartOrganize",
        description="Automatically organize files in a folder by type.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python organizer.py ~/Downloads
  python organizer.py ~/Desktop --dry-run
  python organizer.py "C:\\Users\\You\\Downloads" --report
        """
    )
    parser.add_argument("folder", help="Path to the folder to organize")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without moving any files")
    parser.add_argument("--report", action="store_true",
                        help="Save a JSON summary report after organizing")

    # Show help if no arguments provided
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n📂  Quick start: python organizer.py ~/Downloads\n")
        sys.exit(0)

    args = parser.parse_args()

    print(f"\n\033[1m📂  SmartOrganize\033[0m  —  by [Your Name]")
    print(f"{'─' * 50}")
    if args.dry_run:
        print("\033[93m⚠  DRY RUN MODE — no files will actually be moved\033[0m")

    organizer = SmartOrganize(
        target_dir=args.folder,
        dry_run=args.dry_run,
        generate_report=args.report
    )
    organizer.process()


if __name__ == "__main__":
    main()
