#!/usr/bin/env python3
"""
Samurai Sudoku Puzzle Downloader

Downloads puzzles from https://www.samurai-sudoku.com/ for a specified date range.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import time
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from tkcalendar import DateEntry

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
except ImportError:
    print("ERROR: Selenium is required. Install with: pip install selenium")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: BeautifulSoup is required. Install with: pip install beautifulsoup4")
    sys.exit(1)

try:
    from dateutil import parser as date_parser
except ImportError:
    print("ERROR: python-dateutil is required. Install with: pip install python-dateutil")
    sys.exit(1)


class SamuraiSudokuDownloader:
    """Downloads Samurai Sudoku puzzles from samurai-sudoku.com"""

    BASE_URL = "https://www.samurai-sudoku.com/"
    ARCHIVE_URL = "https://www.samurai-sudoku.com/classic/"

    def __init__(self, output_dir, headless=True, verbose=True):
        """
        Initialize the downloader.

        Args:
            output_dir: Directory to save downloaded puzzles
            headless: Run browser in headless mode (no GUI)
            verbose: Print detailed messages (set to False for GUI mode)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        
        # Setup Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            error_msg = (
                f"Failed to initialize Chrome driver: {e}\n\n"
                f"Make sure you have Chrome and chromedriver installed.\n"
                f"On macOS, install with: brew install chromedriver\n"
                f"You may also need to allow chromedriver in System Settings > Privacy & Security"
            )
            if self.verbose:
                print(f"ERROR: {error_msg}")
            raise RuntimeError(error_msg) from e
        
        self.wait = WebDriverWait(self.driver, 10)
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        if hasattr(self, 'driver'):
            self.driver.quit()
    
    def get_archive_puzzles(self):
        """
        Navigate to the archive and extract available puzzle options from dropdown.
        
        Returns:
            List of dictionaries containing puzzle information
        """
        print(f"Loading archive page: {self.ARCHIVE_URL}")
        self.driver.get(self.ARCHIVE_URL)

        # Smart wait for dropdown to be present
        try:
            self.wait.until(EC.presence_of_element_located((By.ID, "ai")))
        except:
            time.sleep(2)  # Fallback if wait fails
        
        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        # Find the select element with id="ai" (archive dropdown)
        select_element = soup.find('select', {'id': 'ai'})
        
        if not select_element:
            print("ERROR: Could not find archive dropdown (select#ai)")
            return []
        
        puzzles = []
        options = select_element.find_all('option')
        
        print(f"Found {len(options)} puzzle options in archive")
        
        for option in options:
            value = option.get('value')
            text = option.get_text().strip()
            
            # Skip the default "Samurai Sudoku Archive" option
            if not value or value == '0':
                continue
            
            # Parse the text to extract date and difficulty
            # Format: "31st October 2025 - Hard"
            puzzle_info = {
                'value': value,
                'text': text,
                'date_str': None,
                'difficulty': None
            }
            
            # Try to parse date and difficulty from text
            if ' - ' in text:
                parts = text.split(' - ')
                puzzle_info['date_str'] = parts[0].strip()
                if len(parts) > 1:
                    puzzle_info['difficulty'] = parts[1].strip()
            
            puzzles.append(puzzle_info)
        
        print(f"Successfully extracted {len(puzzles)} puzzles from archive")
        return puzzles
    
    def extract_puzzle_from_page(self, puzzle_value, puzzle_info, driver=None, wait=None):
        """
        Extract puzzle data by selecting it from the dropdown and printing to PDF.

        Args:
            puzzle_value: The value attribute to select in the dropdown
            puzzle_info: Dictionary with puzzle information
            driver: Optional WebDriver instance (uses self.driver if not provided)
            wait: Optional WebDriverWait instance (uses self.wait if not provided)

        Returns:
            Dictionary containing puzzle data
        """
        # Use provided driver/wait or fall back to instance variables
        driver = driver or self.driver
        wait = wait or self.wait
        date_str = puzzle_info.get('date_str', 'unknown')
        if self.verbose:
            print(f"Loading puzzle: {date_str} (value: {puzzle_value})")

        try:
            # Find and interact with the select dropdown
            select_element = wait.until(
                EC.presence_of_element_located((By.ID, "ai"))
            )

            # Select the puzzle by value
            from selenium.webdriver.support.ui import Select
            select = Select(select_element)
            select.select_by_value(puzzle_value)

            # Wait for page to update after selection (smart wait instead of fixed sleep)
            time.sleep(0.5)  # Minimal delay for dropdown change

            # Store the main window handle
            main_window = driver.current_window_handle

            # Find and click the print button
            if self.verbose:
                print(f"  Looking for print button...")
            try:
                # Try common print button selectors
                print_button = None
                possible_selectors = [
                    (By.ID, "print"),
                    (By.ID, "btnPrint"),
                    (By.CLASS_NAME, "print"),
                    (By.XPATH, "//button[contains(text(), 'Print')]"),
                    (By.XPATH, "//a[contains(text(), 'Print')]"),
                    (By.XPATH, "//input[@type='button' and contains(@value, 'Print')]"),
                    (By.XPATH, "//button[contains(@class, 'print')]"),
                    (By.XPATH, "//a[contains(@class, 'print')]"),
                ]
                
                for selector_type, selector_value in possible_selectors:
                    try:
                        print_button = driver.find_element(selector_type, selector_value)
                        if print_button:
                            if self.verbose:
                                print(f"  ✓ Found print button using {selector_type}")
                            break
                    except NoSuchElementException:
                        continue

                if not print_button:
                    if self.verbose:
                        print(f"  ⚠ Print button not found, saving page HTML instead")
                    return self._save_page_html(puzzle_value, puzzle_info, driver, wait)

                # Click the print button
                if self.verbose:
                    print(f"  Clicking print button...")
                print_button.click()

                # Wait for new window/tab to open (smart wait)
                wait.until(lambda d: len(d.window_handles) > 1)

                # Switch to the new window
                for window_handle in driver.window_handles:
                    if window_handle != main_window:
                        driver.switch_to.window(window_handle)
                        break

                if self.verbose:
                    print(f"  ✓ Switched to print window")

                # Brief wait for print dialog to render
                time.sleep(0.5)

                # Look for "full page" button or similar
                if self.verbose:
                    print(f"  Looking for full page option...")
                try:
                    full_page_selectors = [
                        (By.XPATH, "//button[contains(text(), 'Full page')]"),
                        (By.XPATH, "//button[contains(text(), 'full page')]"),
                        (By.XPATH, "//input[@type='radio' and contains(@value, 'full')]"),
                        (By.XPATH, "//label[contains(text(), 'Full page')]"),
                        (By.ID, "fullPage"),
                        (By.ID, "full-page"),
                    ]
                    
                    full_page_button = None
                    for selector_type, selector_value in full_page_selectors:
                        try:
                            full_page_button = driver.find_element(selector_type, selector_value)
                            if full_page_button:
                                if self.verbose:
                                    print(f"  ✓ Found full page option")
                                full_page_button.click()
                                time.sleep(0.3)  # Brief wait for option to apply
                                break
                        except NoSuchElementException:
                            continue

                    if not full_page_button and self.verbose:
                        print(f"  ℹ Full page option not found, using default")

                except Exception as e:
                    if self.verbose:
                        print(f"  ℹ Could not interact with full page option: {e}")

                # Now save the print preview as PDF
                if self.verbose:
                    print(f"  Saving PDF from print preview...")
                
                # Create filename with format: DD-MMM-YYYY - DIFFICULTY.pdf
                # Parse the date string to get proper format
                try:
                    parsed_date = date_parser.parse(date_str, fuzzy=True)
                    formatted_date = parsed_date.strftime('%d-%b-%Y')  # e.g., 31-Oct-2025
                except:
                    # Fallback if parsing fails
                    formatted_date = date_str.replace(' ', '-')

                difficulty = puzzle_info.get('difficulty', 'Unknown')
                pdf_filename = f"{formatted_date} - {difficulty}.pdf"
                pdf_path = self.output_dir / pdf_filename

                # Use Chrome's print to PDF functionality
                print_options = {
                    'landscape': False,
                    'displayHeaderFooter': False,
                    'printBackground': True,
                    'preferCSSPageSize': True,
                }
                
                result = driver.execute_cdp_cmd("Page.printToPDF", print_options)

                # Save the PDF
                import base64
                with open(pdf_path, 'wb') as f:
                    f.write(base64.b64decode(result['data']))

                if self.verbose:
                    print(f"  ✓ Saved PDF: {pdf_filename}")

                # Close the print window and switch back to main window
                driver.close()
                driver.switch_to.window(main_window)

                # Prepare puzzle data
                puzzle_data = {
                    'value': puzzle_value,
                    'date_text': date_str,
                    'difficulty': puzzle_info.get('difficulty'),
                    'full_text': puzzle_info.get('text'),
                    'url': driver.current_url,
                    'timestamp': datetime.now().isoformat(),
                    'pdf_file': pdf_filename
                }
                
                return puzzle_data
                
            except Exception as e:
                if self.verbose:
                    print(f"  ✗ Error during print process: {e}")
                # Make sure we're back on the main window
                try:
                    driver.switch_to.window(main_window)
                except:
                    pass
                raise

        except TimeoutException:
            if self.verbose:
                print(f"  ✗ Timeout waiting for element")
            raise
        except Exception as e:
            if self.verbose:
                print(f"  ✗ Error loading puzzle: {e}")
            raise

    def _save_page_html(self, puzzle_value, puzzle_info, driver=None, wait=None):
        """
        Fallback method to save page HTML if print button is not found.

        Args:
            puzzle_value: The puzzle value
            puzzle_info: Dictionary with puzzle information
            driver: Optional WebDriver instance (uses self.driver if not provided)
            wait: Optional WebDriverWait instance (uses self.wait if not provided)

        Returns:
            Dictionary containing puzzle data
        """
        # Use provided driver/wait or fall back to instance variables
        driver = driver or self.driver
        wait = wait or self.wait

        date_str = puzzle_info.get('date_str', 'unknown')
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        puzzle_data = {
            'value': puzzle_value,
            'date_text': date_str,
            'difficulty': puzzle_info.get('difficulty'),
            'full_text': puzzle_info.get('text'),
            'url': driver.current_url,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save full HTML
        puzzle_data['html'] = str(soup)
        
        # Try to find the puzzle grid/table
        puzzle_container = (
            soup.find('table', {'id': lambda x: x and 'puzzle' in str(x).lower()}) or
            soup.find('div', {'id': lambda x: x and 'puzzle' in str(x).lower()}) or
            soup.find('table', {'class': lambda x: x and 'sudoku' in str(x).lower()}) or
            soup.find('div', {'class': lambda x: x and 'sudoku' in str(x).lower()})
        )
        
        if puzzle_container:
            puzzle_data['grid_html'] = str(puzzle_container)
        
        # Try to capture screenshot as fallback
        try:
            safe_date = date_str.replace(' ', '_').replace('/', '-')
            screenshot_filename = f"puzzle_{safe_date}.png"
            screenshot_path = self.output_dir / screenshot_filename

            driver.save_screenshot(str(screenshot_path))
            puzzle_data['screenshot'] = screenshot_filename
            print(f"  ✓ Saved screenshot: {screenshot_filename}")
        except Exception as e:
            print(f"  ⚠ Could not save screenshot: {e}")

        return puzzle_data
    
    def save_puzzle(self, puzzle_data, filename):
        """
        Save puzzle data to file.
        
        Args:
            puzzle_data: Dictionary containing puzzle information
            filename: Name of the output file (without extension) - NOT USED, keeping for compatibility
        """
        # Note: PDF is already saved during the print process
        if 'pdf_file' in puzzle_data:
            print(f"  ✓ PDF saved: {puzzle_data['pdf_file']}")
        
        # Only save HTML if available (fallback when print doesn't work)
        if 'grid_html' in puzzle_data and 'pdf_file' not in puzzle_data:
            # Only create HTML fallback if PDF wasn't created
            html_path = self.output_dir / f"{filename}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Samurai Sudoku - {puzzle_data.get('date_text', 'Unknown')}</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .info {{ 
            margin-bottom: 20px;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 5px;
        }}
        .info p {{
            margin: 5px 0;
        }}
        .puzzle {{
            margin-top: 20px;
        }}
        table {{
            border-collapse: collapse;
            margin: 20px auto;
        }}
        td {{
            border: 1px solid #999;
            padding: 5px;
            text-align: center;
            min-width: 30px;
            min-height: 30px;
        }}
    </style>
</head>
<body>
    <div class="info">
        <h1>Samurai Sudoku Puzzle</h1>
        <p><strong>Date:</strong> {puzzle_data.get('date_text', 'Unknown')}</p>
        <p><strong>Difficulty:</strong> {puzzle_data.get('difficulty', 'Unknown')}</p>
        <p><strong>Puzzle ID:</strong> {puzzle_data.get('value', 'N/A')}</p>
        <p><strong>Downloaded:</strong> {puzzle_data.get('timestamp', 'Unknown')}</p>
    </div>
    <div class="puzzle">
        {puzzle_data.get('grid_html', '<p>No puzzle grid found</p>')}
    </div>
</body>
</html>""")
            print(f"  ✓ Saved HTML fallback: {html_path.name}")
    
    def get_puzzle_filename(self, puzzle_info):
        """
        Generate the PDF filename for a puzzle.

        Args:
            puzzle_info: Dictionary with puzzle information including date_str and difficulty

        Returns:
            Tuple of (pdf_filename, pdf_path)
        """
        date_str = puzzle_info.get('date_str', 'unknown')

        # Parse the date string to get proper format
        try:
            from dateutil import parser as date_parser
            parsed_date = date_parser.parse(date_str, fuzzy=True)
            formatted_date = parsed_date.strftime('%d-%b-%Y')  # e.g., 31-Oct-2025
        except:
            # Fallback if parsing fails
            formatted_date = date_str.replace(' ', '-')

        difficulty = puzzle_info.get('difficulty', 'Unknown')
        pdf_filename = f"{formatted_date} - {difficulty}.pdf"
        pdf_path = self.output_dir / pdf_filename

        return pdf_filename, pdf_path

    def download_single_puzzle(self, puzzle, puzzle_num, total_puzzles, cancel_callback=None, progress_callback=None):
        """
        Download a single puzzle (used by parallel downloader).

        Args:
            puzzle: Puzzle info dictionary
            puzzle_num: Current puzzle number
            total_puzzles: Total number of puzzles
            cancel_callback: Optional function that returns True if download should be cancelled
            progress_callback: Optional function for progress updates

        Returns:
            Tuple of (success, puzzle_name, error_msg)
        """
        # Check for cancellation
        if cancel_callback and cancel_callback():
            return (False, puzzle.get('text', 'Unknown'), 'Cancelled')

        puzzle_name = puzzle['text']
        puzzle_date = puzzle['parsed_date']

        # Check if file already exists BEFORE creating browser instance (optimization!)
        pdf_filename, pdf_path = self.get_puzzle_filename(puzzle)
        if pdf_path.exists():
            if progress_callback:
                progress_callback(puzzle_num, total_puzzles, puzzle_name, "⚡ Skipped (exists)")
            return (True, puzzle_name, None)

        try:
            # Report starting this puzzle
            if progress_callback:
                progress_callback(puzzle_num, total_puzzles, puzzle_name, "Starting...")

            # Create a new browser instance for this thread
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')

            thread_driver = webdriver.Chrome(options=chrome_options)
            thread_wait = WebDriverWait(thread_driver, 10)

            try:
                # Navigate to archive page
                thread_driver.get(self.ARCHIVE_URL)
                thread_wait.until(EC.presence_of_element_located((By.ID, "ai")))

                # Extract puzzle using thread-specific driver
                if progress_callback:
                    progress_callback(puzzle_num, total_puzzles, puzzle_name, "Downloading...")

                # Use thread-specific driver and wait (no swapping needed!)
                puzzle_data = self.extract_puzzle_from_page(
                    puzzle['value'],
                    puzzle,
                    driver=thread_driver,
                    wait=thread_wait
                )

                # Create filename
                filename = f"samurai_sudoku_{puzzle_date.strftime('%Y%m%d')}_{puzzle.get('difficulty', 'unknown').lower()}"

                if progress_callback:
                    progress_callback(puzzle_num, total_puzzles, puzzle_name, "Saving...")

                self.save_puzzle(puzzle_data, filename)

                # Report completion
                if progress_callback:
                    progress_callback(puzzle_num, total_puzzles, puzzle_name, "✓ Complete")

                return (True, puzzle_name, None)

            finally:
                thread_driver.quit()

        except Exception as e:
            error_msg = str(e)
            if progress_callback:
                progress_callback(puzzle_num, total_puzzles, puzzle_name, f"✗ Error: {error_msg}")
            return (False, puzzle_name, error_msg)

    def download_puzzles(self, start_date, end_date, cancel_callback=None, progress_callback=None, max_workers=3):
        """
        Download puzzles for the specified date range.

        Args:
            start_date: Start date (datetime object)
            end_date: End date (datetime object)
            cancel_callback: Optional function that returns True if download should be cancelled
            progress_callback: Optional function(current, total, puzzle_name, step_msg) for progress updates
            max_workers: Number of parallel download threads (default: 3)
        """
        if not progress_callback:
            # Default to printing if no callback provided
            print(f"\nDownloading puzzles from {start_date.date()} to {end_date.date()}")
            print(f"Output directory: {self.output_dir}\n")

        # Get available puzzles from archive
        available_puzzles = self.get_archive_puzzles()
        
        if not available_puzzles:
            if progress_callback:
                progress_callback(0, 0, "ERROR: No puzzles found in archive", "")
            else:
                print("\n✗ ERROR: No puzzles found in archive.")
                print("The website structure may have changed.")
            return

        # Parse dates from puzzle text and filter by date range
        puzzles_to_download = []

        for puzzle in available_puzzles:
            date_str = puzzle.get('date_str')
            if not date_str:
                continue

            try:
                # Parse the date string (e.g., "31st October 2025")
                puzzle_date = date_parser.parse(date_str, fuzzy=True)

                # Check if puzzle date is within range
                if start_date.date() <= puzzle_date.date() <= end_date.date():
                    puzzle['parsed_date'] = puzzle_date
                    puzzles_to_download.append(puzzle)
            except Exception as e:
                if not progress_callback:
                    print(f"  ⚠ Could not parse date '{date_str}': {e}")
                continue

        if not progress_callback:
            print(f"Found {len(puzzles_to_download)} puzzles in date range\n")

        if not puzzles_to_download:
            if progress_callback:
                progress_callback(0, 0, "No puzzles in date range", "")
            else:
                print("✗ No puzzles found in the specified date range.")
                print(f"Available date range: {available_puzzles[0].get('date_str')} to {available_puzzles[-1].get('date_str')}")
            return
        
        # Sort by date
        puzzles_to_download.sort(key=lambda x: x['parsed_date'])

        # Download puzzles in parallel
        total_puzzles = len(puzzles_to_download)
        completed_count = 0
        success_count = 0
        progress_lock = Lock()

        # Thread-safe progress wrapper
        def thread_safe_progress(current, total, puzzle_name, step_msg):
            if progress_callback:
                progress_callback(current, total, puzzle_name, step_msg)

        if not progress_callback:
            print(f"Downloading {total_puzzles} puzzles using {max_workers} parallel workers...")
            print()

        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            future_to_puzzle = {}
            for idx, puzzle in enumerate(puzzles_to_download, 1):
                future = executor.submit(
                    self.download_single_puzzle,
                    puzzle,
                    idx,
                    total_puzzles,
                    cancel_callback,
                    thread_safe_progress
                )
                future_to_puzzle[future] = (idx, puzzle)

            # Process completed downloads as they finish
            for future in as_completed(future_to_puzzle):
                if cancel_callback and cancel_callback():
                    if not progress_callback:
                        print("\n⚠ Download cancelled by user")
                    break

                idx, puzzle = future_to_puzzle[future]
                try:
                    success, puzzle_name, error_msg = future.result()

                    with progress_lock:
                        completed_count += 1
                        if success:
                            success_count += 1

                        if not progress_callback:
                            status = "✓" if success else "✗"
                            msg = f"[{completed_count}/{total_puzzles}] {status} {puzzle_name}"
                            if error_msg:
                                msg += f" - {error_msg}"
                            print(msg)

                except Exception as e:
                    with progress_lock:
                        completed_count += 1
                    if not progress_callback:
                        print(f"[{completed_count}/{total_puzzles}] ✗ {puzzle.get('text', 'Unknown')} - {str(e)}")

        if not progress_callback:
            print()
            print(f"{'='*60}")
            print(f"✓ Successfully downloaded {success_count} of {total_puzzles} puzzles")
            ##print(f"✓ Files saved to: {self.output_dir.absolute()}")
            print(f"{'='*60}")


class SettingsManager:
    """Manages application settings with persistent storage"""

    def __init__(self):
        self.config_dir = Path.home() / '.samurai_sudoku_downloader'
        self.config_file = self.config_dir / 'settings.json'
        self.settings = self.load_settings()

    def load_settings(self):
        """Load settings from JSON file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load settings: {e}")
                return {}
        return {}

    def save_settings(self):
        """Save settings to JSON file"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save settings: {e}")

    def get(self, key, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Set a setting value and save"""
        self.settings[key] = value
        self.save_settings()


class SamuraiSudokuGUI:
    """GUI for the Samurai Sudoku Downloader"""

    # Premium modern dark theme color scheme
    COLORS = {
        'bg_primary': '#0d1117',        # Deep dark background
        'bg_secondary': '#161b22',      # Elevated surfaces
        'bg_tertiary': '#1c2128',       # Card backgrounds
        'bg_hover': '#2d333b',          # Hover states
        'bg_input': '#0d1117',          # Input fields
        'accent': '#58a6ff',            # Bright blue accent
        'accent_hover': '#1f6feb',      # Deeper blue on hover
        'accent_dark': '#1158c7',       # Dark blue for pressed state
        'text_primary': '#f0f6fc',      # Crisp white text
        'text_secondary': '#8b949e',    # Muted gray text
        'text_dim': '#6e7681',          # Dimmed text
        'success': '#3fb950',           # Bright green
        'error': '#f85149',             # Vibrant red
        'error_hover': '#da3633',       # Deeper red
        'warning': '#f59e0b',           # Amber warning
        'border': '#30363d',            # Subtle borders
        'border_bright': '#484f58',     # Brighter borders
        'shadow': 'rgba(0, 0, 0, 0.3)'  # Elevated shadows
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Samurai Sudoku Downloader")
        self.root.geometry("750x650")
        self.root.resizable(True, True)
        self.root.minsize(750, 650)

        self.settings = SettingsManager()
        self.downloader = None
        self.download_thread = None
        self.cancel_download = False

        self.apply_modern_theme()
        self.setup_ui()
        self.check_first_run()

    def apply_modern_theme(self):
        """Apply premium modern dark theme styling to the application"""
        style = ttk.Style()

        # Configure root window
        self.root.configure(bg=self.COLORS['bg_primary'])

        # Configure ttk styles
        style.theme_use('clam')

        # Configure default styles
        style.configure('.',
                       background=self.COLORS['bg_primary'],
                       foreground=self.COLORS['text_primary'],
                       bordercolor=self.COLORS['border'],
                       darkcolor=self.COLORS['bg_secondary'],
                       lightcolor=self.COLORS['bg_tertiary'],
                       troughcolor=self.COLORS['bg_secondary'],
                       focuscolor=self.COLORS['accent'],
                       selectbackground=self.COLORS['accent'],
                       selectforeground=self.COLORS['text_primary'],
                       fieldbackground=self.COLORS['bg_tertiary'],
                       font=('Inter', 10))

        # Frame styles
        style.configure('TFrame',
                       background=self.COLORS['bg_primary'])

        # Label styles
        style.configure('TLabel',
                       background=self.COLORS['bg_primary'],
                       foreground=self.COLORS['text_primary'],
                       font=('Inter', 11))

        style.configure('Title.TLabel',
                       background=self.COLORS['bg_primary'],
                       foreground=self.COLORS['text_primary'],
                       font=('Inter', 28, 'bold'))

        # LabelFrame styles (modern elevated cards)
        style.configure('TLabelframe',
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['text_primary'],
                       bordercolor=self.COLORS['border_bright'],
                       relief='flat',
                       borderwidth=1)

        style.configure('TLabelframe.Label',
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['accent'],
                       font=('Inter', 11, 'bold'))

        # Entry styles (sleek dark input fields)
        style.configure('TEntry',
                       fieldbackground=self.COLORS['bg_input'],
                       foreground=self.COLORS['text_primary'],
                       bordercolor=self.COLORS['border_bright'],
                       insertcolor=self.COLORS['accent'],
                       relief='flat',
                       borderwidth=1,
                       padding=12,
                       font=('Inter', 11))

        # Button styles (sleek dark buttons with subtle hover)
        style.configure('TButton',
                       background=self.COLORS['bg_tertiary'],
                       foreground=self.COLORS['text_primary'],
                       bordercolor=self.COLORS['border_bright'],
                       focuscolor='',
                       relief='flat',
                       borderwidth=1,
                       padding=(18, 10),
                       font=('Inter', 10, 'bold'))

        style.map('TButton',
                 background=[('active', self.COLORS['bg_hover']),
                           ('pressed', self.COLORS['border'])],
                 foreground=[('active', self.COLORS['text_primary'])],
                 bordercolor=[('active', self.COLORS['accent'])])

        # Accent button style (vibrant, modern action button)
        style.configure('Accent.TButton',
                       background=self.COLORS['accent'],
                       foreground='white',
                       bordercolor=self.COLORS['accent'],
                       focuscolor='',
                       relief='flat',
                       borderwidth=0,
                       padding=(28, 14),
                       font=('Inter', 11, 'bold'))

        style.map('Accent.TButton',
                 background=[('active', self.COLORS['accent_hover']),
                           ('pressed', self.COLORS['accent_dark'])],
                 foreground=[('active', 'white')])

        # Cancel button style (prominent destructive action)
        style.configure('Cancel.TButton',
                       background=self.COLORS['error'],
                       foreground='white',
                       bordercolor=self.COLORS['error'],
                       focuscolor='',
                       relief='flat',
                       borderwidth=0,
                       padding=(28, 14),
                       font=('Inter', 11, 'bold'))

        style.map('Cancel.TButton',
                 background=[('active', self.COLORS['error_hover']),
                           ('pressed', '#b91c1c')],
                 foreground=[('active', 'white')])

        # Progressbar style (modern with smooth gradients)
        style.configure('TProgressbar',
                       background=self.COLORS['accent'],
                       troughcolor=self.COLORS['bg_tertiary'],
                       bordercolor=self.COLORS['border'],
                       lightcolor=self.COLORS['accent'],
                       darkcolor=self.COLORS['accent_hover'],
                       thickness=12)

    def setup_ui(self):
        """Set up the user interface"""
        # Main container with generous padding
        main_frame = ttk.Frame(self.root, padding="25")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        title_label = ttk.Label(main_frame, text="Samurai Sudoku Downloader",
                                style='Title.TLabel')
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 25))

        # Date Range Section (elevated card)
        date_frame = ttk.LabelFrame(main_frame, text="  Date Range  ", padding="20")
        date_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))

        # Start Date
        ttk.Label(date_frame, text="Start Date:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.start_date_entry = DateEntry(
            date_frame,
            width=15,
            background=self.COLORS['bg_secondary'],
            foreground=self.COLORS['text_primary'],
            fieldbackground=self.COLORS['bg_secondary'],
            borderwidth=1,
            date_pattern='yyyy-mm-dd',
            font=('Inter', 12),
            # Calendar popup styling
            headersbackground=self.COLORS['accent'],
            headersforeground='white',
            selectbackground=self.COLORS['accent'],
            selectforeground='white',
            normalbackground=self.COLORS['bg_tertiary'],
            normalforeground=self.COLORS['text_primary'],
            weekendbackground=self.COLORS['bg_secondary'],
            weekendforeground=self.COLORS['text_primary'],
            othermonthforeground=self.COLORS['text_secondary'],
            othermonthbackground=self.COLORS['bg_tertiary'],
            othermonthweforeground=self.COLORS['text_secondary'],
            othermonthwebackground=self.COLORS['bg_tertiary']
        )
        self.start_date_entry.grid(row=0, column=1, sticky=tk.W)

        # End Date
        ttk.Label(date_frame, text="End Date:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.end_date_entry = DateEntry(
            date_frame,
            width=15,
            background=self.COLORS['bg_secondary'],
            foreground=self.COLORS['text_primary'],
            fieldbackground=self.COLORS['bg_secondary'],
            borderwidth=1,
            date_pattern='yyyy-mm-dd',
            font=('Inter', 12),
            # Calendar popup styling
            headersbackground=self.COLORS['accent'],
            headersforeground='white',
            selectbackground=self.COLORS['accent'],
            selectforeground='white',
            normalbackground=self.COLORS['bg_tertiary'],
            normalforeground=self.COLORS['text_primary'],
            weekendbackground=self.COLORS['bg_secondary'],
            weekendforeground=self.COLORS['text_primary'],
            othermonthforeground=self.COLORS['text_secondary'],
            othermonthbackground=self.COLORS['bg_tertiary'],
            othermonthweforeground=self.COLORS['text_secondary'],
            othermonthwebackground=self.COLORS['bg_tertiary']
        )
        self.end_date_entry.grid(row=1, column=1, sticky=tk.W, pady=(10, 0))

        # Quick Date Buttons
        quick_frame = ttk.Frame(date_frame)
        quick_frame.grid(row=2, column=0, columnspan=2, pady=(15, 0))

        ttk.Button(quick_frame, text="Today", command=self.set_today, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Button(quick_frame, text="Last 7 Days", command=self.set_last_7_days, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(quick_frame, text="Last 30 Days", command=self.set_last_30_days, width=12).pack(side=tk.LEFT, padx=3)

        # Output Directory Section (elevated card)
        dir_frame = ttk.LabelFrame(main_frame, text="  Output Directory  ", padding="20")
        dir_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))

        self.output_dir_var = tk.StringVar(value=self.settings.get('output_directory', ''))
        output_entry = ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=45)
        output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))

        ttk.Button(dir_frame, text="Browse...", command=self.browse_directory, width=10).grid(row=0, column=1)

        dir_frame.columnconfigure(0, weight=1)

        # Download and Cancel Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(5, 20))

        self.download_btn = ttk.Button(button_frame, text="Download Puzzles",
                                       command=self.start_download, style='Accent.TButton')
        self.download_btn.pack(side=tk.LEFT, padx=8)

        self.cancel_btn = ttk.Button(button_frame, text="Cancel Download",
                                     command=self.cancel_download_process, style='Cancel.TButton')
        self.cancel_btn.pack(side=tk.LEFT, padx=8)
        self.cancel_btn.pack_forget()  # Hide initially

        # Progress Section (elevated card)
        progress_frame = ttk.LabelFrame(main_frame, text="  Progress  ", padding="20")
        progress_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))

        self.progress_var = tk.StringVar(value="Ready to download")
        progress_label = ttk.Label(progress_frame, textvariable=self.progress_var)
        progress_label.pack(anchor=tk.W)

        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', maximum=100)
        self.progress_bar['value'] = 0
        self.progress_bar.pack(fill=tk.X, pady=(5, 10))

        # Log Text Area (modern console-style output with dark theme)
        self.log_text = scrolledtext.ScrolledText(progress_frame, height=10, width=60,
                                                   font=('Consolas', 10),
                                                   bg=self.COLORS['bg_input'],
                                                   fg=self.COLORS['text_primary'],
                                                   insertbackground=self.COLORS['accent'],
                                                   selectbackground=self.COLORS['accent_hover'],
                                                   selectforeground='white',
                                                   borderwidth=1,
                                                   relief='flat',
                                                   highlightthickness=1,
                                                   highlightbackground=self.COLORS['border_bright'],
                                                   highlightcolor=self.COLORS['accent'],
                                                   wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Configure grid weights for proper resizing
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)  # Progress frame should expand
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def check_first_run(self):
        """Check if this is the first run and prompt for output directory"""
        if not self.settings.get('output_directory'):
            messagebox.showinfo(
                "Welcome!",
                "Welcome to Samurai Sudoku Downloader!\n\n"
                "Please select a folder where puzzles will be saved."
            )
            self.browse_directory()

    def browse_directory(self):
        """Open directory browser dialog"""
        current_dir = self.output_dir_var.get() or str(Path.home() / "SamuraiSudokuPuzzles")
        directory = filedialog.askdirectory(
            title="Select Puzzle Output Directory",
            initialdir=current_dir
        )
        if directory:
            self.output_dir_var.set(directory)
            self.settings.set('output_directory', directory)
            self.log(f"Output directory set to: {directory}")

    def set_today(self):
        """Set date range to today only"""
        today = datetime.now()
        self.start_date_entry.set_date(today)
        self.end_date_entry.set_date(today)

    def set_last_7_days(self):
        """Set date range to last 7 days"""
        end = datetime.now()
        start = end - timedelta(days=7)
        self.start_date_entry.set_date(start)
        self.end_date_entry.set_date(end)

    def set_last_30_days(self):
        """Set date range to last 30 days"""
        end = datetime.now()
        start = end - timedelta(days=30)
        self.start_date_entry.set_date(start)
        self.end_date_entry.set_date(end)

    def log(self, message):
        """Add message to log text area"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        # Note: update_idletasks() removed - causes crash on macOS when called from background thread

    def validate_inputs(self):
        """Validate user inputs before starting download"""
        # Validate output directory
        if not self.output_dir_var.get():
            messagebox.showerror("Error", "Please select an output directory")
            return False

        # Validate dates
        try:
            start_date = self.start_date_entry.get_date()
            end_date = self.end_date_entry.get_date()

            if start_date > end_date:
                messagebox.showerror("Error", "Start date must be before or equal to end date")
                return False
        except Exception as e:
            messagebox.showerror("Error", f"Invalid date: {e}")
            return False

        return True

    def start_download(self):
        """Start the download process in a separate thread"""
        if not self.validate_inputs():
            return

        # Prevent multiple downloads
        if self.download_thread and self.download_thread.is_alive():
            messagebox.showwarning("Download in Progress", "A download is already in progress")
            return

        # Clear log
        self.log_text.delete(1.0, tk.END)

        # Reset cancel flag
        self.cancel_download = False

        # Update UI
        self.download_btn.pack_forget()
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
        self.progress_bar['value'] = 0
        self.progress_var.set("Initializing download...")

        # Start download in separate thread
        self.download_thread = threading.Thread(target=self.download_worker, daemon=True)
        self.download_thread.start()

    def cancel_download_process(self):
        """Cancel the ongoing download process"""
        if messagebox.askyesno("Cancel Download", "Are you sure you want to cancel the download?"):
            self.cancel_download = True
            self.log("\n*** CANCELLATION REQUESTED - Stopping download... ***\n")
            self.progress_var.set("Cancelling download...")

    def update_progress(self, current, total, message=""):
        """Update the progress bar and status message"""
        if total > 0:
            percentage = (current / total) * 100
            self.progress_bar['value'] = percentage
        if message:
            self.progress_var.set(message)

    def download_worker(self):
        """Worker function that runs in a separate thread"""
        try:
            # Get dates from DateEntry widgets (returns date objects)
            start_date = datetime.combine(self.start_date_entry.get_date(), datetime.min.time())
            end_date = datetime.combine(self.end_date_entry.get_date(), datetime.min.time())
            output_dir = self.output_dir_var.get()

            self.log("="*60)
            self.log("Samurai Sudoku Downloader")
            self.log("="*60)
            self.log(f"Date Range: {start_date.date()} to {end_date.date()}")
            self.log(f"Output Directory: {output_dir}")
            self.log("Download Mode: 3 parallel workers (fast mode)")
            self.log("")

            # Track completion for progress bar
            completed_puzzles = {'count': 0, 'total': 0}
            progress_lock = Lock()

            # Create thread-safe progress callback
            def progress_callback(current, total, puzzle_name, step_msg=""):
                """Callback for download progress"""
                # Update total if needed
                if total > 0 and completed_puzzles['total'] == 0:
                    completed_puzzles['total'] = total

                # Only update progress bar on completion
                if step_msg.startswith("✓") or step_msg.startswith("⚡"):
                    with progress_lock:
                        completed_puzzles['count'] += 1
                        completed = completed_puzzles['count']
                        total_count = completed_puzzles['total']
                        percentage = (completed / total_count) * 100 if total_count > 0 else 0
                        status = f"Downloaded {completed}/{total_count} ({percentage:.0f}%)"
                        self.root.after(0, lambda: self.update_progress(completed, total_count, status))

                # Simplified log message
                log_msg = f"[{current}/{total}] {puzzle_name}"
                if step_msg:
                    log_msg += f" - {step_msg}"
                self.root.after(0, self.log, log_msg)

            try:
                downloader = SamuraiSudokuDownloader(output_dir, headless=True, verbose=False)
                downloader.download_puzzles(
                    start_date,
                    end_date,
                    cancel_callback=lambda: self.cancel_download,
                    progress_callback=progress_callback,
                    max_workers=3  # Parallel downloads for speed
                )

                if self.cancel_download:
                    self.root.after(0, lambda: self.progress_var.set("Download cancelled"))
                    self.root.after(0, self.log, "\n*** Download cancelled by user ***")
                    self.root.after(0, lambda: self.progress_bar.__setitem__('value', 0))
                else:
                    self.root.after(0, lambda: self.progress_bar.__setitem__('value', 100))
                    self.root.after(0, lambda: self.progress_var.set("Download complete!"))
                    self.root.after(0, self.log, "\n✓ All downloads completed successfully!")
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Success",
                        f"Puzzles downloaded successfully!\n\nSaved to:\n{output_dir}"
                    ))
            finally:
                pass

        except Exception as e:
            error_msg = f"Error during download: {str(e)}"
            self.root.after(0, self.log, f"\n{error_msg}")
            self.root.after(0, lambda: messagebox.showerror("Download Error", error_msg))
            self.root.after(0, lambda: self.progress_bar.__setitem__('value', 0))
        finally:
            # Re-enable download button
            self.root.after(0, self.restore_download_button)
            if not self.cancel_download:
                self.root.after(0, lambda: self.progress_var.set("Ready to download"))

    def restore_download_button(self):
        """Restore the download button and hide cancel button"""
        self.cancel_btn.pack_forget()
        self.download_btn.pack(side=tk.LEFT, padx=5)


def parse_date(date_string):
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_string, '%Y-%m-%d')
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_string}. Use YYYY-MM-DD")


def interactive_mode():
    """Run in interactive mode - prompts user for input"""
    print("\n" + "="*29)
    print("  Samurai Sudoku Downloader  ")
    print("="*29 + "\n")

    # Get output directory
    default_output = str(Path.home() / "Downloads" / "SamuraiSudoku")
    print(f"Output Directory")
    print(f"  (Press Enter for default: {default_output})")
    output_dir = input("  Path: ").strip()
    if not output_dir:
        output_dir = default_output
    print(f"  ✓ Using: {output_dir}\n")

    # Get start date
    default_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    while True:
        print(f"Start Date (YYYY-MM-DD)")
        print(f"  (Press Enter for default: {default_start})")
        start_input = input("  Date: ").strip()
        if not start_input:
            start_input = default_start
        try:
            start_date = datetime.strptime(start_input, '%Y-%m-%d')
            print(f"  ✓ Start date: {start_date.strftime('%Y-%m-%d')}\n")
            break
        except ValueError:
            print(f"  ✗ Invalid date format. Please use YYYY-MM-DD\n")

    # Get end date
    default_end = datetime.now().strftime('%Y-%m-%d')
    while True:
        print(f"End Date (YYYY-MM-DD)")
        print(f"  (Press Enter for default: {default_end})")
        end_input = input("  Date: ").strip()
        if not end_input:
            end_input = default_end
        try:
            end_date = datetime.strptime(end_input, '%Y-%m-%d')
            if end_date < start_date:
                print(f"  ✗ End date must be after start date\n")
                continue
            print(f"  ✓ End date: {end_date.strftime('%Y-%m-%d')}\n")
            break
        except ValueError:
            print(f"  ✗ Invalid date format. Please use YYYY-MM-DD\n")

    # Use 10 parallel workers by default
    workers = 10

    # Confirm and start
    print("="*60)
    print("Summary:")
    print(f"  Output:  {output_dir}")
    print(f"  Dates:   {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"  Workers: {workers}")
    print("="*60)
    print("\nPress Enter to start download (Ctrl+C to cancel)...")
    input()

    # Run download
    try:
        downloader = SamuraiSudokuDownloader(
            output_dir=output_dir,
            headless=True
        )
        downloader.download_puzzles(
            start_date,
            end_date,
            max_workers=workers
        )
    except KeyboardInterrupt:
        print("\n\n⚠ Download cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point - launches GUI by default or CLI if arguments provided"""
    # Check if command-line arguments were provided
    if len(sys.argv) > 1:
        # Run in CLI mode
        parser = argparse.ArgumentParser(
            description='Download Samurai Sudoku puzzles from samurai-sudoku.com',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s --start 2024-01-01 --end 2024-01-31 --output ./puzzles
  %(prog)s -s 2024-10-01 -e 2024-10-07 -o ./october_puzzles --visible
            """
        )

        parser.add_argument(
            '-s', '--start',
            type=parse_date,
            required=True,
            help='Start date in YYYY-MM-DD format'
        )

        parser.add_argument(
            '-e', '--end',
            type=parse_date,
            required=True,
            help='End date in YYYY-MM-DD format'
        )

        parser.add_argument(
            '-o', '--output',
            type=str,
            required=True,
            help='Output directory path for downloaded puzzles'
        )

        parser.add_argument(
            '--visible',
            action='store_true',
            help='Run browser in visible mode (not headless)'
        )

        parser.add_argument(
            '-w', '--workers',
            type=int,
            default=3,
            help='Number of parallel download workers (default: 3, recommended: 2-5)'
        )

        args = parser.parse_args()

        # Validate date range
        if args.start > args.end:
            print("ERROR: Start date must be before or equal to end date")
            sys.exit(1)

        # Create downloader and run
        try:
            downloader = SamuraiSudokuDownloader(
                output_dir=args.output,
                headless=not args.visible
            )
            downloader.download_puzzles(
                args.start,
                args.end,
                max_workers=args.workers
            )
        except KeyboardInterrupt:
            print("\n\nDownload interrupted by user")
            sys.exit(0)
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        # Run in interactive mode
        interactive_mode()


if __name__ == '__main__':
    main()