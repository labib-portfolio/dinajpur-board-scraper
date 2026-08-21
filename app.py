import json
import os
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from engine.captcha_solver import NumericalCaptchaSolver
from engine.scraper_engine import AutoFormScraper
from mock_server import mock_app

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="Auto Scraper & Numerical CAPTCHA Solver")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Mount mock target portal for local demonstration
app.mount("/mock", mock_app)

templates = Jinja2Templates(directory=TEMPLATES_DIR)


class SingleScrapeRequest(BaseModel):
    url: str
    input_fields: Dict[str, Any] = {}
    captcha_input_name: Optional[str] = None
    captcha_selector: Optional[str] = None
    button_selector: Optional[str] = None
    form_selector: Optional[str] = None
    method: Optional[str] = None
    output_file: Optional[str] = "output.json"
    include_html: Optional[bool] = False


class BatchScrapeRequest(BaseModel):
    url: str
    items: List[Dict[str, Any]]
    base_fields: Optional[Dict[str, Any]] = {}
    captcha_input_name: Optional[str] = None
    captcha_selector: Optional[str] = None
    button_selector: Optional[str] = None
    form_selector: Optional[str] = None
    method: Optional[str] = None
    delay_seconds: Optional[float] = 1.0
    output_file: Optional[str] = "batch_results.json"
    include_html: Optional[bool] = False


class CaptchaTestRequest(BaseModel):
    text: str


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serve the main web UI dashboard."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/preview", response_class=HTMLResponse)
@app.get("/monitor", response_class=HTMLResponse)
async def serve_preview_dashboard(request: Request):
    """Serve the dedicated live monitor & student preview dashboard."""
    return templates.TemplateResponse(request=request, name="preview.html")


@app.post("/api/scrape")
def execute_single_scrape(payload: SingleScrapeRequest):
    """API endpoint for single-record form scraping."""
    scraper = AutoFormScraper()
    output_path = os.path.join(BASE_DIR, payload.output_file) if payload.output_file else None

    result = scraper.scrape(
        url=payload.url,
        input_fields=payload.input_fields,
        captcha_selector=payload.captcha_selector,
        captcha_input_name=payload.captcha_input_name,
        button_selector=payload.button_selector,
        form_selector=payload.form_selector,
        method=payload.method,
        output_file=output_path,
        include_html=payload.include_html or False
    )

    return JSONResponse(content=result)


@app.post("/api/batch-scrape")
def execute_batch_scrape(payload: BatchScrapeRequest):
    """API endpoint for batch-scraping a list of records synchronously."""
    scraper = AutoFormScraper()
    output_path = os.path.join(BASE_DIR, payload.output_file) if payload.output_file else None

    batch_result = scraper.batch_scrape(
        url=payload.url,
        items_list=payload.items,
        base_fields=payload.base_fields or {},
        captcha_selector=payload.captcha_selector,
        captcha_input_name=payload.captcha_input_name,
        button_selector=payload.button_selector,
        form_selector=payload.form_selector,
        method=payload.method,
        delay_seconds=payload.delay_seconds if payload.delay_seconds is not None else 1.0,
        output_file=output_path,
        include_html=payload.include_html or False
    )

    return JSONResponse(content=batch_result)


@app.post("/api/batch-scrape-stream")
def execute_batch_scrape_stream(payload: BatchScrapeRequest):
    """Streaming API endpoint (Server-Sent Events) providing live progress for each scraped record."""
    scraper = AutoFormScraper()

    def event_stream():
        for event in scraper.batch_scrape_stream(
            url=payload.url,
            items_list=payload.items,
            base_fields=payload.base_fields or {},
            captcha_selector=payload.captcha_selector,
            captcha_input_name=payload.captcha_input_name,
            button_selector=payload.button_selector,
            form_selector=payload.form_selector,
            method=payload.method,
            delay_seconds=payload.delay_seconds if payload.delay_seconds is not None else 1.0,
            include_html=payload.include_html or False
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/webhook/stream-record")
def receive_stream_record(record: dict):
    """Webhook receiver for live distributed runners to stream records in real time."""
    output_path = "scraped_results_all.json"
    try:
        data = {"summary": {"total_rolls_in_file": 3112, "scraped_so_far": 0, "total_success": 0, "total_failed": 0}, "records": []}
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        roll = record.get("roll_no")
        existing_rolls = {r.get("roll_no") for r in data.get("records", [])}
        if roll not in existing_rolls:
            record["index"] = len(data.get("records", [])) + 1
            data["records"].append(record)
            succ = sum(1 for r in data["records"] if r.get("success"))
            data["summary"]["scraped_so_far"] = len(data["records"])
            data["summary"]["total_success"] = succ
            data["summary"]["total_failed"] = len(data["records"]) - succ
            data["summary"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        return {"status": "ok", "total_records": len(data.get("records", []))}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/live-status")
def get_live_status():
    """Returns the latest live progress summary and all records from scraped_results_all.json."""
    output_path = "scraped_results_all.json"
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}
    return {"summary": {"total_rolls_in_file": 3223, "scraped_so_far": 0, "total_success": 0, "total_failed": 0}, "records": []}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Auto Scraper Dashboard on http://127.0.0.1:8000 ...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
