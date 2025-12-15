# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python application for downloading Samurai Sudoku puzzles from [samurai-sudoku.com](https://www.samurai-sudoku.com/) by date range. The tool extracts puzzles as high-quality PDFs using Selenium to automate browser interactions. Supports both GUI (tkinter) and CLI modes, with parallel downloading capabilities.

This is a Python 3.13+ project managed with **uv**.

## Development Setup

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

## Running the Application

**GUI Mode** (default):
```bash
python main.py
```

**CLI Mode**:
```bash
python main.py -s 2024-01-01 -e 2024-01-31 -o ./puzzles
python main.py --start 2024-10-01 --end 2024-10-07 --output ./october --workers 5
python main.py -s 2024-01-01 -e 2024-01-07 -o ./puzzles --visible  # Non-headless mode
```

## Key Dependencies

- **Selenium**: Browser automation to navigate the site and trigger print dialogs
- **BeautifulSoup**: HTML parsing to extract puzzle metadata from archive dropdown
- **tkcalendar**: DateEntry widgets in the GUI
- **python-dateutil**: Flexible date parsing
- **tkinter**: GUI framework (built-in with Python)

Requires **Google Chrome** and compatible **chromedriver** for Selenium automation.

## Architecture

### Core Components

**`SamuraiSudokuDownloader`** - Main puzzle download engine
- `get_archive_puzzles()`: Scrapes dropdown (`select#ai`) on archive page to get available puzzles
- `extract_puzzle_from_page()`: Selects puzzle in dropdown, clicks print button, saves print preview as PDF using Chrome DevTools Protocol
- `download_puzzles()`: Orchestrates parallel downloads using `ThreadPoolExecutor`, filtering by date range
- `download_single_puzzle()`: Worker function - creates isolated browser instance per thread for thread-safe parallel downloads

**`SamuraiSudokuGUI`** - Tkinter GUI application
- Modern dark theme with custom styling
- Uses `DateEntry` widgets for date selection
- Runs downloads in background threads to avoid UI blocking
- Persistent settings stored in `~/.samurai_sudoku_downloader/settings.json`

**`SettingsManager`** - Settings persistence
- Stores user preferences (output directory) in JSON format
- Config location: `~/.samurai_sudoku_downloader/settings.json`

### Download Strategy

1. **Archive Parsing**: Load `https://www.samurai-sudoku.com/classic/`, parse dropdown options to get puzzle metadata (date, difficulty, value ID)
2. **Date Filtering**: Filter puzzles by user-specified date range
3. **Parallel Execution**: Launch multiple browser instances (default: 3 workers) to download puzzles concurrently
4. **PDF Capture**: For each puzzle:
   - Navigate to archive page
   - Select puzzle from dropdown by value attribute
   - Click print button, switch to print preview window
   - Use Chrome DevTools Protocol `Page.printToPDF` to capture as PDF
   - Save with filename format: `DD-MMM-YYYY - DIFFICULTY.pdf`
5. **Skip Existing**: Before downloading, check if PDF already exists to avoid re-downloading

### PDF Naming Convention

Format: `{DD-MMM-YYYY} - {Difficulty}.pdf`
- Example: `31-Oct-2025 - Hard.pdf`
- Date parsing handled by `python-dateutil` with fallback sanitization

### Thread Safety

- Each download worker creates its own `webdriver.Chrome()` instance to avoid conflicts
- Progress updates use thread-safe callbacks with `Lock()` for counter synchronization
- GUI updates dispatched to main thread using `root.after(0, callback)`

## File Structure

- `main.py` - Single-file application containing all classes and logic
- `analyze_site.py` - Utility script for debugging website structure changes
- `pyproject.toml` - Project metadata and dependencies (uv-managed)
- `.python-version` - Python 3.13 version constraint

## Common Development Tasks

**Debugging site changes**:
```bash
python analyze_site.py
```
This script inspects the samurai-sudoku.com archive page structure to help diagnose issues if the website HTML changes.

**Testing with visible browser** (for troubleshooting Selenium):
```bash
python main.py --start 2024-01-01 --end 2024-01-01 --output ./test --visible
```

## Important Implementation Notes

- **Parallel downloads**: Each worker thread spawns its own Chrome instance. The class stores a primary `self.driver` for sequential operations, but parallel downloads use thread-local drivers passed via `driver=` and `wait=` parameters.
- **Headless mode**: Default for efficiency. Use `--visible` flag in CLI or `headless=False` for debugging.
- **Fallback mechanism**: If print button not found, falls back to HTML extraction and screenshot capture (legacy, rarely used).
- **Chrome DevTools Protocol**: PDF generation uses `driver.execute_cdp_cmd("Page.printToPDF", options)` to capture print preview without triggering OS print dialog.
