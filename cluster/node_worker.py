"""
Official 5-Node Distributed Worker Engine for Dinajpur Board Scraper
Matches the exact local storing architecture of run.py:
- Auto-detects district folders (results/<DISTRICT_SLUG>/)
- Auto-detects upazilla files (results_upazilla_<upz_slug>.json)
- Instant real-time disk flushes with atomic tmp replacements
- Complete deduplication (skips already scraped rolls)
- Independent proxy rotation & zero-captcha high-speed scraping
"""

import os
import sys
import glob
import json
import time
import queue
import re
import threading
import argparse
import requests
from requests.adapters import HTTPAdapter
from typing import Dict, Any, Optional, List

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from engine.fast_student_scraper import ENDPOINT, parse_student_html
from engine.institute_fetcher import InstituteResultFetcher
from engine.proxy_manager import FastProxyPool

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def format_progress_bar(current: int, total: int, width: int = 18) -> str:
    if total <= 0:
        return f"[{'░' * width}]"
    filled = int(width * current // total)
    return f"[{'█' * filled}{'░' * (width - filled)}]"

def run_node_pipeline(node_id: str, eiin_file: str, num_workers: int = 20):
    results_root = os.path.join(BASE_DIR, "results")
    cache_dir = os.path.join(BASE_DIR, "cache", "institutions")
    os.makedirs(results_root, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    if not os.path.isfile(eiin_file):
        print(f"\n{RED}[!] EIIN file for Node {node_id} not found: {eiin_file}{RESET}")
        print(f"[*] Run 'python cluster/shard_eiins.py' to generate node assignments.\n")
        return

    with open(eiin_file, "r", encoding="utf-8") as f:
        eiins = [l.strip() for l in f if l.strip().isdigit() and len(l.strip()) == 6]

    if not eiins:
        print(f"\n{YELLOW}[!] No valid EIINs found in {eiin_file}{RESET}\n")
        return

    print(f"\n=======================================================")
    print(f"🚀 {BOLD}DISTRIBUTED CLUSTER NODE {node_id.upper()} ACTIVE{RESET}")
    print(f"  • Storage Root:       {results_root}")
    print(f"  • Assigned Schools:   {len(eiins)} Institutions")
    print(f"  • Worker Threads:     {num_workers} Parallel Streams")
    print(f"  • Storage Engine:     Real-time District & Upazilla Auto-Deduplication")
    print(f"=======================================================\n")

    # 1. Pre-load already scraped records map to prevent duplicate work
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

    # 2. Dynamic Proxy Pool with Rolling Socket Refresh
    proxy_pool = FastProxyPool()
    proxies = proxy_pool.load_and_verify(max_candidates=3000, max_valid=60)

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

    proxy_session_wrappers = [{"ip": p, "session": create_proxy_session(p), "uses": 0} for p in proxies]
    wrapper_lock = threading.Lock()

    def get_proxy_session(idx: int) -> requests.Session:
        if not proxy_session_wrappers:
            return requests.Session()
        with wrapper_lock:
            item = proxy_session_wrappers[idx % len(proxy_session_wrappers)]
            item["uses"] += 1
            if item["uses"] >= 25:
                try:
                    item["session"].close()
                except Exception:
                    pass
                item["session"] = create_proxy_session(item["ip"])
                item["uses"] = 0
            return item["session"]

    direct_session = requests.Session()
    direct_session.headers.update({"User-Agent": "Mozilla/5.0", "Connection": "keep-alive"})

    fetcher = InstituteResultFetcher(proxies=proxies)

    def fetch_worker(roll_str: str, worker_idx: int) -> Optional[Dict[str, Any]]:
        if proxy_session_wrappers:
            num_sessions = len(proxy_session_wrappers)
            for offset in range(min(5, num_sessions)):
                sess = get_proxy_session(worker_idx * 5 + offset)
                try:
                    r = sess.get(ENDPOINT.format(roll=roll_str), timeout=2.0)
                    if r.status_code == 200:
                        parsed = parse_student_html(r.text, roll_str)
                        if parsed:
                            return parsed
                except Exception:
                    pass
        try:
            r = direct_session.get(ENDPOINT.format(roll=roll_str), timeout=2.0)
            if r.status_code == 200:
                parsed = parse_student_html(r.text, roll_str)
                if parsed:
                    return parsed
        except Exception:
            pass
        return None

    # Upazilla Storage State
    upazilla_memory = {}
    dirty_upazillas = set()
    last_flush_time = [time.time()]
    file_lock = threading.RLock()
    print_lock = threading.Lock()
    stats_lock = threading.Lock()

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

    rolls_queue = queue.Queue()
    pending_rolls = []
    seen_rolls = set(already_scraped_map.keys())
    roll_metadata_map = {}
    batch_received_count = 0
    total_appeared_count = 0
    already_scraped_count = 0
    harvest_done = threading.Event()
    stop_event = threading.Event()

    # Producer
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
                    pass

            is_cached = bool(inst_data and inst_data.get("name") and "students" in inst_data)
            if not is_cached:
                def on_retry(msg):
                    with print_lock:
                        print(f"  [Node {node_id}] [{idx}/{len(eiins)}] EIIN {eiin} ({YELLOW}{msg[:20]}{RESET})", flush=True)

                inst_data = fetcher.fetch_by_eiin(eiin, status_callback=on_retry)
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
                    print(f"  [Node {node_id}] [{idx}/{len(eiins)}] EIIN {eiin} -> {RED}Not Found{RESET}", flush=True)
                continue

            inst_name = inst_data.get("name", "Unknown")
            district = inst_data.get("district", "Unknown")
            upazila = inst_data.get("upazila", "UNKNOWN")
            students = inst_data.get("students", [])

            appeared_students = [s for s in students if s.get("status") != "ABSENT" and "ABS" not in str(s.get("gpa", "")).upper()]
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
                    print(f"  [Node {node_id}] [{idx}/{len(eiins)}] EIIN {eiin}: {inst_name[:25]} {GREEN}+{queued_for_inst} rolls{RESET}", flush=True)
                    time.sleep(1.2)

        with print_lock:
            print(f"  {GREEN}✓ [Node {node_id}] Loaded {len(eiins)} institutions ({total_appeared_count} rolls, {already_scraped_count} already scraped){RESET}\n", flush=True)

        harvest_done.set()

    first_roll_time = [None]
    last_roll_time = [None]
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

            if item is None:
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
                    cur_target = max(1, len(pending_rolls))

                s_name = res.get("student_name", "STUDENT")
                gpa_res = res.get("result", "N/A")
                is_pass = "GPA" in str(gpa_res)
                status_color = GREEN if is_pass else RED
                status_label = "PASSED" if is_pass else "FAILED"
                p_bar = format_progress_bar(cur_rec, cur_target, width=16)

                with print_lock:
                    print(f"{CYAN}[Node {node_id}]{RESET} {p_bar} {cur_rec:4d}/{cur_target} Roll {roll_str:<7} {s_name:<30} {gpa_res:<10} {status_color}{status_label}{RESET}", flush=True)
            else:
                if attempts < 3 and not stop_event.is_set():
                    rolls_queue.put((roll_str, meta, attempts + 1))

            with active_lock:
                active_count[0] -= 1
            rolls_queue.task_done()

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
        rolls_queue.join()
        for _ in range(num_workers):
            rolls_queue.put(None)
        for t in consumer_threads:
            t.join()
    except KeyboardInterrupt:
        stop_event.set()
        print(f"\n[Node {node_id}] Stopped by user. Preserving all records...")

    flush_dirty_upazillas(force=True)

    print(f"\n{GREEN}{BOLD}✓ [Node {node_id}] Finished! Total {batch_received_count} records saved directly to results/ hierarchy!{RESET}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distributed Cluster Node Worker")
    parser.add_argument("--node", type=str, default="1", help="Node ID (e.g. 1, 2, 3)")
    parser.add_argument("--eiins", type=str, default="", help="Path to eiins.txt file")
    parser.add_argument("--workers", type=int, default=20, help="Parallel worker threads")
    args = parser.parse_args()

    eiin_path = args.eiins or os.path.join(os.path.dirname(__file__), "nodes", f"node_{args.node}", "eiins.txt")
    run_node_pipeline(args.node, eiin_path, args.workers)
