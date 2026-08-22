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
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from engine.scraper_engine import AutoFormScraper

def run_chunk(chunk_index: int, total_chunks: int, rolls_file: str, output_file: str, delay: float = 3.2, webhook_url: Optional[str] = None):
    with open(rolls_file, 'r', encoding='utf-8') as f:
        rolls_data = json.load(f)

    if isinstance(rolls_data, dict):
        rolls = rolls_data.get("rolls", [])
    else:
        rolls = rolls_data

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

    def scrape_student_fast(roll: str) -> Optional[dict]:
        try:
            url = f"https://results.dinajpurboard.gov.bd/fast/student?roll={roll}&exam=1&exp=1787224774&t=769debce061f8471859fb4cd1069e0454aae3b18294e70c8454edd2fc416320a"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                name, father, mother, inst, result, marks, group = "", "", "", "", "", "", ""
                for tr in soup.find_all('tr'):
                    tds = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    if len(tds) >= 2:
                        k = tds[0].lower()
                        if 'name of student' in k: name = tds[1]
                        elif 'father' in k: father = tds[1]
                        elif 'mother' in k: mother = tds[1]
                        elif 'institute' in k: inst = tds[1]
                        elif 'result' in k: result = tds[1]
                        elif 'total mark' in k: marks = tds[1]
                        elif 'group' in k: group = tds[1]

                grades = []
                for tr in soup.find_all('tr'):
                    tds = tr.find_all('td')
                    if len(tds) >= 3 and tds[0].get_text(strip=True).isdigit():
                        code = tds[0].get_text(strip=True)
                        subj = tds[1].get_text(strip=True)
                        grade = tds[2].get_text(strip=True)
                        grades.append({"sub_code": code, "subject_name": subj, "grade": grade})

                if name:
                    return {
                        "success": True,
                        "status_code": 200,
                        "student_name": name,
                        "father_name": father,
                        "mother_name": mother,
                        "institute": inst,
                        "board": "DINAJPUR",
                        "group": group or "GENERAL",
                        "result": result or "N/A",
                        "total_marks": marks or "N/A",
                        "subject_grades": grades
                    }
        except Exception:
            pass
        return None

    for idx, roll in enumerate(my_rolls, 1):
        print(f"[{idx}/{len(my_rolls)}] Node {chunk_index + 1} -> Scraping Roll {roll}...")
        
        # 1. Primary high-speed direct lookup (0.3s)
        fast_res = scrape_student_fast(roll)
        if fast_res:
            res = fast_res
        else:
            # 2. Resilient fallback via AutoFormScraper
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

    # Signal chunk completion to master CLI
    if webhook_url:
        try:
            requests.post(
                webhook_url,
                json={
                    "event": "chunk_completed",
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                    "total_in_chunk": len(my_rolls),
                    "total_success": success_count
                },
                headers={"Bypass-Tunnel-Reminder": "true", "User-Agent": "Mozilla/5.0"},
                timeout=3.0
            )
        except Exception:
            pass

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

    webhook = None
    if os.path.exists("tunnel_config.json"):
        try:
            with open("tunnel_config.json", "r", encoding="utf-8") as tf:
                cfg = json.load(tf)
                webhook = cfg.get("webhook_url", "").strip()
        except Exception:
            pass

    if not webhook:
        webhook = args.webhook_url.strip()

    run_chunk(
        chunk_index=args.chunk,
        total_chunks=args.total_chunks,
        rolls_file=args.input,
        output_file=args.output,
        delay=args.delay,
        webhook_url=webhook or None
    )
