# ⚔️ Samurai Sudoku Puzzle Downloader

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🌟 Project Overview

This is a versatile Python utility designed to download **Samurai Sudoku** puzzles from the official [https://www.samurai-sudoku.com/](https://www.samurai-sudoku.com/) archive for a specified date range. The puzzles are captured from the site's print preview and saved as high-quality **Print-ready PDF files** for offline solving.

It supports both a **Command Line Interface (CLI)** for scripting and automation, and a **Graphical User Interface (GUI)** built with `tkinter` for easy, visual selection and download management.

## ✨ Features

* **Date Range Selection:** Download all puzzles published within a start and end date.
* **PDF Output:** Puzzles are saved as high-quality PDF files.
* **Parallel Downloads:** Uses a `ThreadPoolExecutor` and separate browser instances for fast, concurrent downloading.
* **GUI Mode:** A modern, dark-themed GUI built with `tkinter` for easy operation.
* **Headless Browsing:** Runs `chromedriver` in headless mode by default for resource efficiency.
* **Skip Existing Files:** Automatically checks and skips puzzles that have already been downloaded.

---

## 🚀 Installation

### Prerequisites

You must have **Python 3.8 or higher** and **Google Chrome** installed on your system.

### Step 1: Clone the Repository

```bash
git clone [https://github.com/YourUsername/samurai-sudoku-downloader.git](https://github.com/YourUsername/samurai-sudoku-downloader.git)
cd samurai-sudoku-downloader