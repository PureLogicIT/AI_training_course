# devlog

A minimal command-line developer work-log tool. Record, search, and manage dated notes directly from your terminal.

## Project Status

Core features implemented: entry creation, listing, keyword search, entry deletion.

## Requirements

- Python 3.10 or later
- No third-party packages required

## File Layout

```
devlog/
├── devlog.py    # Main entry point and core logic
├── config.py    # Configuration constants
├── CHANGELOG.md # Project changelog
├── README.md    # This file
└── .env         # Local environment overrides (DO NOT COMMIT)
```

## Quick Start

```bash
# Log a new entry (interactive)
python3 devlog.py

# List all entries
python3 devlog.py --list

# Search entries by keyword
python3 devlog.py --search error

# Delete entry by ID
python3 devlog.py --delete 2
```

## Contributing

Work on feature branches. Never commit directly to `main`.

## Usage

Run `python3 devlog.py --help` for a full list of flags.
