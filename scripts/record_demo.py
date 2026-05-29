"""Record a silent video walkthrough of the NANDA Index Explorer demo.

Usage:
    pip install playwright
    python -m playwright install chromium
    python scripts/record_demo.py

The recording is saved to recordings/nanda-demo.webm and is intended
to be imported into a video editor (DaVinci, CapCut, Premiere, etc.)
where you can lay down a voice track over the visuals.

Pacing is deliberately slow so a narrator can speak each section
without rushing. Total length ~2:30 — leave a few seconds of head
and tail for transitions in your editor.

REQUIRES: all 6 NANDA services running on the alt port range
(18000–18020) with the 3 demo agents bootstrapped. The script picks
those defaults up automatically. Override via env vars if you ran
the stack on the default 8000 range.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# ---------- config (override via env vars if needed) ----------
INDEX_URL  = os.environ.get("INDEX_URL",  "http://localhost:18000")
F1_URL     = os.environ.get("FACTS1_URL", "http://localhost:18001")
F2_URL     = os.environ.get("FACTS2_URL", "http://localhost:18002")
A1_URL     = os.environ.get("AGENT1_URL", "http://localhost:18010")
A2_URL     = os.environ.get("AGENT2_URL", "http://localhost:18011")
RES_URL    = os.environ.get("RESOLVER_URL", "http://localhost:18020")

VIDEO_SIZE = {"width": 1400, "height": 900}
OUT_DIR    = Path("recordings")
OUT_DIR.mkdir(exist_ok=True)


def ui_url(path: str = "") -> str:
    overrides = (
        f"?index={INDEX_URL}"
        f"&facts1={F1_URL}"
        f"&facts2={F2_URL}"
        f"&agent1={A1_URL}"
        f"&agent2={A2_URL}"
        f"&resolver={RES_URL}"
    )
    return f"{INDEX_URL}/ui/{path}{overrides}"


def beat(page, seconds: float, label: str = "") -> None:
    """Wait a beat, with optional console label so you can follow along."""
    if label:
        print(f"  [{seconds:5.1f}s] {label}")
    page.wait_for_timeout(int(seconds * 1000))


def main() -> int:
    print(f"INDEX_URL = {INDEX_URL}")
    print(f"Recording to: {OUT_DIR.resolve()}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=120)
        context = browser.new_context(
            viewport=VIDEO_SIZE,
            record_video_dir=str(OUT_DIR),
            record_video_size=VIDEO_SIZE,
        )
        page = context.new_page()

        # ─── 1. Landing (≈ 15 s) ────────────────────────────────────
        print("[1/5] Landing — show the architecture cards")
        page.goto(ui_url(), wait_until="networkidle")
        beat(page, 3.0, "settle on landing")
        page.evaluate("window.scrollTo({top: 350, behavior: 'smooth'})")
        beat(page, 5.0, "scroll to architecture cards")
        page.evaluate("window.scrollTo({top: 700, behavior: 'smooth'})")
        beat(page, 5.0, "scroll to registered agents")

        # ─── 2. Resolve echo agent — full cascade (≈ 40 s) ──────────
        print("[2/5] Resolve echo — cascade animates 5 steps")
        page.evaluate(
            "document.querySelector('[data-action=\"resolve\"][data-agent=\"urn:agent:demo:echo\"]').click()"
        )
        beat(page, 1.0, "click Resolve")
        page.wait_for_selector("text=Trust chain complete", timeout=10_000)
        page.evaluate("document.getElementById('resolutionPanel').scrollIntoView({block:'start'})")
        beat(page, 6.0, "show the 5 verified steps")
        page.evaluate("window.scrollBy(0, 500)")
        beat(page, 8.0, "scroll through AgentAddr JSON")
        page.evaluate("window.scrollBy(0, 500)")
        beat(page, 8.0, "scroll through AgentFacts VC")
        page.evaluate("window.scrollBy(0, 400)")
        beat(page, 5.0, "land on Trust chain complete")

        # ─── 3. Tamper detection (≈ 20 s) ───────────────────────────
        print("[3/5] Tamper demo — MITM rejected")
        page.evaluate("document.getElementById('tamperBtn').scrollIntoView({block:'center'})")
        beat(page, 2.5, "find the Run attack button")
        page.evaluate("document.getElementById('tamperBtn').click()")
        beat(page, 1.0, "click Run attack")
        page.wait_for_selector("text=Client refused the call", timeout=8_000)
        page.evaluate("document.getElementById('tamperResult').scrollIntoView({block:'center'})")
        beat(page, 8.0, "show the diff + REJECTED alert")

        # ─── 4. Adaptive routing (≈ 30 s) ──────────────────────────
        print("[4/5] Adaptive routing — geo dispatch to eu-west")
        page.evaluate("document.getElementById('callAgentSelect').scrollIntoView({block:'center'})")
        beat(page, 2.0, "scroll to Call panel")
        page.evaluate(
            """() => {
                document.getElementById('callAgentSelect').value = 'urn:agent:demo:multiregion';
                document.getElementById('adaptiveToggle').checked = true;
                document.getElementById('regionSelect').value = 'eu-west';
                document.getElementById('callMessage').value = 'bonjour';
            }"""
        )
        beat(page, 2.5, "configure adaptive call (eu-west, 'bonjour')")
        page.evaluate("document.getElementById('callBtn').click()")
        page.wait_for_selector("text=Response from", timeout=12_000)
        page.evaluate("document.getElementById('callResult').scrollIntoView({block:'center'})")
        beat(page, 8.0, "show routing token verified + response")

        # ─── 5. Design & flow page (≈ 60 s) ─────────────────────────
        print("[5/5] Design page — diagrams + standards")
        page.goto(f"{INDEX_URL}/ui/design.html", wait_until="networkidle")
        beat(page, 4.0, "let Mermaid render")
        page.evaluate("window.scrollTo({top: 500, behavior: 'smooth'})")
        beat(page, 10.0, "headline 'book a flight' diagram")
        page.evaluate("window.scrollTo({top: 1100, behavior: 'smooth'})")
        beat(page, 8.0, "signature callouts")
        page.evaluate("window.scrollTo({top: 1700, behavior: 'smooth'})")
        beat(page, 8.0, "standards cards (W3C + IETF)")
        page.evaluate("window.scrollTo({top: 2400, behavior: 'smooth'})")
        beat(page, 6.0, "system architecture diagram")
        page.evaluate("window.scrollTo({top: 3300, behavior: 'smooth'})")
        beat(page, 6.0, "resolution flow + adaptive routing")

        # Tail — gives the editor a clean fade-out point.
        beat(page, 2.0, "end")
        print("\nDone. Closing browser…")

        context.close()  # finalises the .webm
        browser.close()

    # Rename the latest recording to a stable filename.
    recordings = sorted(OUT_DIR.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    if not recordings:
        print("ERROR: no .webm produced. Check that the browser was visible.")
        return 1

    final = OUT_DIR / "nanda-demo.webm"
    if final.exists():
        final.unlink()
    shutil.move(str(recordings[-1]), str(final))
    size_mb = final.stat().st_size / 1024 / 1024
    print(f"\n[OK] Saved: {final.resolve()}")
    print(f"  Size:  {size_mb:.1f} MB")
    print("  Import into your editor and add your voice over it.")
    print("  WebM works directly in DaVinci, CapCut, Premiere, Final Cut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
