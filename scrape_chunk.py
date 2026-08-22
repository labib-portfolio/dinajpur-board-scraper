"""
Chunk Scraper Runner for GitHub Actions Matrix or Distributed Node
"""

import sys
import os
import time
import json
import argparse
import logging
from typing import Optional, List, Dict, Any
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from engine.scraper_engine import AutoFormScraper

def run_chunk(chunk_index: int, total_chunks: int, rolls_file: str, output_file: str, delay: float = 3.2, webhook_url: Optional[str] = None):
    with open(rolls_file, 'r', encoding='utf-8') as f:
        rolls = json.load(f)

    # Standardize list
    roll_list = []
    for item in rolls:
        if isinstance(item, (int, str)):
            roll_list.append(str(item).strip())
        elif isinstance(item, dict):
            r = item.get("roll_no") or item.get("roll") or item.get("id")
            if r:
                roll_list.append(str(r).strip())

    total_rolls = len(roll_list)
    chunk_size = (total_rolls + total_chunks - 1) // total_chunks
    start_idx = chunk_index * chunk_size
    end_idx = min(start_idx + chunk_size, total_rolls)

    my_rolls = roll_list[start_idx:end_idx]
    print(f"[*] Node {chunk_index + 1}/{total_chunks}: Processing {len(my_rolls)} rolls (index {start_idx} to {end_idx - 1})...\n")

    scraper = AutoFormScraper()
    completed_records = []
    success_count = 0
    start_time = time.time()

    for idx, roll in enumerate(my_rolls, 1):
        print(f"[{idx}/{len(my_rolls)}] Node {chunk_index + 1} -> Scraping Roll {roll}...")
        res = scraper.scrape(
            url="https://results.dinajpurboard.gov.bd/search/student",
            input_fields={"roll_no": roll},
            captcha_input_name="captcha",
            button_selector='button[name="submit"]',
            method="POST",
            _retry_count=2
        )

        kv = res.get("data", {}).get("key_value_data", {})
        subject_grades = res.get("subject_grades", [])

        structured_entry = {
            "index": start_idx + idx,
            "roll_no": roll,
            "success": res.get("success", False),
            "status_code": res.get("status_code"),
            "student_name": res.get("student_name") or kv.get("Name of Student") or kv.get("Student Name"),
            "father_name": res.get("father_name") or kv.get("Father's Name"),
            "mother_name": res.get("mother_name") or kv.get("Mother's Name"),
            "institute": res.get("institute") or kv.get("Name of Institute"),
            "board": res.get("board", "DINAJPUR"),
            "group": res.get("group") or kv.get("Group"),
            "result": res.get("result") or kv.get("Result"),
            "total_marks": res.get("total_marks") or kv.get("TOTAL MARK"),
            "subject_grades": subject_grades,
            "full_data": res.get("full_data") or res.get("data"),
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        if res.get("success"):
            success_count += 1
            print(f"    ✅ Success: {structured_entry.get('student_name', 'Unknown')} | Result: {structured_entry.get('result', 'N/A')}")
        else:
            print(f"    ❌ Result Not Found (Status {res.get('status_code')})")

        completed_records.append(structured_entry)

        # Non-blocking real-time webhook push (0ms overhead)
        if webhook_url:
            try:
                requests.post(
                    webhook_url,
                    json=structured_entry,
                    headers={"Bypass-Tunnel-Reminder": "true", "User-Agent": "Mozilla/5.0"},
                    timeout=2.0
                )
            except Exception as e:
                pass

        # Checkpoint save
        payload = {
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "summary": {
                "total_in_chunk": len(my_rolls),
                "scraped_so_far": len(completed_records),
                "total_success": success_count,
                "total_failed": len(completed_records) - success_count,
                "elapsed_seconds": round(time.time() - start_time, 2),
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "records": completed_records
        }

        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as out_f:
            json.dump(payload, out_f, indent=2, ensure_ascii=False)

        if delay > 0:
            time.sleep(delay)

    print(f"\n🎉 Node {chunk_index + 1} finished {len(my_rolls)} rolls! Saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk", type=int, default=0, help="Chunk index (0-based)")
    parser.add_argument("--total-chunks", type=int, default=10, help="Total number of chunks")
    parser.add_argument("--input", type=str, default="rolls.json", help="Path to rolls file")
    parser.add_argument("--output", type=str, default="chunk_result.json", help="Path to output chunk file")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests in seconds")
    parser.add_argument("--webhook-url", type=str, default="", help="Optional real-time live stream webhook URL")
    args = parser.parse_args()

    run_chunk(
        chunk_index=args.chunk,
        total_chunks=args.total_chunks,
        rolls_file=args.input,
        output_file=args.output,
        delay=args.delay,
        webhook_url=args.webhook_url or None
    )
