# Initial-commit---NIT-Trichy-internship-project
Automated file organizer in Python — sorts 60+ file types into categorized folders, detects duplicates via MD5 hashing, supports dry-run mode, and generates timestamped logs and JSON reports.
# SmartOrganize 📂

An automated Python file organizer that sorts your messy folders in seconds.

## Features
- **Auto-categorization** — Sorts 60+ file types into folders (Images, Videos, Code, Documents, etc.)
- **Duplicate detection** — MD5 hashing finds identical files before moving
- **Dry-run mode** — Preview what will happen without touching any files
- **Conflict resolution** — Renames files automatically to avoid overwrites
- **Detailed logging** — Every action is saved to a timestamped `.log` file
- **JSON reports** — Machine-readable summary after each run

## Requirements
- Python 3.10+ (uses walrus operator `:=` and `list[Path]` syntax)
- No third-party libraries needed — pure standard library

## Usage

```bash
# Basic usage
python organizer.py ~/Downloads

# Preview changes (safe, nothing moves)
python organizer.py ~/Downloads --dry-run

# Organize and save a JSON report
python organizer.py ~/Desktop --report

# Both flags together
python organizer.py ~/Documents --dry-run --report
```

## Output Folder Structure

```
Downloads/
├── Images/
│   ├── photo.jpg
│   └── screenshot.png
├── Code/
│   ├── script.py
│   └── index.html
├── Documents/
│   └── resume.pdf
├── Videos/
│   └── tutorial.mp4
└── _SmartOrganize_Logs/
    ├── organizer_20260410_143022.log
    └── report_20260410_143022.json
```

## How It Works

1. **Scan** — Lists all files in the target folder (non-recursive)
2. **Hash** — Computes MD5 hash of each file for duplicate detection
3. **Categorize** — Maps file extension to the appropriate folder
4. **Move** — Moves each file to its category folder (with rename on conflict)
5. **Report** — Logs everything and optionally saves a JSON summary

## File Categories

| Category    | Extensions                                           |
|-------------|------------------------------------------------------|
| Images      | jpg, png, gif, svg, webp, heic, ...                  |
| Videos      | mp4, mkv, avi, mov, webm, ...                        |
| Audio       | mp3, wav, flac, aac, ogg, ...                        |
| Documents   | pdf, docx, xlsx, pptx, txt, md, ...                  |
| Code        | py, js, html, css, java, cpp, json, sql, ...         |
| Archives    | zip, rar, tar, gz, 7z, ...                           |
| Data        | csv, tsv, db, sqlite, parquet, ...                   |
| Others      | Everything else                                      |

## Author
Built as a mini project for NIT Trichy CDI Summer Internship 2026 application.
