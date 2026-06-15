#!/usr/bin/env python3
"""Capture full-page screenshots for each demo beat (Playwright)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "artifacts" / "demo" / "screenshots"
DEMO_CSS = ROOT / ".clipwise" / "prepare" / "demo.css"

BEATS = [
    ("01_landing", None),
    ("02_murder_board", lambda p: p.locator("#tab-gallery").click()),
    ("03_gallery_polaroids", lambda p: p.locator("#gallery-grid").scroll_into_view_if_needed()),
    ("04_archivist_overlay", "_archivist"),
    ("05_evidence_cabinet", "_cabinet"),
    ("06_lead_followed", "_lead"),
    ("07_artifact_open", "_artifact"),
    ("08_search", "_search"),
    ("09_deduction", "_deduction"),
    ("10_reveal", "_reveal"),
    ("11_back_desk", lambda p: p.locator("#btn-back-desk").click()),
    ("12_case_files", lambda p: p.locator("#tab-featured").click()),
    ("13_hart_notice", "_hart"),
    ("14_hart_reveal", "_hart_reveal"),
]


def ensure_server() -> None:
    import urllib.request

    try:
        urllib.request.urlopen("http://127.0.0.1:7860/", timeout=2)
        return
    except Exception:
        pass
    env = {**subprocess.os.environ, "ARCHIVE_DETECTIVE_USE_CACHE": "1", "ARCHIVE_DETECTIVE_DEMO_PACER": "22"}
    subprocess.Popen(
        ["uv", "run", "python", "main.py"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(45):
        try:
            urllib.request.urlopen("http://127.0.0.1:7860/", timeout=2)
            time.sleep(2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("server not up on :7860")


def run_flow(page) -> None:
    page.goto("http://127.0.0.1:7860/", wait_until="networkidle")
    if DEMO_CSS.is_file():
        page.add_style_tag(content=DEMO_CSS.read_text(encoding="utf-8"))
    page.wait_for_function("document.querySelectorAll('.gallery-card').length > 0", timeout=60000)
    page.wait_for_timeout(800)

    state = {"step": 0}

    def snap(name: str) -> None:
        path = OUT / f"{name}.png"
        page.screenshot(path=str(path), full_page=True)
        print(f"  {path.name}")

    snap("01_landing")
    page.locator("#model-banner").scroll_into_view_if_needed()
    time.sleep(0.4)
    snap("02_model_banner")
    page.locator("#gallery-grid").scroll_into_view_if_needed()
    time.sleep(0.4)
    snap("03_gallery_polaroids")

    page.locator(".gallery-card").nth(1).click(force=True, timeout=60000)
    page.wait_for_function(
        "document.getElementById('archivist-overlay') && !document.getElementById('archivist-overlay').hidden",
        timeout=30000,
    )
    time.sleep(0.6)
    snap("04_archivist_overlay")

    page.wait_for_function(
        "document.getElementById('cabinet-layout') && !document.getElementById('cabinet-layout').hidden",
        timeout=180000,
    )
    time.sleep(0.8)
    snap("05_evidence_cabinet")

    page.locator("#lead-buttons button").first.click()
    time.sleep(0.8)
    snap("06_lead_followed")

    page.locator('button.artifact-card:not(.locked):has(img)').first.click()
    page.wait_for_function(
        "(() => { const img = document.getElementById('artifact-img'); return img && !img.hidden && img.complete && img.naturalWidth > 0; })()",
        timeout=15000,
    )
    time.sleep(0.8)
    snap("07_artifact_open")

    page.locator("#search-input").fill("organist")
    page.locator("#search-form button[type='submit']").click()
    time.sleep(0.8)
    snap("08_search")

    page.locator("#deduction-form").scroll_into_view_if_needed()
    page.locator("#artifact-frame").scroll_into_view_if_needed()
    time.sleep(0.3)
    page.locator("#deduction-form .option-pill").first.click()
    time.sleep(0.4)
    snap("09_deduction")

    page.locator("#btn-reveal").click()
    time.sleep(1.0)
    snap("10_reveal")

    page.locator("#btn-back-desk").click()
    time.sleep(0.8)
    snap("11_back_desk")

    page.locator("#tab-featured").click()
    time.sleep(0.5)
    snap("12_case_files")

    page.locator(".hero-case-card").first.click()
    page.wait_for_function(
        "document.getElementById('cabinet-layout') && !document.getElementById('cabinet-layout').hidden",
        timeout=30000,
    )
    time.sleep(0.6)
    snap("13_hart_notice")

    page.locator("#lead-buttons button").first.click()
    page.locator("#deduction-form .option-pill").first.click()
    page.locator("#btn-reveal").click()
    time.sleep(1.0)
    snap("14_hart_reveal")


def main() -> None:
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    ensure_server()
    print(f"Capturing to {OUT}/")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        run_flow(page)
        browser.close()
    print("Done.")


if __name__ == "__main__":
    main()
