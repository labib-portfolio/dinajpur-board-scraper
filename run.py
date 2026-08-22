"""
Interactive Terminal CLI for Dinajpur Board Result Scraper (EIIN Mode)
Matches the exact terminal UI and execution flow.
"""

import sys
import os
import re
import json
import time
from collections import Counter
from typing import List, Dict, Any, Optional

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.stdout.reconfigure(encoding='utf-8')

import requests
from bs4 import BeautifulSoup
from engine.scraper_engine import AutoFormScraper
from engine.institute_fetcher import InstituteResultFetcher

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

COOKIE_FILE = os.path.join(BASE_DIR, ".session_cache.json")

def print_banner():
    print(f"\n{CYAN}┌───────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}Dinajpur Board Result Scraper 2026  —  EIIN Mode{RESET}         {CYAN}│{RESET}")
    print(f"{CYAN}├───────────────────────────────────────────────────────────┤{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Automated Institute Gazette & Individual Student Parser{RESET}   {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Organized by Upazilla • Zero-Loss Live Stream{RESET}            {CYAN}│{RESET}")
    print(f"{CYAN}└───────────────────────────────────────────────────────────┘{RESET}\n")

def get_eiin_inputs() -> List[str]:
    print(f"{BOLD}Enter EIIN number(s) (space, comma, or newline separated).{RESET}")
    print(f"{DIM}Press Enter on an empty line when done:{RESET}")
    
    lines = []
    while True:
        try:
            line = input().strip()
            if not line:
                break
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            break

    raw_text = " ".join(lines)
    tokens = re.split(r'[\s,]+', raw_text.strip())
    eiins = [t.strip() for t in tokens if t.strip().isdigit() and len(t.strip()) == 6]
    return list(dict.fromkeys(eiins))

def load_saved_cookies() -> Optional[Dict[str, str]]:
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None

def save_cookies(cookie_dict: Dict[str, str]):
    try:
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookie_dict, f, indent=2)
    except Exception:
        pass

def format_progress_bar(current: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return f"[{'░' * width}]"
    filled = int(width * current // total)
    return f"[{'█' * filled}{'░' * (width - filled)}]"

def run_interactive_cli():
    print_banner()

    eiins = get_eiin_inputs()
    if not eiins:
        print(f"\n{YELLOW}[!] No valid 6-digit EIIN entered. Exiting...{RESET}")
        return

    print()
    saved_cookies = load_saved_cookies()
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    })

    if saved_cookies and "XSRF-TOKEN" in saved_cookies:
        xsrf_snippet = saved_cookies['XSRF-TOKEN'][:40] + "..."
        print(f"{DIM}Saved cookie found: XSRF-TOKEN={xsrf_snippet}{RESET}")
        try:
            choice = input(f"{BOLD}Use saved cookie? (y/n/paste new): {RESET}").strip().lower()
            if choice == 'y' or choice == '':
                session.cookies.update(saved_cookies)
                print(f"{GREEN}✓ Loaded saved session cookies.{RESET}")
            elif choice.startswith("ey"): # Pasted token
                session.cookies.set("XSRF-TOKEN", choice)
                print(f"{GREEN}✓ Loaded pasted session cookie.{RESET}")
        except (EOFError, KeyboardInterrupt):
            pass

    fetcher = InstituteResultFetcher()
    student_scraper = AutoFormScraper()
    output_base = os.path.join(BASE_DIR, "upazilla_results")
    os.makedirs(output_base, exist_ok=True)

    total_eiins = len(eiins)

    for idx, eiin in enumerate(eiins, 1):
        # Header Box per EIIN
        box_text = f" EIIN {eiin}  ({idx}/{total_eiins}) "
        padding = max(0, 48 - len(box_text))
        print(f"\n{CYAN}┌{'─' * 52}┐{RESET}")
        print(f"{CYAN}│{RESET}  {BOLD}{box_text}{RESET}{' ' * padding}{CYAN}│{RESET}")
        print(f"{CYAN}└{'─' * 52}┘{RESET}\n")

        # Step 1: Fetch Institute Result
        print(f"{CYAN}[1/2] Fetching institute result for EIIN {eiin}...{RESET}")
        print(f"{DIM}Fetching CSRF token & resolving gateway...{RESET}")

        inst_data = fetcher.fetch_by_eiin(eiin)
        if not inst_data or "error" in inst_data or not inst_data.get("name"):
            print(f"{RED}[!] Error: Could not retrieve institute data for EIIN {eiin}.{RESET}\n")
            continue

        # Save session cookies for next time
        save_cookies(fetcher.session.cookies.get_dict())

        inst_name = inst_data.get("name", "Unknown")
        district = inst_data.get("district", "Unknown")
        upazila = inst_data.get("upazila", "UNKNOWN")
        students = inst_data.get("students", [])
        total_rolls = len(students)

        print(f"\n{BOLD}Institute:{RESET} {inst_name}")
        print(f"{BOLD}District:{RESET}  {district}")
        print(f"{BOLD}Upazilla:{RESET}  {upazila}")
        print(f"{GREEN}{BOLD}Total rolls found:{RESET} {total_rolls}\n")

        if total_rolls == 0:
            print(f"{YELLOW}[!] No student rolls found for this institute.{RESET}\n")
            continue

        # Prepare Upazilla Output File
        upz_slug = re.sub(r'[^a-zA-Z0-9]+', '_', upazila.strip().lower()).strip('_')
        upazilla_file = os.path.join(output_base, f"results_upazilla_{upz_slug}.json")
        
        upz_records = []
        if os.path.exists(upazilla_file):
            try:
                with open(upazilla_file, 'r', encoding='utf-8') as f:
                    prev = json.load(f)
                    upz_records = prev.get("records", [])
            except Exception:
                pass

        existing_rolls_map = {str(r.get("roll_no")): r for r in upz_records}

        # Step 2: Fetch Individual Student Results
        print(f"{CYAN}[2/2] Fetching individual results for {total_rolls} rolls...{RESET}")

        for s_idx, st in enumerate(students, 1):
            roll_str = str(st["roll"])
            p_bar = format_progress_bar(s_idx, total_rolls, width=20)
            
            # Check if already scraped
            if roll_str in existing_rolls_map:
                r_item = existing_rolls_map[roll_str]
                s_name = (r_item.get("student_name") or "STUDENT")[:20]
                gpa_res = r_item.get("result", "N/A")
                is_pass = "GPA" in gpa_res
                status_color = GREEN if is_pass else RED
                status_label = "PASSED" if is_pass else "FAILED"

                print(f"{CYAN}{p_bar}{RESET} {s_idx:3d}/{total_rolls}  Roll {roll_str}  {s_name:<20}  {gpa_res:<10} {status_color}{status_label}{RESET}")
                continue

            # Scrape student details
            res = student_scraper.scrape(
                url="https://results.dinajpurboard.gov.bd/search/student",
                input_fields={"roll_no": roll_str},
                captcha_input_name="captcha",
                button_selector='button[name="submit"]',
                method="POST",
                _retry_count=2
            )

            kv = res.get("data", {}).get("key_value_data", {})
            student_name = res.get("student_name") or kv.get("Name of Student") or kv.get("Student Name") or "STUDENT"
            gpa_res = res.get("result") or kv.get("Result") or st.get("gpa") or "N/A"
            is_pass = res.get("success", False) and not ("FAIL" in str(gpa_res).upper() or str(gpa_res).startswith("F"))
            status_color = GREEN if is_pass else RED
            status_label = "PASSED" if is_pass else "FAILED"

            s_name_display = student_name[:20]
            print(f"{CYAN}{p_bar}{RESET} {s_idx:3d}/{total_rolls}  Roll {roll_str}  {s_name_display:<20}  {gpa_res:<10} {status_color}{status_label}{RESET}")

            # Structured Entry
            record_entry = {
                "index": len(upz_records) + 1,
                "roll_no": roll_str,
                "eiin": int(eiin),
                "upazila": upazila,
                "district": district,
                "institute": inst_name,
                "success": res.get("success", False),
                "student_name": student_name,
                "father_name": res.get("father_name") or kv.get("Father's Name"),
                "mother_name": res.get("mother_name") or kv.get("Mother's Name"),
                "group": res.get("group") or kv.get("Group") or st.get("group"),
                "result": gpa_res,
                "total_marks": res.get("total_marks") or kv.get("TOTAL MARK"),
                "subject_grades": res.get("subject_grades", []),
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            upz_records.append(record_entry)
            existing_rolls_map[roll_str] = record_entry

            # Checkpoint save into Upazilla JSON
            payload = {
                "upazila": upazila,
                "district": district,
                "summary": {
                    "total_records": len(upz_records),
                    "total_passed": sum(1 for r in upz_records if "GPA" in str(r.get("result", ""))),
                    "total_failed": sum(1 for r in upz_records if not ("GPA" in str(r.get("result", "")))),
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "records": upz_records
            }

            with open(upazilla_file, 'w', encoding='utf-8') as out_f:
                json.dump(payload, out_f, indent=2, ensure_ascii=False)

            # Polite zero-penalty pacing
            time.sleep(3.2)

        print(f"\n{GREEN}✓ Completed EIIN {eiin} ({inst_name}){RESET}")
        print(f"{DIM}Saved to: {upazilla_file}{RESET}\n")

    print(f"{GREEN}{BOLD}🎉 All EIIN tasks completed successfully!{RESET}\n")


if __name__ == "__main__":
    run_interactive_cli()
