#!/usr/bin/env python3
"""Optional Chromium export of the exact SVG engineering diagrams."""
import argparse
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = [
    'prototype/output/map.svg',
    'prototype/output/port-detail.svg',
    'experiments/seed-study/output/six-seeds.svg',
    'experiments/seed-study/output/all-20-seeds.svg',
    'experiments/seed-study/output/recommended-60-atlas.svg',
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='*', help='SVG paths, relative to the repository root or absolute')
    parser.add_argument('--browser-executable', help='Optional installed Chromium executable')
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        options = dict(headless=True, args=['--disable-dev-shm-usage'])
        if args.browser_executable:
            options['executable_path'] = args.browser_executable
        browser = playwright.chromium.launch(**options)
        try:
            page = browser.new_page()
            for name in args.files or DEFAULTS:
                path = ROOT / name
                source = path.read_text()
                xml = ET.fromstring(source)
                width = math.ceil(float(xml.attrib['width']))
                height = math.ceil(float(xml.attrib['height']))
                page.set_viewport_size(dict(width=width, height=min(height, 3000)))
                page.set_content('<!doctype html><meta charset="utf-8"><style>html,body{margin:0}svg{display:block}</style>' + source, wait_until='domcontentloaded')
                page.evaluate('document.fonts.ready')
                page.screenshot(path=str(path.with_suffix('.png')), full_page=True)
                print(path.with_suffix('.png'))
        finally:
            browser.close()

if __name__ == '__main__':
    main()
