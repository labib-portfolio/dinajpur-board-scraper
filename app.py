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


import threading

file_write_lock = threading.Lock()
JSONL_STREAM_FILE = os.path.join(BASE_DIR, "stream_records.jsonl")

@app.post("/api/webhook/stream-record")
def receive_stream_record(record: dict):
    """Webhook receiver for live distributed runners to stream records in real time."""
    output_path = os.path.join(BASE_DIR, "scraped_results_all.json")
    try:
        # 1. Atomic append to JSONL journal for instant reading
        line = json.dumps(record, ensure_ascii=False)
        with open(JSONL_STREAM_FILE, "a", encoding="utf-8") as jf:
            jf.write(line + "\n")

        # 2. Thread-safe update of scraped_results_all.json
        with file_write_lock:
            data = {"summary": {"total_rolls_in_file": 3223, "scraped_so_far": 0, "total_success": 0, "total_failed": 0}, "records": []}
            if os.path.exists(output_path):
                try:
                    with open(output_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    pass
            
            roll = str(record.get("roll_no"))
            existing_rolls = {str(r.get("roll_no")) for r in data.get("records", [])}
            if roll and roll not in existing_rolls:
                record["index"] = len(data.get("records", [])) + 1
                data["records"].append(record)
                succ = sum(1 for r in data["records"] if r.get("success"))
                data["summary"]["scraped_so_far"] = len(data["records"])
                data["summary"]["total_success"] = succ
                data["summary"]["total_failed"] = len(data["records"]) - succ
                data["summary"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Write to temp file and rename atomically
                temp_path = output_path + ".tmp"
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(temp_path, output_path)
                    
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


# ==========================================
# New Student & Board Result Explorer APIs
# ==========================================

import glob
import csv
import io
import requests

@app.get("/api/student/{roll}")
def get_student_result(roll: str):
    """Instant lookup for a single student result across all local district files and live fallback."""
    roll_clean = str(roll).strip()
    if not roll_clean:
        return JSONResponse(content={"success": False, "error": "Please enter a valid roll number."}, status_code=400)

    # 1. Check all district upazilla JSON files
    results_root = os.path.join(BASE_DIR, "results")
    district_files = glob.glob(os.path.join(results_root, "**", "results_upazilla_*.json"), recursive=True)
    for fpath in district_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                d = json.load(f)
                for rec in d.get("records", []):
                    if str(rec.get("roll_no")) == roll_clean:
                        return {"success": True, "cached": True, "source": fpath, "data": rec}
        except Exception:
            pass

    # 2. Check master scraped_results_all.json
    master_file = os.path.join(BASE_DIR, "scraped_results_all.json")
    if os.path.exists(master_file):
        try:
            with open(master_file, 'r', encoding='utf-8') as f:
                d = json.load(f)
                for rec in d.get("records", []):
                    if str(rec.get("roll_no")) == roll_clean:
                        return {"success": True, "cached": True, "source": "master", "data": rec}
        except Exception:
            pass

    # 3. Live fallback to official Dinajpur Board endpoint
    try:
        from engine.fast_student_scraper import fetch_single_student
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        res = fetch_single_student(session, roll_clean)
        if res and res.get("success"):
            return {"success": True, "cached": False, "source": "live_board", "data": res}
    except Exception as e:
        return {"success": False, "error": f"Error fetching live roll: {str(e)}"}

    return {"success": False, "error": f"Roll {roll_clean} not found on the board or in local database."}


@app.get("/api/board/summary")
def get_board_summary():
    """Aggregates all scraped district and upazilla JSON files into a board-wide statistical summary."""
    results_root = os.path.join(BASE_DIR, "results")
    district_files = glob.glob(os.path.join(results_root, "**", "results_upazilla_*.json"), recursive=True)
    
    total_students = 0
    total_passed = 0
    total_failed = 0
    total_gpa5 = 0
    total_schools = set()
    districts_map = {}

    for fpath in sorted(district_files):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                d = json.load(f)
            
            dist = d.get("district", "UNKNOWN").upper()
            upz = d.get("upazila", "UNKNOWN").upper()
            recs = d.get("records", [])
            summary = d.get("summary", {})
            
            passed = sum(1 for r in recs if "GPA" in str(r.get("result", "")))
            failed = len(recs) - passed
            gpa5 = sum(1 for r in recs if "5.00" in str(r.get("result", "")))
            
            total_students += len(recs)
            total_passed += passed
            total_failed += failed
            total_gpa5 += gpa5
            
            for r in recs:
                if r.get("institute"):
                    total_schools.add(r.get("institute"))
            
            slug = os.path.basename(fpath).replace("results_upazilla_", "").replace(".json", "")
            
            if dist not in districts_map:
                districts_map[dist] = {
                    "district": dist,
                    "total_records": 0,
                    "total_passed": 0,
                    "total_failed": 0,
                    "total_gpa5": 0,
                    "upazillas": []
                }
            
            districts_map[dist]["total_records"] += len(recs)
            districts_map[dist]["total_passed"] += passed
            districts_map[dist]["total_failed"] += failed
            districts_map[dist]["total_gpa5"] += gpa5
            
            districts_map[dist]["upazillas"].append({
                "name": upz,
                "slug": slug,
                "file_name": os.path.basename(fpath),
                "total_records": len(recs),
                "total_passed": passed,
                "total_failed": failed,
                "total_gpa5": gpa5,
                "institutions_count": summary.get("institutions_count", len(summary.get("scraped_eiins", []))),
                "pass_rate": round(100.0 * passed / max(1, len(recs)), 1),
                "last_updated": summary.get("last_updated", "")
            })
        except Exception:
            pass

    pass_rate = round(100.0 * total_passed / max(1, total_students), 1)

    return {
        "board": "DINAJPUR",
        "exam": "SSC 2026",
        "total_students": total_students,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_gpa5": total_gpa5,
        "pass_rate": pass_rate,
        "total_institutions": len(total_schools),
        "total_upazillas_scraped": sum(len(d["upazillas"]) for d in districts_map.values()),
        "districts": districts_map
    }


@app.get("/api/board/upazilla/{district}/{upazilla_slug}")
def get_upazilla_detail(district: str, upazilla_slug: str):
    """Retrieves full student dataset and summary for a specific Upazilla."""
    results_root = os.path.join(BASE_DIR, "results")
    slug_clean = upazilla_slug.lower().replace("results_upazilla_", "").replace(".json", "")
    fpath = os.path.join(results_root, district.upper(), f"results_upazilla_{slug_clean}.json")
    if not os.path.exists(fpath):
        files = glob.glob(os.path.join(results_root, "**", f"results_upazilla_{slug_clean}.json"), recursive=True)
        if files:
            fpath = files[0]
        else:
            return JSONResponse(content={"error": f"Upazilla {upazilla_slug} in district {district} not found."}, status_code=404)

    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/board/export/{district}/{upazilla_slug}/csv")
def export_upazilla_csv(district: str, upazilla_slug: str):
    """Exports and streams a clean CSV spreadsheet of the specified Upazilla results."""
    results_root = os.path.join(BASE_DIR, "results")
    slug_clean = upazilla_slug.lower().replace("results_upazilla_", "").replace(".json", "")
    fpath = os.path.join(results_root, district.upper(), f"results_upazilla_{slug_clean}.json")
    if not os.path.exists(fpath):
        files = glob.glob(os.path.join(results_root, "**", f"results_upazilla_{slug_clean}.json"), recursive=True)
        if files:
            fpath = files[0]
        else:
            return JSONResponse(content={"error": "File not found"}, status_code=404)

    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        records = data.get("records", [])
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["#", "Roll No", "Student Name", "Father's Name", "Mother's Name", "Institute", "Group", "Result/GPA", "Total Marks", "District", "Upazila"])
        
        for idx, r in enumerate(records, 1):
            writer.writerow([
                idx,
                r.get("roll_no", ""),
                r.get("student_name", ""),
                r.get("father_name", ""),
                r.get("mother_name", ""),
                r.get("institute", ""),
                r.get("group", ""),
                r.get("result", ""),
                r.get("total_marks", ""),
                r.get("district", district),
                r.get("upazila", data.get("upazila", ""))
            ])
        
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=results_{district}_{upazilla_slug}.csv"}
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Dinajpur Board Result Portal on http://127.0.0.1:8000 ...")
    uvicorn.run(app, host="127.0.0.1", port=8000)

