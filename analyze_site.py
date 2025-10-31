#!/usr/bin/env python3
"""Quick script to analyze the samurai-sudoku.com site structure"""

import requests
from bs4 import BeautifulSoup
import json

url = "https://www.samurai-sudoku.com/classic/"

print("Fetching page...")
response = requests.get(url, timeout=10)
print(f"Status: {response.status_code}\n")

soup = BeautifulSoup(response.content, 'html.parser')

# Find the dropdown
print("="*60)
print("DROPDOWN ANALYSIS")
print("="*60)
dropdown = soup.find('select', {'id': 'ai'})
if dropdown:
    options = dropdown.find_all('option')
    print(f"Found dropdown with {len(options)} options\n")

    # Show first few options with their values
    print("Sample options:")
    for i, opt in enumerate(options[:3]):
        print(f"  {i+1}. Text: {opt.get_text()}")
        print(f"     Value: {opt.get('value')}")
        print()

# Look for JavaScript that handles the dropdown
print("="*60)
print("JAVASCRIPT ANALYSIS")
print("="*60)
scripts = soup.find_all('script')
print(f"Found {len(scripts)} script tags")

for i, script in enumerate(scripts):
    if script.string and ('ai' in script.string or 'archive' in script.string.lower()):
        print(f"\nScript {i+1} (contains 'ai' or 'archive'):")
        print(script.string[:500])
        print("...")

# Look for any PDF links or file patterns
print("\n" + "="*60)
print("LOOKING FOR PDF/FILE PATTERNS")
print("="*60)
all_links = soup.find_all('a', href=True)
pdf_links = [a['href'] for a in all_links if '.pdf' in a['href'].lower()]
print(f"Direct PDF links found: {len(pdf_links)}")
if pdf_links:
    for link in pdf_links[:5]:
        print(f"  - {link}")

# Look for form actions or data endpoints
print("\n" + "="*60)
print("FORMS AND ENDPOINTS")
print("="*60)
forms = soup.find_all('form')
print(f"Forms found: {len(forms)}")
for form in forms:
    print(f"  Action: {form.get('action')}")
    print(f"  Method: {form.get('method')}")

# Check if there's a pattern in URLs
print("\n" + "="*60)
print("URL PATTERN ANALYSIS")
print("="*60)
print(f"Current URL: {url}")
print("Testing if puzzles have direct URLs...")

# Try some common patterns
test_patterns = [
    "https://www.samurai-sudoku.com/classic/puzzle.php?id=1",
    "https://www.samurai-sudoku.com/classic/print.php?id=1",
    "https://www.samurai-sudoku.com/print/1",
    "https://www.samurai-sudoku.com/classic/1",
]

for test_url in test_patterns:
    try:
        r = requests.head(test_url, timeout=5)
        print(f"  {test_url}: {r.status_code}")
    except:
        print(f"  {test_url}: Failed")

print("\nDone!")
