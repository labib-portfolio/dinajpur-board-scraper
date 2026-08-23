"""
Interactive Terminal CLI for Chittagong Education Board (BISE CTG) Result Scraper 2026
Ultra-Fast Concurrent Scraping Engine (with Automatic Proxy Pool & Real-Time Persistence)
Endpoint: https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/result.php
"""

import sys
import os
import re
import json
import time
import queue
import glob
import logging
import threading
import collections
import concurrent.futures
from typing import List, Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

logging.disable(logging.INFO)
logging.basicConfig(level=logging.WARNING)

from engine.ctg_scraper import parse_ctg_student_html, CTG_RESULT_URL, CTG_REFERER

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_ctg_banner():
    print(f"\n{CYAN}┌───────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}Chittagong Board SSC Result Scraper 2026 — High-Speed{RESET}     {CYAN}│{RESET}")
    print(f"{CYAN}├───────────────────────────────────────────────────────────┤{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Direct POST Engine • Full Marksheets • Zero CAPTCHA{RESET}        {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Multi-Threaded Proxy Rotation • Real-Time JSON Export{RESET}     {CYAN}│{RESET}")
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


def create_isolated_session(proxy_ip: Optional[str] = None) -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=5, pool_maxsize=5, max_retries=0)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    if proxy_ip:
        parts = proxy_ip.split(":")
        if len(parts) == 4:
            ip, port, user, pwd = parts
            proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
        else:
            proxy_url = f"http://{proxy_ip}"
        s.proxies.update({"http": proxy_url, "https": proxy_url})
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Origin": "https://sresult.bise-ctg.gov.bd",
        "Referer": CTG_REFERER,
        "Connection": "keep-alive"
    })
    return s


def run_ctg_scraper(rolls: List[str], output_dir: Optional[str] = None, output_name: str = "chittagong_results.json"):
    rolls = sorted(list(dict.fromkeys(str(r).strip() for r in rolls if str(r).strip().isdigit())))
    if not rolls:
        print(f"{RED}[!] No valid 6-digit rolls provided.{RESET}", flush=True)
        return

    out_dir = output_dir or os.path.join(BASE_DIR, "results", "chittagong")
    os.makedirs(out_dir, exist_ok=True)
    master_file = os.path.join(out_dir, output_name)

    proxies = load_proxies()
    print(f"\n=======================================================")
    print(f"🚀 {BOLD}CHITTAGONG SCRAPER PIPELINE CONFIGURATION:{RESET}")
    print(f"  • Target Rolls:        {GREEN}{BOLD}{len(rolls)} Candidate Rolls{RESET}")
    print(f"  • Active Proxy Pool:   {CYAN}{BOLD}{len(proxies)} Dedicated Nodes{RESET}")
    print(f"  • Destination File:    {YELLOW}{master_file}{RESET}")
    print(f"=======================================================\n", flush=True)

    already_scraped = {}
    if os.path.exists(master_file):
        try:
            with open(master_file, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                for r in prev_data.get("records", []):
                    if r.get("roll_no") and r.get("success"):
                        already_scraped[str(r.get("roll_no"))] = r
        except Exception:
            pass

    pending_rolls = [r for r in rolls if r not in already_scraped]
    if len(already_scraped) > 0:
        print(f"  • Already Scraped:     {GREEN}{len(already_scraped)} rolls (Skipping){RESET}")
        print(f"  • Pending to Scrape:   {YELLOW}{len(pending_rolls)} rolls{RESET}\n", flush=True)

    if not pending_rolls:
        print(f"{GREEN}✓ All {len(rolls)} rolls are already scraped and saved!{RESET}", flush=True)
        return

    results_map = dict(already_scraped)
    results_lock = threading.Lock()
    print_lock = threading.Lock()
    stats_lock = threading.Lock()
    recent_completions = collections.deque()
    recent_lock = threading.Lock()

    scraped_count = 0
    first_roll_time = [None]
    last_roll_time = [None]
    batch_start_time = time.time()
    stop_event = threading.Event()

    num_workers = min(30, max(5, len(proxies) if proxies else 10))
    if len(pending_rolls) < num_workers:
        num_workers = len(pending_rolls)

    rolls_queue = queue.Queue()
    for r in pending_rolls:
        rolls_queue.put((r, 1))

    def save_master():
        with results_lock:
            recs = list(results_map.values())
            passed = sum(1 for x in recs if "GPA" in str(x.get("result", "")))
            gpa5 = sum(1 for x in recs if str(x.get("gpa", "")) in ["5.00", "5", "5.0"])
            data = {
                "board": "CHATTOGRAM",
                "summary": {
                    "total_records": len(recs),
                    "total_passed": passed,
                    "total_failed": len(recs) - passed,
                    "total_gpa_5": gpa5,
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "records": recs
            }
            tmp_f = master_file + ".tmp"
            try:
                with open(tmp_f, "w", encoding="utf-8") as out:
                    json.dump(data, out, indent=2, ensure_ascii=False)
                os.replace(tmp_f, master_file)
            except Exception:
                pass

    def worker_loop(worker_id: int):
        nonlocal scraped_count
        p_ip = proxies[worker_id % len(proxies)] if proxies else None
        sess = create_isolated_session(p_ip)
        payload = {"button2": "Submit"}

        while not stop_event.is_set():
            try:
                item = rolls_queue.get(timeout=1.0)
            except queue.Empty:
                break

            if item is None:
                rolls_queue.task_done()
                break

            roll_str, attempt = item
            payload["roll"] = roll_str
            res = None

            for offset in range(3):
                cur_proxy = proxies[(worker_id + offset * 11) % len(proxies)] if proxies else None
                try:
                    s_to_use = create_isolated_session(cur_proxy) if cur_proxy != p_ip else sess
                    r = s_to_use.post(CTG_RESULT_URL, data=payload, timeout=8.0, verify=False)
                    if s_to_use != sess:
                        s_to_use.close()
                    if r.status_code == 200:
                        parsed = parse_ctg_student_html(r.text, roll_str)
                        if parsed and parsed.get("success"):
                            res = parsed
                            break
                        elif parsed and parsed.get("error") == "Record Not Found":
                            res = parsed
                            break
                except Exception:
                    pass

            if res and res.get("success"):
                with results_lock:
                    results_map[roll_str] = res
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

                s_name = res.get("student_name", "STUDENT")
                gpa_res = res.get("result", "N/A")
                is_pass = "GPA" in str(gpa_res)
                st_color = GREEN if is_pass else RED
                st_label = "PASSED" if is_pass else "FAILED"
                pct = (cur_c / max(1, cur_t)) * 100
                elapsed = now_ts - (first_roll_time[0] or now_ts)
                mins, secs = divmod(elapsed, 60)
                time_str = f"{int(mins)}m {int(secs):02d}s"
                p_bar = format_progress_bar(cur_c, cur_t, width=22)

                with print_lock:
                    sys.stdout.write("\r\033[K")
                    print(f" {cur_c:4d}/{cur_t}  Roll {roll_str:<7}  {s_name:<30}  {gpa_res:<10} {st_color}{st_label}{RESET}", flush=True)
                    sys.stdout.write(f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_c}/{cur_t} ({pct:.1f}%) ⚡ {speed:.1f} rolls/s │ ⏱️ {time_str}")
                    sys.stdout.flush()
            else:
                if attempt < 3 and not stop_event.is_set():
                    rolls_queue.put((roll_str, attempt + 1))

            if scraped_count % 15 == 0:
                save_master()

            rolls_queue.task_done()

        try:
            sess.close()
        except Exception:
            pass

    threads = []
    for wid in range(num_workers):
        t = threading.Thread(target=worker_loop, args=(wid,), daemon=True)
        t.start()
        threads.append(t)

    try:
        rolls_queue.join()
        for _ in range(num_workers):
            rolls_queue.put(None)
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        stop_event.set()
        print(f"\n\n{YELLOW}[!] Pipeline interrupted by user. Saved {len(results_map)} records safely!{RESET}", flush=True)

    save_master()
    sys.stdout.write("\n\n")
    sys.stdout.flush()

    total_elapsed = time.time() - batch_start_time
    mins, secs = divmod(total_elapsed, 60)
    time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"

    print(f"=======================================================")
    print(f"🎉 {GREEN}{BOLD}CHITTAGONG BOARD SCRAPING COMPLETE!{RESET}")
    print(f"  • Total Rolls Processed:  {len(results_map)}")
    print(f"  • Total Time Elapsed:     {CYAN}{time_str}{RESET}")
    print(f"  • Output File:            {GREEN}{master_file}{RESET}")
    print(f"=======================================================\n", flush=True)


def interactive_ctg_menu():
    print_ctg_banner()
    print(f"{BOLD}Select Chittagong Board Scraping Mode:{RESET}")
    print(f"  {CYAN}[1]{RESET} Single / Comma-Separated Candidate Rolls (e.g. 129051, 129052)")
    print(f"  {CYAN}[2]{RESET} Roll Number Range (e.g. 129000-129100)")
    print(f"  {CYAN}[3]{RESET} Upazila / Zilla Selector (from chittagong_board_eiin dataset)")
    print(f"  {CYAN}[4]{RESET} Load Rolls from File (txt/json)")
    print(f"  {CYAN}[0]{RESET} Exit\n", flush=True)

    choice = input(f"{BOLD}Enter choice [1-4]: {RESET}").strip()

    if choice == "1":
        raw = input(f"\n{BOLD}Enter Roll number(s): {RESET}").strip()
        rolls = [r.strip() for r in re.split(r'[,\s\n]+', raw) if r.strip().isdigit()]
        if rolls:
            run_ctg_scraper(rolls)
    elif choice == "2":
        raw = input(f"\n{BOLD}Enter Roll Range (e.g. 129000-129050): {RESET}").strip()
        m = re.match(r'(\d+)\s*[-:]\s*(\d+)', raw)
        if m:
            start_r, end_r = int(m.group(1)), int(m.group(2))
            if start_r > end_r:
                start_r, end_r = end_r, start_r
            rolls = [str(r) for r in range(start_r, end_r + 1)]
            run_ctg_scraper(rolls, output_name=f"ctg_range_{start_r}_{end_r}.json")
        else:
            print(f"{RED}[!] Invalid range format. Example: 129000-129050{RESET}", flush=True)
    elif choice == "3":
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
            for i, uf in enumerate(upz_files, 1):
                u_name = os.path.splitext(os.path.basename(uf))[0]
                print(f"  [{i}] {u_name}")
            u_choice = input(f"Select Upazila [1-{len(upz_files)}]: ").strip()
            if u_choice.isdigit() and 1 <= int(u_choice) <= len(upz_files):
                selected_upz_file = upz_files[int(u_choice) - 1]
                upz_name = os.path.splitext(os.path.basename(selected_upz_file))[0]
                print(f"\n{GREEN}Selected: {selected_z} -> {upz_name}{RESET}", flush=True)
                raw_r = input(f"{BOLD}Enter roll range for this center (e.g. 129000-129100): {RESET}").strip()
                m = re.match(r'(\d+)\s*[-:]\s*(\d+)', raw_r)
                if m:
                    start_r, end_r = int(m.group(1)), int(m.group(2))
                    rolls = [str(r) for r in range(start_r, end_r + 1)]
                    out_d = os.path.join(BASE_DIR, "results", "chittagong", selected_z)
                    run_ctg_scraper(rolls, output_dir=out_d, output_name=f"{upz_name}_results.json")
    elif choice == "4":
        path = input(f"\n{BOLD}Enter filepath (txt/json): {RESET}").strip().strip('"')
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            rolls = [r.strip() for r in re.split(r'[,\s\n"\[\]]+', content) if r.strip().isdigit()]
            if rolls:
                run_ctg_scraper(rolls)
        else:
            print(f"{RED}[!] File not found: {path}{RESET}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg_rolls = []
        for a in sys.argv[1:]:
            if "-" in a and re.match(r'^\d+-\d+$', a):
                s, e = map(int, a.split("-"))
                arg_rolls.extend([str(x) for x in range(min(s, e), max(s, e) + 1)])
            elif a.isdigit():
                arg_rolls.append(a)
        if arg_rolls:
            run_ctg_scraper(arg_rolls)
        else:
            interactive_ctg_menu()
    else:
        interactive_ctg_menu()
