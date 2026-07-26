"""Drive the real UI with Playwright and capture evidence screenshots.

Uses the Chromium that Crawl4AI already installs, so no extra tooling. Everything shown is a
genuine interaction with the running system - the prompts are typed into the real input and
the responses are the model's actual output.

Content is chosen to contain no personal data: the OCR sample is generated here, and the
prompts are generic technical questions.

Requires the backend on :8081.

    venv\\Scripts\\python.exe benchmarks\\capture_screenshots.py
"""

import asyncio
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import async_playwright

from _common import API_BASE, REPO_ROOT, environment

SHOT_DIR = REPO_ROOT / "rework-proof" / "assets" / "screenshots"
UPLOADS = Path(__file__).resolve().parent.parent / "uploads"
VIEWPORT = {"width": 1680, "height": 1000}

manifest = []


def record(name, proves, caption, redaction="No personal data on screen; content is "
                                            "generic technical text generated for this capture."):
    manifest.append({
        "id": name,
        "file": f"{name}.png",
        "proves": proves,
        "caption": caption,
        "redaction_check": redaction,
    })


async def shot(page, name, proves, caption, **kw):
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(SHOT_DIR / f"{name}.png"))
    record(name, proves, caption, **kw)
    print(f"  captured {name}.png")


def make_ocr_sample():
    """A synthetic invoice-style image - no real customer or personal data."""
    try:
        big = ImageFont.truetype("arial.ttf", 34)
        small = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        big = small = ImageFont.load_default()
    img = Image.new("RGB", (900, 460), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 34), "ACME WIDGETS LTD", font=big, fill="black")
    d.text((40, 84), "Invoice No: INV-2026-00841", font=small, fill="black")
    d.text((40, 116), "Date: 26 July 2026", font=small, fill="black")
    d.line((40, 156, 860, 156), fill="black", width=2)
    rows = [
        ("Description", "Qty", "Unit", "Amount"),
        ("Widget assembly, type B", "12", "450.00", "5,400.00"),
        ("Calibration service", "3", "1,200.00", "3,600.00"),
        ("Extended warranty", "1", "5,250.00", "5,250.00"),
    ]
    y = 176
    for desc, qty, unit, amt in rows:
        d.text((40, y), desc, font=small, fill="black")
        d.text((470, y), qty, font=small, fill="black")
        d.text((580, y), unit, font=small, fill="black")
        d.text((740, y), amt, font=small, fill="black")
        y += 42
    d.line((40, y + 6, 860, y + 6), fill="black", width=2)
    d.text((580, y + 24), "Total Due:", font=big, fill="black")
    d.text((740, y + 24), "14,250.00", font=big, fill="black")

    UPLOADS.mkdir(parents=True, exist_ok=True)
    path = UPLOADS / "demo_invoice.png"
    img.save(path)
    return path


async def wait_for_done(page, timeout_ms=240_000):
    """The send button reappears when the stream finishes."""
    await page.wait_for_function(
        "() => document.getElementById('send-btn').style.display !== 'none'",
        timeout=timeout_ms)
    await page.wait_for_timeout(1200)


async def ask(page, prompt):
    await page.fill("#prompt-input", prompt)
    await page.click("#send-btn")


async def main():
    print("=" * 70)
    print("UI screenshot capture")
    print("=" * 70)

    ocr_image = make_ocr_sample()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport=VIEWPORT, device_scale_factor=2)

        print("\n  Opening the UI ...")
        await page.goto(API_BASE, wait_until="networkidle")
        await page.wait_for_timeout(2500)
        await shot(page, "01_ui_overview",
                   "The application loads and renders: three-pane layout, thread library, "
                   "swarm status panel, prompt input.",
                   "AgentForge on first load. Vanilla JS and CSS with no framework and no "
                   "build step - the glassmorphism styling and animated particle background "
                   "are hand-written.")

        # ---- a research query: shows routing, live reasoning, sources
        print("\n  Query 1: web research (this takes ~20s) ...")
        await ask(page, "What is retrieval-augmented generation? Answer in two sentences.")

        # Catch the live reasoning stream mid-flight.
        try:
            await page.wait_for_selector(".thinking-content", timeout=60_000)
            await page.wait_for_timeout(3500)
            await shot(page, "02_live_reasoning_stream",
                       "The model's reasoning is streamed to the UI on a separate SSE channel "
                       "from the answer, and the agent status panel updates per pipeline stage.",
                       "Mid-query. The collapsible panel shows the model's reasoning arriving "
                       "token by token while the right-hand Swarm Status panel tracks the "
                       "pipeline stage. Reasoning and answer travel as distinct SSE event types.")
        except Exception as e:
            print(f"    [warn] reasoning shot missed: {e}")

        await wait_for_done(page)
        await shot(page, "03_answer_with_sources",
                   "A complete grounded answer with source attribution from live web scraping.",
                   "Completed research query. The answer is generated from content scraped "
                   "during this request; each Source card links to a page the system actually "
                   "fetched and indexed, not to the model's training data.")

        # ---- the RAG context modal: shows what the model was actually given
        print("\n  Opening the RAG context modal ...")
        try:
            await page.click("text=Extracted Context", timeout=10_000)
            await page.wait_for_timeout(1200)
            await shot(page, "04_rag_context_inspector",
                       "The exact context passed to the model is inspectable, so an answer can "
                       "be checked against its evidence.",
                       "The retrieved context block. Every chunk that entered the prompt is "
                       "shown with its source, which makes the grounding auditable rather than "
                       "implied.")
        except Exception as e:
            print(f"    [warn] context modal: {e}")

        # ---- OCR upload: shows the VRAM hot-swap path end to end
        print("\n  Query 2: image upload -> OCR hot-swap (this takes ~40s) ...")
        await page.click("#new-chat-btn")
        await page.wait_for_timeout(1200)
        await page.set_input_files("#file-input", str(ocr_image))
        await page.wait_for_timeout(900)
        await shot(page, "05_file_attached",
                   "Upload handling: the file is staged client-side before submission.",
                   "A synthetic invoice staged for upload. Filenames are flattened to a bare "
                   "basename and checked against an extension allowlist server-side before "
                   "anything is written to disk.")

        await ask(page, "Extract all the text from this invoice and tell me the total due.")
        await wait_for_done(page)
        await shot(page, "06_ocr_result",
                   "The vision OCR path: the language model is evicted from VRAM, GLM-OCR runs "
                   "on the GPU, the language model is restored, and the extracted text is used "
                   "to answer.",
                   "Result of the image path. Producing this answer required the full model "
                   "hot-swap measured in evidence/bench_vram.json - two models that cannot "
                   "coexist in 8 GB, swapped in about 12 seconds.")

        # ---- session history
        print("\n  Session library ...")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2500)
        await shot(page, "07_session_library",
                   "Conversations persist in SQLite across restarts and reload with their "
                   "reasoning, sources and context intact.",
                   "The thread library after a reload. Sessions are isolated from one another "
                   "at query time; deleting one now removes its chunks and embeddings as well "
                   "as its messages.")

        await browser.close()

    ocr_image.unlink(missing_ok=True)

    out = SHOT_DIR / "manifest.json"
    out.write_text(json.dumps(
        {"captured": manifest, "environment": environment(),
         "method": "Playwright Chromium at 1680x1000, device_scale_factor=2, driving the real "
                   "UI against the running backend. All content is genuine model output."},
        indent=2, default=str), encoding="utf-8")
    print(f"\n  {len(manifest)} screenshots -> {SHOT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
