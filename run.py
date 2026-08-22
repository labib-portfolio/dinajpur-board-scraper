"""
Interactive Terminal CLI for Dinajpur Board Result Scraper
100% Cloud-Powered Mode using 40 Parallel GitHub Actions Cloud Runners
Optimized for Massive Multi-EIIN and District-Wide Batches
"""

import sys
import os
import re
import json
import time
import subprocess
import requests
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.stdout.reconfigure(encoding='utf-8')

# Completely mute noisy debug/info logs from the terminal
logging.disable(logging.INFO)
logging.basicConfig(level=logging.WARNING)
for log_name in ["engine.scraper_engine", "engine.institute_fetcher", "urllib3", "root"]:
    logging.getLogger(log_name).setLevel(logging.WARNING)

from engine.institute_fetcher import InstituteResultFetcher

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def print_banner():
    print(f"\n{CYAN}┌───────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}Dinajpur Board Result Scraper 2026 — 40 Cloud Workers{RESET}    {CYAN}│{RESET}")
    print(f"{CYAN}├───────────────────────────────────────────────────────────┤{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}100% Cloud Parallel Scraping for Massive Multi-EIIN Lists{RESET} {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}2 Repositories • 40 Unique IP Addresses • 600 rolls/min{RESET}   {CYAN}│{RESET}")
    print(f"{CYAN}└───────────────────────────────────────────────────────────┘{RESET}\n")

def get_eiin_inputs() -> List[str]:
    print(f"{BOLD}Enter EIIN number(s) (space, comma, or newline separated).{RESET}")
    print(f"{DIM}You can paste single EIINs or massive lists of 100+ EIINs.{RESET}")
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

def format_progress_bar(current: int, total: int, width: int = 20) -> str:
    if total <= 0:
        return f"[{'░' * width}]"
    filled = int(width * current // total)
    return f"[{'█' * filled}{'░' * (width - filled)}]"

def dispatch_to_github_cloud(rolls: List[str]) -> bool:
    """Partitions rolls across Repo 1 and Repo 2 and triggers GitHub Actions."""
    try:
        rolls_file = os.path.join(BASE_DIR, "rolls.json")
        with open(rolls_file, 'w', encoding='utf-8') as f:
            json.dump(rolls, f, indent=2)

        print(f"{CYAN}[🚀 Cloud Dispatch] Launching 40 Parallel Cloud Workers on GitHub Actions...{RESET}")
        
        subprocess.run(
            ["git", "add", "rolls.json"],
            cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"Dispatch {len(rolls)} rolls to 40 cloud workers"],
            cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        
        print(f"{DIM}Pushing to Node 1 (20 Workers) and Node 2 (20 Workers)...{RESET}")
        p1 = subprocess.Popen(["git", "push", "origin", "main"], cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(["git", "push", "node2", "main"], cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p1.wait()
        p2.wait()

        print(f"{GREEN}✓ Dispatched! 40 Cloud Workers are actively scraping in parallel at 600 rolls/min!{RESET}\n")
        return True
    except Exception as e:
        print(f"{RED}[!] Error dispatching to GitHub: {e}{RESET}")
        return False

def run_cloud_cli():
    print_banner()

    eiins = get_eiin_inputs()
    if not eiins:
        print(f"\n{YELLOW}[!] No valid 6-digit EIIN entered. Exiting...{RESET}")
        return

    fetcher = InstituteResultFetcher()
    output_base = os.path.join(BASE_DIR, "upazilla_results")
    os.makedirs(output_base, exist_ok=True)

    print(f"\n{CYAN}[Step 1/2] Harvesting Gazette Records for {len(eiins)} Institution(s)...{RESET}")

    # Map roll_no -> {eiin, institute_name, upazila, district}
    roll_metadata_map = {}
    all_target_rolls = []
    upazilla_summary = {}

    for idx, eiin in enumerate(eiins, 1):
        print(f"  [{idx}/{len(eiins)}] Querying EIIN {eiin}...", end=" ", flush=True)
        inst_data = fetcher.fetch_by_eiin(eiin)

        if not inst_data or "error" in inst_data or not inst_data.get("name"):
            print(f"{RED}Failed (Not found){RESET}")
            continue

        inst_name = inst_data.get("name", "Unknown")
        district = inst_data.get("district", "Unknown")
        upazila = inst_data.get("upazila", "UNKNOWN")
        students = inst_data.get("students", [])
        
        rolls = [str(s["roll"]) for s in students if s.get("roll")]
        print(f"{GREEN}✓ {inst_name[:32]} ({len(rolls)} rolls){RESET}")

        upz_slug = re.sub(r'[^a-zA-Z0-9]+', '_', upazila.strip().lower()).strip('_')
        if upz_slug not in upazilla_summary:
            upazilla_summary[upz_slug] = {"upazila": upazila, "district": district, "rolls_count": 0}
        upazilla_summary[upz_slug]["rolls_count"] += len(rolls)

        for s in students:
            r_str = str(s["roll"])
            all_target_rolls.append(r_str)
            roll_metadata_map[r_str] = {
                "eiin": int(eiin),
                "institute": inst_name,
                "upazila": upazila,
                "district": district,
                "group": s.get("group")
            }

        time.sleep(0.5)

    all_unique_rolls = list(dict.fromkeys(all_target_rolls))

    print(f"\n=======================================================")
    print(f"📊 {BOLD}HARVEST SUMMARY:{RESET}")
    print(f"  • Institutions Processed: {len(eiins)}")
    print(f"  • Total Upazillas:        {len(upazilla_summary)}")
    print(f"  • Total Candidate Rolls:  {len(all_unique_rolls)}")
    print(f"=======================================================\n")

    if not all_unique_rolls:
        print(f"{YELLOW}[!] No student rolls found across the provided EIINs.{RESET}\n")
        return

    # Check already scraped
    master_file = os.path.join(BASE_DIR, "scraped_results_all.json")
    already_scraped_map = {}
    if os.path.exists(master_file):
        try:
            with open(master_file, 'r', encoding='utf-8') as f:
                prev_data = json.load(f)
                for r in prev_data.get("records", []):
                    if r.get("roll_no"):
                        already_scraped_map[str(r.get("roll_no"))] = r
        except Exception:
            pass

    pending_rolls = [r for r in all_unique_rolls if r not in already_scraped_map]
    print(f"[*] Already Scraped: {len(all_unique_rolls) - len(pending_rolls)} | Remaining: {len(pending_rolls)}")

    if not pending_rolls:
        print(f"{GREEN}🎉 All {len(all_unique_rolls)} rolls across all EIINs are already 100% scraped!{RESET}\n")
        return

    # Step 2: Dispatch Entire Pool to 40 Cloud Workers
    print(f"\n{CYAN}[Step 2/2] Launching 40 Cloud Workers for {len(pending_rolls)} Rolls...{RESET}")
    dispatch_to_github_cloud(pending_rolls)

    print(f"{BOLD}⏳ Connecting to 40 GitHub Cloud Workers (Booting VMs ~20-30s)...{RESET}")

    received_count = 0
    target_count = len(pending_rolls)
    seen_rolls = set(already_scraped_map.keys())
    timeout_start = time.time()
    boot_announced = False

    # Track Upazilla file records
    upazilla_records_map = {}

    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    spin_idx = 0

    while received_count < target_count:
        if not boot_announced and received_count == 0:
            elapsed = int(time.time() - timeout_start)
            spin_char = spinner_chars[spin_idx % len(spinner_chars)]
            spin_idx += 1
            print(f"\r  {CYAN}{spin_char}{RESET} Waiting for cloud workers to start streaming ({elapsed}s)...", end="", flush=True)

        if os.path.exists(master_file):
            try:
                with open(master_file, 'r', encoding='utf-8') as f:
                    m_data = json.load(f)
                    records = m_data.get("records", [])
                    
                    for r in records:
                        r_roll = str(r.get("roll_no"))
                        if r_roll in pending_rolls and r_roll not in seen_rolls:
                            if not boot_announced:
                                boot_announced = True
                                print(f"\r{GREEN}⚡ Connected! Receiving live stream from 40 cloud workers:{RESET}\n")

                            seen_rolls.add(r_roll)
                            received_count += 1
                            
                            s_name = r.get("student_name") or "STUDENT"
                            gpa_res = r.get("result", "N/A")
                            is_pass = "GPA" in str(gpa_res)
                            status_color = GREEN if is_pass else RED
                            status_label = "PASSED" if is_pass else "FAILED"
                            p_bar = format_progress_bar(received_count, target_count, width=20)

                            print(f"{CYAN}{p_bar}{RESET} {received_count:4d}/{target_count}  Roll {r_roll}  {s_name:<32}  {gpa_res:<10} {status_color}{status_label}{RESET}")

                            # Route record to its respective Upazilla JSON
                            meta = roll_metadata_map.get(r_roll, {})
                            upz_name = meta.get("upazila") or r.get("upazilla") or "UNKNOWN_UPAZILLA"
                            upz_slug = re.sub(r'[^a-zA-Z0-9]+', '_', upz_name.strip().lower()).strip('_')
                            upz_file = os.path.join(output_base, f"results_upazilla_{upz_slug}.json")

                            if upz_slug not in upazilla_records_map:
                                upazilla_records_map[upz_slug] = []
                                if os.path.exists(upz_file):
                                    try:
                                        with open(upz_file, 'r', encoding='utf-8') as uf:
                                            upazilla_records_map[upz_slug] = json.load(uf).get("records", [])
                                    except Exception:
                                        pass

                            r["upazila"] = upz_name
                            r["district"] = meta.get("district", "NILPHAMARI")
                            r["eiin"] = meta.get("eiin")
                            upazilla_records_map[upz_slug].append(r)

                            # Save Upazilla file checkpoint
                            upz_payload = {
                                "upazila": upz_name,
                                "district": meta.get("district", "NILPHAMARI"),
                                "summary": {
                                    "total_records": len(upazilla_records_map[upz_slug]),
                                    "total_passed": sum(1 for item in upazilla_records_map[upz_slug] if "GPA" in str(item.get("result", ""))),
                                    "total_failed": sum(1 for item in upazilla_records_map[upz_slug] if not ("GPA" in str(item.get("result", "")))),
                                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                                },
                                "records": upazilla_records_map[upz_slug]
                            }

                            with open(upz_file, 'w', encoding='utf-8') as out_f:
                                json.dump(upz_payload, out_f, indent=2, ensure_ascii=False)

            except Exception:
                pass

        time.sleep(1.0)
        # Timeout safety (e.g. 30 mins)
        if time.time() - timeout_start > 1800:
            break

    print(f"\n{GREEN}{BOLD}🎉 Finished Massive Batch! All {received_count} student results saved across Upazilla files!{RESET}\n")


if __name__ == "__main__":
    run_cloud_cli()
