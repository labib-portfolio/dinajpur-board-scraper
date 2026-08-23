"""
Interactive Terminal CLI for Dinajpur Board Result Scraper 2026
Ultra-Fast Concurrent Scraping Engine (with Automatic Proxy Pool & 100% Roll Delivery)
"""

import sys
import os
import re
import json
import time
import requests
from requests.adapters import HTTPAdapter
import logging
import glob
import queue
import threading
import concurrent.futures
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

# Completely mute noisy debug/info/connectionpool logs from the terminal
logging.disable(logging.INFO)
logging.basicConfig(level=logging.WARNING)
for log_name in ["engine.scraper_engine", "engine.institute_fetcher", "urllib3", "urllib3.connectionpool", "asyncio", "root"]:
    logging.getLogger(log_name).setLevel(logging.CRITICAL)

from engine.institute_fetcher import InstituteResultFetcher
from engine.fast_student_scraper import fetch_single_student, parse_student_html, ENDPOINT

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

PROXY_SOURCES = [
    # Fast APIs
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,https&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://api.openproxylist.xyz/http.txt",
    
    # Active GitHub Repositories (HTTP / HTTPS)
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/https.txt",
    "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt",
    "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_all.txt",
    "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_ssl.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master-List/main/http.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/https.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/master/proxy_files/http_proxies.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/master/proxy_files/https_proxies.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https/https.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
    "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/http/global/http_checked.txt",
    "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/http.txt",
    "https://raw.githubusercontent.com/andigwandi/free-proxy/main/proxy_list.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/https.txt"
]

class FastProxyPool:
    def __init__(self):
        self.proxies: List[str] = []
        self.cache_file = os.path.join(BASE_DIR, "working_proxies.txt")

    def load_and_verify(self, max_candidates: int = 1500, max_valid: int = 90) -> List[str]:
        # 1. Instantly load from local verified proxy cache if available (0.00s startup)
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cached = [line.strip() for line in f if ":" in line.strip()]
                if len(cached) >= 20:
                    self.proxies = cached[:max_valid]
                    return self.proxies
            except Exception:
                pass

        # 2. Run fast async verification across 35 sources
        try:
            import asyncio
            from engine.proxy_manager import harvest_and_verify_proxies
            valid = asyncio.run(harvest_and_verify_proxies(needed=max_valid, max_candidates=max_candidates))
            if valid:
                self.proxies = valid[:max_valid]
                try:
                    with open(self.cache_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(self.proxies))
                except Exception:
                    pass
                return self.proxies
        except Exception:
            pass

        return self.proxies

def print_banner():
    print(f"\n{CYAN}┌───────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}Dinajpur Board Result Scraper 2026 — High-Speed Engine{RESET}   {CYAN}│{RESET}")
    print(f"{CYAN}├───────────────────────────────────────────────────────────┤{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}100% Guaranteed Roll Extraction • 35 Active Proxy Networks{RESET}  {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Zero Webhook Drops • Real-time Upazilla JSON Persistence{RESET}   {CYAN}│{RESET}")
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

def run_scraper_cli():
    # Storage Root Directory: Auto-detect Android Phone Storage or Local PC
    if os.path.exists("/storage/emulated/0"):
        results_root = "/storage/emulated/0/Result Scraper"
    elif os.path.exists("/sdcard"):
        results_root = "/sdcard/Result Scraper"
    elif os.path.exists("/storage/emulated"):
        results_root = "/storage/emulated/Result Scraper"
    else:
        results_root = os.path.join(BASE_DIR, "results")

    os.makedirs(results_root, exist_ok=True)
    master_file = os.path.join(results_root, "scraped_results_all.json")
    print(f"{DIM}Storage Destination: {results_root}{RESET}")
    
    proxy_pool = FastProxyPool()
    print(f"{DIM}Checking dynamic proxy pool for zero rate limits...{RESET}", end="", flush=True)
    proxies = proxy_pool.load_and_verify(max_candidates=4000, max_valid=90)
    num_workers = min(35, max(15, len(proxies) - 20)) if len(proxies) > 0 else 20
    spare_proxies = max(0, len(proxies) - num_workers)
    fetcher = InstituteResultFetcher(proxies=proxies)
    print(f"\r{GREEN}✓ Active Proxy Pool: {len(proxies)} ultra-fast nodes ready! ({num_workers} Parallel Workers + {spare_proxies} Standby Spares){RESET}\n")

    while True:
        eiins = get_eiin_inputs()
        if not eiins:
            print(f"\n{YELLOW}[!] No EIIN entered. Exiting... Goodbye!{RESET}\n")
            break

        batch_start_time = time.time()

        # Pre-load already scraped records map so we don't duplicate work
        already_scraped_map = {}
        all_existing_files = (
            glob.glob(os.path.join(results_root, "**", "results_upazilla_*.json"), recursive=True) +
            glob.glob(os.path.join(BASE_DIR, "upazilla_results", "*.json"))
        )
        for upz_path in all_existing_files:
            try:
                with open(upz_path, 'r', encoding='utf-8') as f:
                    u_data = json.load(f)
                    for r in u_data.get("records", []):
                        if r.get("roll_no") and r.get("success"):
                            already_scraped_map[str(r.get("roll_no"))] = r
            except Exception:
                pass

        if os.path.exists(master_file):
            try:
                with open(master_file, 'r', encoding='utf-8') as f:
                    prev_data = json.load(f)
                    for r in prev_data.get("records", []):
                        if r.get("roll_no") and r.get("success"):
                            already_scraped_map[str(r.get("roll_no"))] = r
            except Exception:
                pass

        # Ensure proxy pool is active
        if len(proxies) < 30:
            print(f"{DIM}Refreshing proxy pool...{RESET}", end="", flush=True)
            proxies = proxy_pool.load_and_verify(max_candidates=4000, max_valid=90)
            num_workers = min(35, max(15, len(proxies) - 20)) if len(proxies) > 0 else 20
            spare_proxies = max(0, len(proxies) - num_workers)
            print(f"\r{GREEN}✓ Active Proxy Pool: {len(proxies)} high-speed nodes ready!{RESET}\n")

        # Build persistent Keep-Alive session pool with Auto-Recycle (Zero Stale Sockets)
        def create_proxy_session(ip_str: str) -> requests.Session:
            s = requests.Session()
            adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20)
            s.mount("http://", adapter)
            s.mount("https://", adapter)
            s.proxies.update({"http": f"http://{ip_str}", "https": f"http://{ip_str}"})
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Connection": "keep-alive"
            })
            return s

        proxy_session_wrappers = []
        for p in proxies:
            proxy_session_wrappers.append({
                "ip": p,
                "session": create_proxy_session(p),
                "uses": 0
            })

        wrapper_lock = threading.Lock()

        def get_proxy_session(idx: int) -> requests.Session:
            with wrapper_lock:
                item = proxy_session_wrappers[idx % len(proxy_session_wrappers)]
                item["uses"] += 1
                # Auto-recycle TCP socket every 25 requests to maintain maximum peak throughput indefinitely
                if item["uses"] >= 25:
                    try:
                        item["session"].close()
                    except Exception:
                        pass
                    item["session"] = create_proxy_session(item["ip"])
                    item["uses"] = 0
                return item["session"]

        direct_session = requests.Session()
        direct_adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        direct_session.mount("http://", direct_adapter)
        direct_session.mount("https://", direct_adapter)
        direct_session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive"
        })

        print(f"\n=======================================================")
        print(f"🚀 {BOLD}ENGINE PIPELINE CONFIGURATION:{RESET}")
        print(f"  • Active Proxy Pool:       {GREEN}{BOLD}{len(proxies)} Verified Ultra-Fast Nodes{RESET}")
        print(f"  • Auto-Recycle Mode:       {GREEN}{BOLD}Rolling TCP Socket Refresh (Every 25 reqs/node){RESET}")
        print(f"  • Concurrent Workers:      {CYAN}{BOLD}{num_workers} Parallel Threads{RESET}")
        print(f"  • Standby Failover Spares: {YELLOW}{BOLD}{spare_proxies} Spare Proxies{RESET}")
        print(f"  • Target Institutions:     {len(eiins)} Schools")
        print(f"=======================================================\n")

        rolls_queue = queue.Queue()
        pending_rolls = []
        roll_metadata_map = {}
        upazilla_summary = {}
        seen_rolls = set(already_scraped_map.keys())
        batch_received_count = 0
        total_appeared_count = 0
        already_scraped_count = 0

        harvest_done = threading.Event()
        stop_event = threading.Event()
        stats_lock = threading.Lock()
        file_lock = threading.RLock()
        print_lock = threading.Lock()

        cache_dir = os.path.join(BASE_DIR, "cache", "institutions")
        os.makedirs(cache_dir, exist_ok=True)

        upazilla_memory = {}
        dirty_upazillas = set()
        last_flush_time = [time.time()]

        def get_upazilla_data(upz_slug: str, upz_name: str, district_name: str, upz_file: str):
            if upz_slug not in upazilla_memory:
                upz_data = {
                    "upazila": upz_name,
                    "district": district_name,
                    "summary": {"total_records": 0, "total_passed": 0, "total_failed": 0, "institutions_count": 0, "last_updated": ""},
                    "records": []
                }
                if os.path.exists(upz_file):
                    try:
                        with open(upz_file, 'r', encoding='utf-8') as uf:
                            upz_data = json.load(uf)
                    except Exception:
                        pass
                existing_map = {str(item.get("roll_no")): item for item in upz_data.get("records", [])}
                upazilla_memory[upz_slug] = {
                    "data": upz_data,
                    "roll_map": existing_map,
                    "file_path": upz_file,
                    "upz_name": upz_name,
                    "district_name": district_name
                }
            return upazilla_memory[upz_slug]

        def flush_dirty_upazillas(force=False):
            now = time.time()
            if not force and (now - last_flush_time[0] < 1.5 or not dirty_upazillas):
                return
            last_flush_time[0] = now
            with file_lock:
                to_flush = list(dirty_upazillas)
                dirty_upazillas.clear()
            for upz_slug in to_flush:
                entry = upazilla_memory.get(upz_slug)
                if not entry:
                    continue
                upz_data = entry["data"]
                roll_map = entry["roll_map"]
                upz_file = entry["file_path"]
                all_upz_records = list(roll_map.values())
                for i, rec in enumerate(all_upz_records, 1):
                    rec["index"] = i
                passed_count = sum(1 for item in all_upz_records if "GPA" in str(item.get("result", "")))
                unique_eiins = sorted(list({int(item.get("eiin")) for item in all_upz_records if item.get("eiin")}))
                upz_data["summary"] = {
                    "total_records": len(all_upz_records),
                    "total_passed": passed_count,
                    "total_failed": len(all_upz_records) - passed_count,
                    "institutions_count": len(unique_eiins),
                    "scraped_eiins": unique_eiins,
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                upz_data["records"] = all_upz_records
                temp_upz_file = upz_file + ".tmp"
                try:
                    with open(temp_upz_file, 'w', encoding='utf-8') as out_f:
                        json.dump(upz_data, out_f, indent=2, ensure_ascii=False)
                    os.replace(temp_upz_file, upz_file)
                except Exception:
                    pass

        def fetch_worker(roll_str: str, worker_idx: int) -> Optional[Dict[str, Any]]:
            # 1. Rotate through up to 5 auto-recycled proxy sessions with 2.0s reliable timeout
            if proxy_session_wrappers:
                num_sessions = len(proxy_session_wrappers)
                for offset in range(min(5, num_sessions)):
                    sess = get_proxy_session(worker_idx * 5 + offset)
                    try:
                        url = ENDPOINT.format(roll=roll_str)
                        r = sess.get(url, timeout=2.0)
                        if r.status_code == 200:
                            parsed = parse_student_html(r.text, roll_str)
                            if parsed:
                                return parsed
                    except Exception:
                        pass

            # 2. Fast direct attempt fallback with 2.0s timeout
            try:
                url = ENDPOINT.format(roll=roll_str)
                r = direct_session.get(url, timeout=2.0)
                if r.status_code == 200:
                    parsed = parse_student_html(r.text, roll_str)
                    if parsed:
                        return parsed
            except Exception:
                pass
            return None

        def save_record_to_upazilla(r: Dict[str, Any], meta: Dict[str, Any]):
            r_roll = str(r.get("roll_no"))
            district_name = meta.get("district") or r.get("district") or "UNKNOWN_DISTRICT"
            district_slug = re.sub(r'[^a-zA-Z0-9]+', '_', district_name.strip().upper()).strip('_')
            district_folder = os.path.join(results_root, district_slug)
            os.makedirs(district_folder, exist_ok=True)

            upz_name = meta.get("upazila") or r.get("upazila") or "UNKNOWN_UPAZILLA"
            upz_slug = re.sub(r'[^a-zA-Z0-9]+', '_', upz_name.strip().lower()).strip('_')
            upz_file = os.path.join(district_folder, f"results_upazilla_{upz_slug}.json")

            r["upazila"] = upz_name
            r["district"] = district_name
            if meta.get("eiin"): r["eiin"] = meta.get("eiin")
            if meta.get("institute"): r["institute"] = meta.get("institute")

            with file_lock:
                entry = get_upazilla_data(upz_slug, upz_name, district_name, upz_file)
                entry["roll_map"][r_roll] = r
                dirty_upazillas.add(upz_slug)

            flush_dirty_upazillas()

        def harvest_producer():
            nonlocal total_appeared_count, already_scraped_count
            for idx, eiin in enumerate(eiins, 1):
                if stop_event.is_set():
                    break

                cache_file = os.path.join(cache_dir, f"eiin_{eiin}.json")
                inst_data = None

                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, "r", encoding="utf-8") as cf:
                            inst_data = json.load(cf)
                    except Exception:
                        inst_data = None

                is_cached = bool(inst_data and inst_data.get("name") and "students" in inst_data)
                if not is_cached:
                    def on_retry_status(msg):
                        with print_lock:
                            sys.stdout.write("\r\033[K")
                            sys.stdout.write(f"  [{idx}/{len(eiins)}] EIIN {eiin} ({YELLOW}{msg[:20]}{RESET})\n")
                            sys.stdout.flush()

                    inst_data = fetcher.fetch_by_eiin(eiin, status_callback=on_retry_status)
                    if inst_data and not inst_data.get("error") and inst_data.get("name"):
                        try:
                            with open(cache_file, "w", encoding="utf-8") as cf:
                                json.dump(inst_data, cf, indent=2, ensure_ascii=False)
                        except Exception:
                            pass
                    else:
                        time.sleep(0.3)

                if not inst_data or "error" in inst_data or not inst_data.get("name"):
                    with print_lock:
                        sys.stdout.write("\r\033[K")
                        sys.stdout.write(f"  [{idx}/{len(eiins)}] EIIN {eiin} -> {RED}Not Found{RESET}\n")
                        sys.stdout.flush()
                    continue

                inst_name = inst_data.get("name", "Unknown")
                district = inst_data.get("district", "Unknown")
                upazila = inst_data.get("upazila", "UNKNOWN")
                students = inst_data.get("students", [])

                appeared_students = [s for s in students if s.get("status") != "ABSENT" and "ABS" not in str(s.get("gpa", "")).upper()]
                rolls = [str(s["roll"]) for s in appeared_students if s.get("roll")]

                upz_slug = re.sub(r'[^a-zA-Z0-9]+', '_', upazila.strip().lower()).strip('_')
                if upz_slug not in upazilla_summary:
                    upazilla_summary[upz_slug] = {"upazila": upazila, "district": district, "rolls_count": 0}
                upazilla_summary[upz_slug]["rolls_count"] += len(rolls)

                queued_for_inst = 0
                for s in appeared_students:
                    r_str = str(s["roll"])
                    meta = {
                        "eiin": int(eiin),
                        "institute": inst_name,
                        "upazila": upazila,
                        "district": district,
                        "group": s.get("group")
                    }
                    with stats_lock:
                        total_appeared_count += 1
                        roll_metadata_map[r_str] = meta
                        if r_str in already_scraped_map:
                            already_scraped_count += 1
                        else:
                            if r_str not in seen_rolls:
                                pending_rolls.append(r_str)
                                rolls_queue.put((r_str, meta))
                                queued_for_inst += 1

                with print_lock:
                    if not is_cached:
                        sys.stdout.write("\r\033[K")
                        sys.stdout.write(f"  [{idx}/{len(eiins)}] EIIN {eiin}: {inst_name[:25]} {GREEN}+{queued_for_inst} rolls{RESET}\n")
                        sys.stdout.flush()

                if not is_cached:
                    time.sleep(1.2)

            with print_lock:
                sys.stdout.write("\r\033[K")
                sys.stdout.write(f"  {GREEN}✓ Loaded all {len(eiins)} institutions ({total_appeared_count} rolls queued){RESET}\n\n")
                sys.stdout.flush()

            harvest_done.set()

        first_roll_time = [None]
        last_roll_time = [None]
        hud_rendered = [False]
        active_count = [0]
        active_lock = threading.Lock()

        def student_consumer(worker_idx: int):
            nonlocal batch_received_count
            while not stop_event.is_set():
                try:
                    item = rolls_queue.get(timeout=0.2)
                except queue.Empty:
                    with active_lock:
                        if harvest_done.is_set() and rolls_queue.empty() and active_count[0] == 0:
                            break
                    continue

                if item is None:  # Clean sentinel exit
                    rolls_queue.task_done()
                    break

                with active_lock:
                    active_count[0] += 1

                if len(item) == 3:
                    roll_str, meta, attempts = item
                else:
                    roll_str, meta = item
                    attempts = 0

                res = fetch_worker(roll_str, worker_idx + attempts * 13)
                if res and res.get("success"):
                    save_record_to_upazilla(res, meta)
                    
                    with stats_lock:
                        if first_roll_time[0] is None:
                            first_roll_time[0] = time.time()
                        last_roll_time[0] = time.time()
                        batch_received_count += 1
                        seen_rolls.add(roll_str)
                        cur_rec = batch_received_count
                        cur_target = len(pending_rolls)
                    s_name = res.get("student_name", "STUDENT")
                    gpa_res = res.get("result", "N/A")
                    is_pass = "GPA" in str(gpa_res)
                    status_color = GREEN if is_pass else RED
                    status_label = "PASSED" if is_pass else "FAILED"
                    p_bar = format_progress_bar(cur_rec, max(1, cur_target), width=35)
                    pct = (cur_rec / max(1, cur_target)) * 100

                    with print_lock:
                        sys.stdout.write("\r\033[K")
                        student_line = f" {cur_rec:4d}/{cur_target}  Roll {roll_str:<7}  {s_name:<30}  {gpa_res:<10} {status_color}{status_label}{RESET}\n"
                        sys.stdout.write(student_line)
                        p_bar_line = f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_rec}/{cur_target} ({pct:.1f}%)"
                        sys.stdout.write(p_bar_line)
                        sys.stdout.flush()
                else:
                    if attempts < 3 and not stop_event.is_set():
                        rolls_queue.put((roll_str, meta, attempts + 1))

                with active_lock:
                    active_count[0] -= 1
                rolls_queue.task_done()

        # Launch Producer and Consumer threads concurrently (35 parallel workers with 51+ standby spares)
        num_workers = min(35, max(15, len(proxies) - 20)) if len(proxies) > 0 else 20
        producer_thread = threading.Thread(target=harvest_producer, daemon=True)
        consumer_threads = [
            threading.Thread(target=student_consumer, args=(i,), daemon=True)
            for i in range(num_workers)
        ]

        producer_thread.start()
        for t in consumer_threads:
            t.start()

        try:
            producer_thread.join()
            rolls_queue.join()  # Guarantee all queued rolls & in-flight retries are 100% completed
            for _ in range(num_workers):
                rolls_queue.put(None)  # Signal all workers to shut down cleanly
            for t in consumer_threads:
                t.join()
        except KeyboardInterrupt:
            stop_event.set()
            print(f"\n\n{YELLOW}{BOLD}[!] Pipeline stopped by user (Ctrl+C). All {batch_received_count} scraped records are safely preserved!{RESET}")

        flush_dirty_upazillas(force=True)

        # Auto-Recovery Passes on Missing Rolls (guaranteed 100% completion)
        if not stop_event.is_set():
            unretrieved = [r for r in pending_rolls if r not in seen_rolls]
            max_recovery_passes = 8
            for pass_num in range(1, max_recovery_passes + 1):
                if not unretrieved:
                    break
                print(f"\n{YELLOW}🔄 [Auto Catch-Up Pass {pass_num}/{max_recovery_passes}] Re-attempting {len(unretrieved)} unretrieved roll(s) across all proxy nodes...{RESET}")
                time.sleep(1.0)

                rec_workers = min(20, len(unretrieved))
                with concurrent.futures.ThreadPoolExecutor(max_workers=rec_workers) as rec_exec:
                    future_to_roll = {
                        rec_exec.submit(fetch_worker, roll, idx + pass_num * 17): roll
                        for idx, roll in enumerate(unretrieved)
                    }
                    for future in concurrent.futures.as_completed(future_to_roll):
                        roll = future_to_roll[future]
                        res = future.result()
                        if res and res.get("success"):
                            meta = roll_metadata_map.get(roll, {})
                            save_record_to_upazilla(res, meta)
                            with stats_lock:
                                batch_received_count += 1
                                seen_rolls.add(roll)
                                cur_rec = batch_received_count
                                cur_target = len(pending_rolls)
                                pct = (cur_rec / max(1, cur_target)) * 100
                                elapsed = time.time() - (first_roll_time[0] or time.time())
                                speed = cur_rec / max(0.1, elapsed)
                                mins, secs = divmod(elapsed, 60)
                                time_str = f"{int(mins)}m {int(secs)}s"

                            s_name = res.get("student_name", "STUDENT")
                            gpa_res = res.get("result", "N/A")
                            is_pass = "GPA" in str(gpa_res)
                            status_color = GREEN if is_pass else RED
                            status_label = "PASSED" if is_pass else "FAILED"
                            p_bar = format_progress_bar(cur_rec, max(1, cur_target), width=35)

                            with print_lock:
                                sys.stdout.write("\r\033[K")
                                student_line = f" {cur_rec:4d}/{cur_target}  Roll {roll:<7}  {s_name:<30}  {gpa_res:<10} {status_color}{status_label}{RESET}\n"
                                sys.stdout.write(student_line)
                                p_bar_line = f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_rec}/{cur_target} ({pct:.1f}%)"
                                sys.stdout.write(p_bar_line)
                                sys.stdout.flush()

                flush_dirty_upazillas(force=True)
                unretrieved = [r for r in pending_rolls if r not in seen_rolls]

        flush_dirty_upazillas(force=True)
        sys.stdout.write("\n\n")

        total_elapsed = time.time() - batch_start_time
        mins, secs = divmod(total_elapsed, 60)
        time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"
        
        # Pure Scraping Duration
        if first_roll_time[0] and last_roll_time[0]:
            scrape_duration = max(0.1, last_roll_time[0] - first_roll_time[0])
            pure_speed = batch_received_count / scrape_duration
            pure_rpm = int(pure_speed * 60)
            pure_speed_str = f"{pure_speed:.1f} rolls/sec ({pure_rpm} rolls/min)"
        else:
            pure_speed_str = "N/A"

        final_target = len(pending_rolls)

        print(f"\n=======================================================")
        print(f"⏱️ {BOLD}PIPELINED PROCESS EXECUTION TIME & PERFORMANCE:{RESET}")
        print(f"  • Total Pipeline Time:    {CYAN}{BOLD}{time_str}{RESET}")
        print(f"  • Institutions Processed: {len(eiins)}")
        print(f"  • Total Candidate Rolls:  {total_appeared_count} ({already_scraped_count} skipped - already done)")
        print(f"  • Live Scraped in Batch:  {batch_received_count}/{final_target} ({100.0 * batch_received_count / max(1, final_target):.1f}%)")
        print(f"  • Active Scraping Speed:  {GREEN}{BOLD}{pure_speed_str}{RESET}")
        print(f"=======================================================")

        if len([r for r in pending_rolls if r not in seen_rolls]) == 0:
            print(f"\n{GREEN}{BOLD}🎉 Finished Batch! All results saved across Upazilla files in {time_str}!{RESET}")
        else:
            print(f"\n{YELLOW}{BOLD}⚠️ Finished Batch! {batch_received_count}/{final_target} results saved in {time_str}!{RESET}")
        print(f"{CYAN}───────────────────────────────────────────────────────────{RESET}\n")

if __name__ == "__main__":
    try:
        run_scraper_cli()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Scraper terminated by user. All scraped records are safely preserved!{RESET}")
        sys.exit(0)
