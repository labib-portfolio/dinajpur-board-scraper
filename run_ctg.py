"""
Interactive Terminal CLI for Chittagong Education Board (BISE CTG) Result Scraper 2026
Ultra-Fast Concurrent Scraping Engine (Unified Master File Across All Modes)
Endpoints:
  • Institutional Gazette (with subject marks): https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/resultm.php
  • Individual Marksheet (by roll): https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/result.php
"""

import sys
import os
import re
import json
import time
import glob
import logging
import threading
import collections
import concurrent.futures
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

logging.disable(logging.INFO)
logging.basicConfig(level=logging.WARNING)

from engine.ctg_scraper import (
    parse_ctg_student_html,
    fetch_ctg_student,
    parse_ctg_institute_gazette,
    fetch_ctg_institute
)

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def get_default_results_dir() -> str:
    """Auto-detect Android Mobile Internal Storage (Termux) or PC directory."""
    if os.path.exists("/storage/emulated/0"):
        return "/storage/emulated/0/Result Scraper/Chittagong"
    elif os.path.exists("/sdcard"):
        return "/sdcard/Result Scraper/Chittagong"
    elif os.path.exists("/storage/emulated"):
        return "/storage/emulated/Result Scraper/Chittagong"
    return os.path.join(BASE_DIR, "results", "chittagong")


def print_ctg_banner():
    print(f"\n{CYAN}┌───────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}Chittagong Board SSC Result Scraper 2026 — High-Speed{RESET}     {CYAN}│{RESET}")
    print(f"{CYAN}├───────────────────────────────────────────────────────────┤{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Unified Master Storage • Auto-Calculated Total Marks{RESET}       {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Zero CAPTCHA • Multi-Threaded Proxies • Real-Time JSON{RESET}    {CYAN}│{RESET}")
    print(f"{CYAN}└───────────────────────────────────────────────────────────┘{RESET}\n", flush=True)


def load_proxies() -> List[str]:
    proxies = []
    proxy_file = os.path.join(BASE_DIR, "webshare_proxies.txt")
    if os.path.exists(proxy_file):
        with open(proxy_file, "r", encoding="utf-8") as f:
            for line in f:
                l = line.strip()
                if l and not l.startswith("#") and ":" in l:
                    proxies.append(l)
    return proxies


def format_progress_bar(current: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return f"[{'=' * width}]"
    fraction = min(1.0, max(0.0, current / total))
    filled = int(round(width * fraction))
    return f"[{'=' * filled}{' ' * (width - filled)}]"


# =========================================================================
# 1. EIIN INSTITUTIONAL SCRAPING ENGINE (High-Speed Single / Batch EIIN)
# =========================================================================
def run_ctg_eiin_scraper(
    eiins: List[str],
    output_dir: Optional[str] = None,
    output_name: str = "chittagong_results.json"
):
    eiins = sorted(list(dict.fromkeys(str(e).strip() for e in eiins if str(e).strip().isdigit() and len(str(e).strip()) == 6)))
    if not eiins:
        print(f"{RED}[!] No valid 6-digit EIINs provided.{RESET}", flush=True)
        return

    out_dir = output_dir or get_default_results_dir()
    os.makedirs(out_dir, exist_ok=True)
    master_file = os.path.join(out_dir, output_name)

    proxies = load_proxies()
    print(f"\n=======================================================")
    print(f"🏛️  {BOLD}CHITTAGONG EIIN INSTITUTIONAL PIPELINE:{RESET}")
    print(f"  • Target Institutions: {GREEN}{BOLD}{len(eiins)} School EIINs{RESET}")
    print(f"  • Active Proxy Pool:   {CYAN}{BOLD}{len(proxies)} Dedicated Nodes{RESET}")
    print(f"  • Master Destination:  {YELLOW}{master_file}{RESET}")
    print(f"=======================================================\n", flush=True)

    already_scraped_institutes = {}
    already_scraped_students = {}
    if os.path.exists(master_file):
        try:
            with open(master_file, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                for inst in prev_data.get("institutions", []):
                    if inst.get("eiin"):
                        already_scraped_institutes[str(inst.get("eiin"))] = inst
                raw_studs = prev_data.get("students", []) or prev_data.get("records", [])
                for st in raw_studs:
                    if st.get("roll_no"):
                        already_scraped_students[str(st.get("roll_no"))] = st
        except Exception:
            pass

    pending_eiins = [e for e in eiins if e not in already_scraped_institutes]
    if len(already_scraped_institutes) > 0:
        print(f"  • Already Scraped:     {GREEN}{len(already_scraped_institutes)} institutions (Skipping){RESET}")
        print(f"  • Pending to Scrape:   {YELLOW}{len(pending_eiins)} institutions{RESET}\n", flush=True)

    if not pending_eiins:
        print(f"{GREEN}✓ All {len(eiins)} institutions are already in master file! Total students: {len(already_scraped_students)}{RESET}", flush=True)
        return

    institutions_map = dict(already_scraped_institutes)
    students_map = dict(already_scraped_students)
    data_lock = threading.Lock()
    print_lock = threading.Lock()
    stats_lock = threading.Lock()

    completed_inst_count = 0
    batch_start_time = time.time()

    def save_master_eiin():
        with data_lock:
            all_insts = list(institutions_map.values())
            all_studs = list(students_map.values())
            passed = sum(1 for x in all_studs if x.get("status") == "PASSED")
            gpa5 = sum(1 for x in all_studs if str(x.get("gpa", "")) in ["5.00", "5", "5.0"])
            
            payload = {
                "board": "CHATTOGRAM",
                "summary": {
                    "total_institutions": len(all_insts),
                    "total_students": len(all_studs),
                    "total_passed": passed,
                    "total_failed": len(all_studs) - passed,
                    "total_gpa_5": gpa5,
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "institutions": all_insts,
                "students": all_studs
            }
            tmp_f = master_file + ".tmp"
            try:
                with open(tmp_f, "w", encoding="utf-8") as out:
                    json.dump(payload, out, indent=2, ensure_ascii=False)
                os.replace(tmp_f, master_file)
            except Exception:
                pass

    def process_eiin(task_info):
        nonlocal completed_inst_count
        idx, eiin_str = task_info
        p = proxies[idx % len(proxies)] if proxies else None
        
        res = fetch_ctg_institute(eiin=eiin_str, proxy=p, timeout=8.0)
        if not res or not res.get("success"):
            p_alt = proxies[(idx + 13) % len(proxies)] if proxies else None
            res = fetch_ctg_institute(eiin=eiin_str, proxy=p_alt, timeout=8.0)
            
        with stats_lock:
            completed_inst_count += 1
            cur_c = completed_inst_count
            cur_t = len(pending_eiins)

        pct = (cur_c / max(1, cur_t)) * 100
        p_bar = format_progress_bar(cur_c, cur_t, width=20)

        if res and res.get("success"):
            inst_name = res.get("institute_name", "UNKNOWN")
            studs = res.get("students", [])
            
            with data_lock:
                institutions_map[eiin_str] = {
                    "eiin": eiin_str,
                    "name": inst_name,
                    "zilla": res.get("zilla", ""),
                    "thana": res.get("thana", ""),
                    "appeared": res.get("total_appeared", 0),
                    "passed": res.get("total_passed", 0),
                    "gpa5": res.get("total_gpa5", 0),
                    "pass_percentage": res.get("pass_percentage", ""),
                    "students_count": len(studs)
                }
                for s in studs:
                    students_map[str(s["roll_no"])] = s

            with print_lock:
                sys.stdout.write("\r\033[K")
                print(f" {cur_c:3d}/{cur_t}  EIIN {eiin_str}  {inst_name:<40}  {len(studs):3d} Students  {GREEN}✓ OK{RESET}", flush=True)
                sys.stdout.write(f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_c}/{cur_t} ({pct:.1f}%) │ 👥 {len(students_map)} Total Master Students")
                sys.stdout.flush()
        elif res and res.get("error") == "EIIN Not Found":
            with print_lock:
                sys.stdout.write("\r\033[K")
                print(f" {cur_c:3d}/{cur_t}  EIIN {eiin_str}  {RED}EIIN Not Found{RESET}", flush=True)
        else:
            with print_lock:
                sys.stdout.write("\r\033[K")
                print(f" {cur_c:3d}/{cur_t}  EIIN {eiin_str}  {YELLOW}Failed to fetch{RESET}", flush=True)

        if completed_inst_count % 3 == 0:
            save_master_eiin()

        return res

    num_threads = min(20, max(2, len(proxies) if proxies else 6))
    if len(pending_eiins) < num_threads:
        num_threads = len(pending_eiins)

    tasks = list(enumerate(pending_eiins))
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        try:
            list(executor.map(process_eiin, tasks))
        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}[!] Pipeline interrupted by user. Saved data safely!{RESET}", flush=True)

    save_master_eiin()
    sys.stdout.write("\n\n")

    total_elapsed = time.time() - batch_start_time
    mins, secs = divmod(total_elapsed, 60)
    time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"

    print(f"=======================================================")
    print(f"🎉 {GREEN}{BOLD}CHITTAGONG INSTITUTIONAL SCRAPING COMPLETE!{RESET}")
    print(f"  • Institutions in Master: {len(institutions_map)}")
    print(f"  • Total Master Students:  {GREEN}{BOLD}{len(students_map)} Students{RESET}")
    print(f"  • Total Time Elapsed:     {CYAN}{time_str}{RESET}")
    print(f"  • Master JSON File:       {GREEN}{master_file}{RESET}")
    print(f"=======================================================\n", flush=True)


# =========================================================================
# 2. INDIVIDUAL ROLL / RANGE SCRAPING ENGINE (Merges into Same Master File)
# =========================================================================
def run_ctg_scraper(
    rolls: List[str],
    output_dir: Optional[str] = None,
    output_name: str = "chittagong_results.json",
    force_recheck: bool = False
):
    rolls = sorted(list(dict.fromkeys(str(r).strip() for r in rolls if str(r).strip().isdigit())))
    if not rolls:
        print(f"{RED}[!] No valid 6-digit rolls provided.{RESET}", flush=True)
        return

    out_dir = output_dir or get_default_results_dir()
    os.makedirs(out_dir, exist_ok=True)
    master_file = os.path.join(out_dir, output_name)
    cache_file = os.path.join(out_dir, f".{os.path.splitext(output_name)[0]}_memory.json")

    proxies = load_proxies()
    print(f"\n=======================================================")
    print(f"🚀 {BOLD}CHITTAGONG ROLL SCRAPER PIPELINE CONFIGURATION:{RESET}")
    print(f"  • Requested Range:     {GREEN}{BOLD}{len(rolls)} Candidate Rolls{RESET}")
    print(f"  • Active Proxy Pool:   {CYAN}{BOLD}{len(proxies)} Dedicated Nodes{RESET}")
    print(f"  • Master Destination:  {YELLOW}{master_file}{RESET}")
    print(f"=======================================================\n", flush=True)

    already_scraped = {}
    institutions_map = {}
    if os.path.exists(master_file):
        try:
            with open(master_file, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                for inst in prev_data.get("institutions", []):
                    if inst.get("eiin"):
                        institutions_map[str(inst.get("eiin"))] = inst
                raw_studs = prev_data.get("students", []) or prev_data.get("records", [])
                for r in raw_studs:
                    if r.get("roll_no"):
                        already_scraped[str(r.get("roll_no"))] = r
        except Exception:
            pass

    dead_slots = set()
    if not force_recheck and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as cf:
                cache_data = json.load(cf)
                dead_slots = set(str(x) for x in cache_data.get("dead_slots", []))
        except Exception:
            pass

    if force_recheck:
        pending_rolls = [r for r in rolls if r not in already_scraped]
    else:
        pending_rolls = [r for r in rolls if r not in already_scraped and r not in dead_slots]

    skipped_success = sum(1 for r in rolls if r in already_scraped)
    skipped_dead = sum(1 for r in rolls if r in dead_slots and r not in already_scraped)

    if skipped_success > 0 or skipped_dead > 0:
        print(f"🧠 {BOLD}CACHED MEMORY STATUS:{RESET}")
        if skipped_success > 0:
            print(f"  • Already Saved in Master: {GREEN}{skipped_success} rolls (Skipped - 100% Cached){RESET}")
        if skipped_dead > 0:
            print(f"  • Confirmed Dead Slots:    {DIM}{skipped_dead} empty rolls (Skipped - Already Checked){RESET}")
        print(f"  • Pending Live Queries:    {YELLOW}{len(pending_rolls)} rolls{RESET}\n", flush=True)

    if not pending_rolls:
        print(f"{GREEN}✓ All {len(rolls)} rolls in this range are already in master file!{RESET}", flush=True)
        print(f"  (Total valid saved records in master: {len(already_scraped)})")
        return

    results_map = dict(already_scraped)
    dead_slots_set = set(dead_slots)

    results_lock = threading.Lock()
    dead_lock = threading.Lock()
    print_lock = threading.Lock()
    stats_lock = threading.Lock()
    recent_completions = collections.deque()
    recent_lock = threading.Lock()

    scraped_count = 0
    first_roll_time = [None]
    last_roll_time = [None]
    batch_start_time = time.time()

    def save_master():
        with results_lock:
            all_studs = list(results_map.values())
            passed = sum(1 for x in all_studs if x.get("status") == "PASSED" or "GPA" in str(x.get("result", "")))
            gpa5 = sum(1 for x in all_studs if str(x.get("gpa", "")) in ["5.00", "5", "5.0"])
            data = {
                "board": "CHATTOGRAM",
                "summary": {
                    "total_institutions": len(institutions_map),
                    "total_students": len(all_studs),
                    "total_passed": passed,
                    "total_failed": len(all_studs) - passed,
                    "total_gpa_5": gpa5,
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "institutions": list(institutions_map.values()),
                "students": all_studs
            }
            tmp_f = master_file + ".tmp"
            try:
                with open(tmp_f, "w", encoding="utf-8") as out:
                    json.dump(data, out, indent=2, ensure_ascii=False)
                os.replace(tmp_f, master_file)
            except Exception:
                pass

        with dead_lock:
            tmp_c = cache_file + ".tmp"
            try:
                with open(tmp_c, "w", encoding="utf-8") as out_c:
                    json.dump({
                        "board": "CHATTOGRAM",
                        "dead_slots_count": len(dead_slots_set),
                        "dead_slots": sorted(list(dead_slots_set)),
                        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                    }, out_c, indent=2)
                os.replace(tmp_c, cache_file)
            except Exception:
                pass

    def process_roll(task_info):
        nonlocal scraped_count
        idx, roll_str = task_info
        p = proxies[idx % len(proxies)] if proxies else None

        res = fetch_ctg_student(roll=roll_str, proxy=p, timeout=7.0)
        if not res or not res.get("success"):
            p_alt = proxies[(idx + 17) % len(proxies)] if proxies else None
            res = fetch_ctg_student(roll=roll_str, proxy=p_alt, timeout=7.0)

        now_ts = time.time()
        with stats_lock:
            if first_roll_time[0] is None:
                first_roll_time[0] = now_ts
            last_roll_time[0] = now_ts
            scraped_count += 1
            cur_c = scraped_count
            cur_t = len(pending_rolls)

        with recent_lock:
            recent_completions.append(now_ts)
            cutoff = now_ts - 6.0
            while recent_completions and recent_completions[0] < cutoff:
                recent_completions.popleft()
            dur = max(0.5, now_ts - recent_completions[0]) if len(recent_completions) > 1 else 1.0
            speed = len(recent_completions) / dur

        pct = (cur_c / max(1, cur_t)) * 100
        elapsed = now_ts - (first_roll_time[0] or now_ts)
        mins, secs = divmod(elapsed, 60)
        time_str = f"{int(mins)}m {int(secs):02d}s"
        p_bar = format_progress_bar(cur_c, cur_t, width=22)

        if res and res.get("success"):
            with results_lock:
                results_map[roll_str] = {
                    "roll_no": roll_str,
                    "student_name": res.get("student_name"),
                    "gpa": res.get("gpa"),
                    "total_marks": res.get("total_marks"),
                    "group": res.get("group", "GENERAL"),
                    "status": "PASSED" if "GPA" in str(res.get("result", "")) else "FAILED",
                    "institute": res.get("institute", ""),
                    "registration_no": res.get("registration_no", ""),
                    "father_name": res.get("father_name", ""),
                    "mother_name": res.get("mother_name", "")
                }

            s_name = res.get("student_name", "STUDENT")
            gpa_res = res.get("result", "N/A")
            is_pass = "GPA" in str(gpa_res)
            st_color = GREEN if is_pass else RED
            st_label = "PASSED" if is_pass else "FAILED"

            with print_lock:
                sys.stdout.write("\r\033[K")
                print(f" {cur_c:4d}/{cur_t}  Roll {roll_str:<7}  {s_name:<30}  {gpa_res:<10} {st_color}{st_label}{RESET}", flush=True)
                sys.stdout.write(f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_c}/{cur_t} ({pct:.1f}%) ⚡ {speed:.1f} rolls/s │ ⏱️ {time_str}")
                sys.stdout.flush()
        elif res and res.get("error") == "Record Not Found":
            with dead_lock:
                dead_slots_set.add(roll_str)
            with print_lock:
                sys.stdout.write(f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_c}/{cur_t} ({pct:.1f}%) ⚡ {speed:.1f} rolls/s │ ⏱️ {time_str}")
                sys.stdout.flush()

        if scraped_count % 20 == 0:
            save_master()

        return res

    num_threads = min(30, max(4, len(proxies) if proxies else 10))
    if len(pending_rolls) < num_threads:
        num_threads = len(pending_rolls)

    tasks = list(enumerate(pending_rolls))
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        try:
            list(executor.map(process_roll, tasks))
        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}[!] Pipeline interrupted by user. Saved {len(results_map)} records safely!{RESET}", flush=True)

    save_master()
    sys.stdout.write("\n\n")

    total_elapsed = time.time() - batch_start_time
    mins, secs = divmod(total_elapsed, 60)
    time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"

    print(f"=======================================================")
    print(f"🎉 {GREEN}{BOLD}CHITTAGONG BOARD SCRAPING COMPLETE!{RESET}")
    print(f"  • Total Master Students:  {GREEN}{len(results_map)}{RESET}")
    print(f"  • Total Dead Slots:       {DIM}{len(dead_slots_set)}{RESET}")
    print(f"  • Total Time Elapsed:     {CYAN}{time_str}{RESET}")
    print(f"  • Master JSON File:       {GREEN}{master_file}{RESET}")
    print(f"=======================================================\n", flush=True)


# =========================================================================
# 3. INTERACTIVE CLI MENU
# =========================================================================
def interactive_ctg_menu():
    print_ctg_banner()
    print(f"{BOLD}Select Chittagong Board Scraping Mode:{RESET}")
    print(f"  {GREEN}[1]{RESET} {BOLD}EIIN Mode{RESET} — Instant Institutional Results (Recommended ⚡)")
    print(f"  {GREEN}[2]{RESET} {BOLD}District / Upazila Bulk Scraper{RESET} — Select Upazila and scrape all colleges/schools")
    print(f"  {CYAN}[3]{RESET} Roll Number Range (e.g. 100001-105000, 129000-129100)")
    print(f"  {CYAN}[4]{RESET} Single / Multiple Candidate Rolls (e.g. 129051, 100001)")
    print(f"  {CYAN}[5]{RESET} Load Rolls / EIINs from File (txt/json)")
    print(f"  {CYAN}[0]{RESET} Exit\n", flush=True)

    choice = input(f"{BOLD}Enter choice [1-5]: {RESET}").strip()

    if choice == "1":
        print(f"\n{BOLD}Enter EIIN number(s) (e.g. 103086 or space/comma-separated list):{RESET}")
        raw = input(f"{BOLD}EIIN: {RESET}").strip()
        eiins = [e.strip() for e in re.split(r'[,\s\n]+', raw) if e.strip().isdigit() and len(e.strip()) == 6]
        if eiins:
            run_ctg_eiin_scraper(eiins)
    elif choice == "2":
        zillas = ["BANDARBAN", "CHATTOGRAM", "COX_S_BAZAR", "KHAGRACHHARI", "RANGAMATI"]
        print(f"\n{BOLD}Select Zilla (District):{RESET}", flush=True)
        for i, z in enumerate(zillas, 1):
            print(f"  [{i}] {z}")
        z_choice = input(f"Enter Zilla [1-5]: ").strip()
        if z_choice.isdigit() and 1 <= int(z_choice) <= 5:
            selected_z = zillas[int(z_choice) - 1]
            z_dir = os.path.join(BASE_DIR, "chittagong_board_eiin", "districts", selected_z)
            if not os.path.exists(z_dir):
                z_dir = os.path.join(r"C:\Users\labib_n4\Documents\Project\Result-Scraper\chittagong_board_eiin\districts", selected_z)
            
            upz_files = glob.glob(os.path.join(z_dir, "*.txt"))
            upz_files = [f for f in upz_files if "ALL_" not in os.path.basename(f)]
            
            print(f"\n{BOLD}Upazilas in {selected_z}:{RESET}", flush=True)
            print(f"  [0] >> SCRAPE ENTIRE {selected_z} ZILLA (All Upazilas) <<")
            for i, uf in enumerate(upz_files, 1):
                u_name = os.path.splitext(os.path.basename(uf))[0]
                print(f"  [{i}] {u_name}")
            u_choice = input(f"Select Option [0-{len(upz_files)}]: ").strip()
            
            if u_choice == "0":
                all_z_file = os.path.join(z_dir, f"ALL_{selected_z}_EIINS.txt")
                if os.path.exists(all_z_file):
                    with open(all_z_file, "r", encoding="utf-8") as azf:
                        eiins = [l.strip() for l in azf if l.strip().isdigit()]
                    out_d = os.path.join(get_default_results_dir(), selected_z)
                    run_ctg_eiin_scraper(eiins, output_dir=out_d, output_name=f"all_{selected_z.lower()}_results.json")
            elif u_choice.isdigit() and 1 <= int(u_choice) <= len(upz_files):
                selected_upz_file = upz_files[int(u_choice) - 1]
                upz_name = os.path.splitext(os.path.basename(selected_upz_file))[0]
                with open(selected_upz_file, "r", encoding="utf-8") as uf:
                    eiins = [l.strip() for l in uf if l.strip().isdigit()]
                print(f"\n{GREEN}Selected: {selected_z} -> {upz_name} ({len(eiins)} institutions){RESET}", flush=True)
                out_d = os.path.join(get_default_results_dir(), selected_z)
                run_ctg_eiin_scraper(eiins, output_dir=out_d, output_name=f"{upz_name.lower()}_results.json")
    elif choice == "3":
        raw = input(f"\n{BOLD}Enter Roll Range (e.g. 100001-100500, 129000-129050): {RESET}").strip()
        m = re.match(r'(\d+)\s*[-:]\s*(\d+)', raw)
        if m:
            start_r, end_r = int(m.group(1)), int(m.group(2))
            if start_r > end_r:
                start_r, end_r = end_r, start_r
            rolls = [str(r) for r in range(start_r, end_r + 1)]
            run_ctg_scraper(rolls)
        else:
            print(f"{RED}[!] Invalid range format. Example: 129000-129050{RESET}", flush=True)
    elif choice == "4":
        raw = input(f"\n{BOLD}Enter Roll number(s): {RESET}").strip()
        rolls = [r.strip() for r in re.split(r'[,\s\n]+', raw) if r.strip().isdigit()]
        if rolls:
            run_ctg_scraper(rolls)
    elif choice == "5":
        path = input(f"\n{BOLD}Enter filepath (txt/json): {RESET}").strip().strip('"')
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            items = [r.strip() for r in re.split(r'[,\s\n"\[\]]+', content) if r.strip().isdigit()]
            if items and len(items[0]) == 6:
                t_choice = input(f"Are these EIIN numbers or Candidate Rolls? [E=EIIN, R=Rolls, default E]: ").strip().upper()
                if t_choice == "R":
                    run_ctg_scraper(items)
                else:
                    run_ctg_eiin_scraper(items)
            elif items:
                run_ctg_scraper(items)
        else:
            print(f"{RED}[!] File not found: {path}{RESET}", flush=True)


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    
    if "--eiin" in args:
        e_idx = args.index("--eiin")
        eiin_args = args[e_idx + 1:]
        if eiin_args:
            run_ctg_eiin_scraper(eiin_args)
        else:
            interactive_ctg_menu()
    elif args:
        arg_rolls = []
        for a in args:
            if "-" in a and re.match(r'^\d+-\d+$', a):
                s, e = map(int, a.split("-"))
                arg_rolls.extend([str(x) for x in range(min(s, e), max(s, e) + 1)])
            elif a.isdigit():
                arg_rolls.append(a)
        if arg_rolls:
            run_ctg_scraper(arg_rolls, force_recheck=force_flag)
        else:
            interactive_ctg_menu()
    else:
        interactive_ctg_menu()
