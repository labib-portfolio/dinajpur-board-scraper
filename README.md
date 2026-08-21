# ⚡ Auto Scraper Pro — Single & Batch Multi-Record Scraper

An automated web scraper with an interactive web UI dashboard and command-line interface. It is designed to navigate to any web form, fill arbitrary input fields, automatically detect and solve arithmetic / numerical CAPTCHAs (e.g. `2 + 7`, `15 - 4`, `3 * 8`) and Gateway Human Checks, submit the form, and extract single or multi-record batch results into structured JSON format.

---

## 🌟 Key Features

1. **Interactive Web Dashboard (`http://127.0.0.1:8000`)**:
   - **🎯 Single Record Mode**: Scrape an individual record or query.
   - **🚀 Multi-Record Batch Mode**:
     - **Paste List / CSV**: Paste a list of roll numbers or records (one per line, e.g. `roll_no, regi_no`).
     - **Quick Range Generator**: Automatically generate roll number sequences (e.g., from `108420` to `108430`).
     - **Configurable Request Delay**: Set pauses (e.g. `1.0s`) to avoid server rate limiting.
     - **Live Animated Progress Bar**: Real-time progress tracking (`[██████░░░░] 60%`).
     - **Live Batch Results Table**: Populates records in real-time as each student is scraped.
   - **Numerical CAPTCHA Solver**: Parses and solves arithmetic math challenges (`2 + 7 = 9`).
   - **Gateway Human Check Solver**: Automatically bypasses "Find the different symbol" challenges (e.g. on Dinajpur/Dhaka Board portals).
   - **JSON Exporter**: Live formatted JSON display, copy-to-clipboard, and one-click **Download JSON** button.

2. **Core Scraping & CAPTCHA Engine (`engine/`)**:
   - [`NumericalCaptchaSolver`](engine/captcha_solver.py): Safe arithmetic parser handling `+`, `-`, `*`, `/`, written words (`five plus seven`), and natural language queries.
   - [`AutoFormScraper`](engine/scraper_engine.py): Maintains HTTP session state, solves Gateway & Math CAPTCHAs, submits payloads, and parses response pages. Supports single & streaming batch scraping.
   - [`parse_html_to_json`](engine/parser_utils.py): Converts HTML tables, key-value definitions, headings, alerts, and text blocks into structured JSON.

3. **Command Line Interface (CLI)**:
   - Run single scrapes or batch jobs directly from the terminal.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Interactive Web UI
```bash
python run.py
```
Open your browser and navigate to:
- **Web UI Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 🖥️ Using the Web Dashboard

### 🎯 Single Record Mode:
1. Click **"🎓 Load Dinajpur Board Preset"** or enter your target URL.
2. Enter your roll number and registration number.
3. Click **"🚀 Click Button & Scrape All Page Info"**.

### 🚀 Multi-Record Batch Mode:
1. Click the **"🚀 Batch / Multi-Record List"** tab at the top.
2. Paste a list of records in the text box (or use the **Quick Range Generator**):
   ```text
   roll_no, regi_no
   108420, 1817654320
   108421, 1817654321
   108422, 1817654322
   ```
3. Set your delay (default `1.0` seconds).
4. Click **"🚀 Start Batch Scraping"**.
5. Watch the live progress bar and table update in real-time.
6. Click **"📥 Download JSON"** to export the entire dataset.

---

## 💻 Command Line Interface (CLI)

### Batch Scrape via Number Range:
```bash
python cli.py --url "https://results.dinajpurboard.gov.bd/search/student" \
              --range 108420 108425 \
              --range-field roll_no \
              --button-selector "button[name='submit']" \
              --delay 1.0 \
              --out batch_results.json
```

### Batch Scrape via CSV File:
```bash
python cli.py --url "https://results.dinajpurboard.gov.bd/search/student" \
              --batch-file students.csv \
              --button-selector "button[name='submit']" \
              --delay 1.0 \
              --out batch_results.json
```

---

## 🧪 Running Tests

```bash
python -m unittest discover tests
```
All 12 automated unit and integration tests will execute, verifying arithmetic CAPTCHA resolution, HTML-to-JSON parsing, single scraping, batch scraping, and SSE streaming.
