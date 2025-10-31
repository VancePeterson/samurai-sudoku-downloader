# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python application for downloading Samurai Sudoku puzzles. This is a Python 3.13+ project managed with uv.

## Development Setup

The project uses Python 3.13 (specified in `.python-version`). Dependencies are managed via `pyproject.toml`.

To set up the development environment:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

## Running the Application

```bash
python main.py
```

## Project Structure

This is a minimal single-file Python application:
- `main.py` - Entry point containing the main() function
- `pyproject.toml` - Project metadata and dependencies
- `.python-version` - Specifies Python 3.13

No dependencies are currently specified in the project.
