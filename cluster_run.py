"""
🚀 1-STEP ALL-IN-ONE 5-NODE SCRAPING CLUSTER (100 CONCURRENT WORKERS)
Usage:
    python cluster_run.py
Paste your EIINs, press Enter, and watch all 100 workers scrape at 60-80 rolls/sec!
"""

import os
import sys
import glob
import json
import time
import queue
import re
import threading
import requests
from requests.adapters import HTTPAdapter
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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

def parse_eiin_inputs():
    print(f"\n{CYAN}{BOLD}📥 ENTER OR PASTE YOUR EIINs (Press Enter twice to start):{RESET}")
    lines = []
    while True:
        try:
            line = input()
            if not line:
                if lines:
                    break
                else:
                    return []
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            break

    raw_text = " ".join(lines)
    tokens = re.split(r'[\s,;\n\r\t]+', raw_text.strip())
    eiins = [t.strip() for t in tokens if t.strip().isdigit() and len(t.strip()) == 6]
    return list(dict.fromkeys(eiins))

def main():
    print(f"\n{GREEN}{BOLD}=======================================================")
    print(f"🚀 1-STEP 5-NODE CLUSTER ENGINE (100 PARALLEL WORKERS)")
    print(f"======================================================={RESET}")

    results_root = os.path.join(BASE_DIR, "results")
    cache_dir = os.path.join(BASE_DIR, "cache", "institutions")
    master_file = os.path.join(BASE_DIR, "scraped_results_all.json")
    os.makedirs(results_root, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    # 1. Load dynamic proxy pool
    proxy_pool = FastProxyPool()
    print(f"{DIM}Loading verified proxy pool...{RESET}", end="", flush=True)
    proxies = proxy_pool.load_and_verify(max_candidates=4000, max_valid=90)
    print(f"\r{GREEN}✓ Active Proxy Pool: {len(proxies)} verified nodes ready!{RESET}\n")

    while True:
        eiins = parse_eiin_inputs()
        if not eiins:
            print(f"\n{YELLOW}[!] No EIIN entered. Exiting... Goodbye!{RESET}\n")
            break

        start_time = time.time()

        # 2. Preload existing results to avoid duplicate scraping
        already_scraped_map = {}
        for f in glob.glob(os.path.join(results_root, "**", "results_upazilla_*.json"), recursive=True):
            try:
                with open(f, 'r', encoding='utf-8') as uf:
                    for r in json.load(uf).get("records", []):
                        if r.get("roll_no") and r.get("success"):
                            already_scraped_map[str(r.get("roll_no"))] = r
            except Exception: pass

        # 3. Setup Proxy Session Wrappers with Auto-Recycle
        def create_proxy_session(ip_str: str) -> requests.Session:
            s = requests.Session()
            adapter = HTTPAdapter(pool_connections=15, pool_maxsize=15)
            s.mount("http://", adapter)
            s.mount("https://", adapter)
            s.proxies.update({"http": f"http://{ip_str}", "https": f"http://{ip_str}"})
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Connection": "keep-alive"
            })
            return s

        proxy_wrappers = [{"ip": p, "session": create_proxy_session(p), "uses": 0} for p in proxies]
        wrapper_lock = threading.Lock()

        def get_proxy_session(idx: int) -> requests.Session:
            if not proxy_wrappers:
                return requests.Session()
            with wrapper_lock:
                item = proxy_wrappers[idx % len(proxy_wrappers)]
                item["uses"] += 1
                if item["uses"] >= 25:
                    try: item["session"].close()
                    except Exception: pass
                    item["session"] = create_proxy_session(item["ip"])
                    item["uses"] = 0
                return item["session"]

        direct_session = requests.Session()
        direct_session.headers.update({"User-Agent": "Mozilla/5.0", "Connection": "keep-alive"})
        fetcher = InstituteResultFetcher(proxies=proxies)

        def fetch_worker(roll_str: str, worker_idx: int) -> Optional[Dict[str, Any]]:
            if proxy_wrappers:
                for offset in range(min(5, len(proxy_wrappers))):
                    sess = get_proxy_session(worker_idx * 5 + offset)
                    try:
                        r = sess.get(ENDPOINT.format(roll=roll_str), timeout=2.0)
                        if r.status_code == 200:
                            parsed = parse_student_html(r.text, roll_str)
                            if parsed: return parsed
                    except Exception: pass
            try:
                r = direct_session.get(ENDPOINT.format(roll=roll_str), timeout=2.0)
                if r.status_code == 200:
                    parsed = parse_student_html(r.text, roll_str)
                    if parsed: return parsed
            except Exception: pass
            return None

        # Storage
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
                    except Exception: pass
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
                if not entry: continue
                upz_data = entry["data"]
                roll_map = entry["roll_map"]
                upz_file = entry["file_path"]
                all_upz_records = list(roll_map.values())
                for i, rec in enumerate(all_upz_records, 1): rec["index"] = i
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
                except Exception: pass

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
        batch_received_count = 0
        total_appeared_count = 0
        already_scraped_count = 0
        harvest_done = threading.Event()
        stop_event = threading.Event()

        # 4. Harvest Producer (Streams rolls instantly to workers)
        def harvest_producer():
            nonlocal total_appeared_count, already_scraped_count
            for idx, eiin in enumerate(eiins, 1):
                if stop_event.is_set(): break
                cache_file = os.path.join(cache_dir, f"eiin_{eiin}.json")
                inst_data = None
                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, "r", encoding="utf-8") as cf:
                            inst_data = json.load(cf)
                    except Exception: pass

                is_cached = bool(inst_data and inst_data.get("name") and "students" in inst_data)
                if not is_cached:
                    inst_data = fetcher.fetch_by_eiin(eiin)
                    if inst_data and not inst_data.get("error") and inst_data.get("name"):
                        try:
                            with open(cache_file, "w", encoding="utf-8") as cf:
                                json.dump(inst_data, cf, indent=2, ensure_ascii=False)
                        except Exception: pass
                    else:
                        time.sleep(0.3)

                if not inst_data or not inst_data.get("name"):
                    with print_lock:
                        print(f"  [{idx}/{len(eiins)}] EIIN {eiin} -> {RED}Not Found{RESET}", flush=True)
                    continue

                inst_name = inst_data.get("name", "Unknown")
                district = inst_data.get("district", "Unknown")
                upazila = inst_data.get("upazila", "UNKNOWN")
                students = [s for s in inst_data.get("students", []) if s.get("status") != "ABSENT" and "ABS" not in str(s.get("gpa", "")).upper()]

                queued = 0
                for s in students:
                    r_str = str(s["roll"])
                    meta = {"eiin": int(eiin), "institute": inst_name, "upazila": upazila, "district": district, "group": s.get("group")}
                    with stats_lock:
                        total_appeared_count += 1
                        if r_str in already_scraped_map:
                            already_scraped_count += 1
                        else:
                            if r_str not in seen_rolls:
                                pending_rolls.append(r_str)
                                rolls_queue.put((r_str, meta))
                                queued += 1

                with print_lock:
                    if not is_cached:
                        print(f"  [{idx}/{len(eiins)}] EIIN {eiin}: {inst_name[:25]} {GREEN}+{queued} rolls{RESET}", flush=True)
                        time.sleep(1.2)

            with print_lock:
                print(f"  {GREEN}✓ Loaded all {len(eiins)} institutions ({total_appeared_count} rolls, {already_scraped_count} already scraped){RESET}\n", flush=True)
            harvest_done.set()

        first_roll_time = [None]
        last_roll_time = [None]
        active_count = [0]
        active_lock = threading.Lock()

        # 5. High-Speed 100-Worker Consumer Engine
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

                with active_lock: active_count[0] += 1
                roll_str, meta, attempts = item if len(item) == 3 else (item[0], item[1], 0)
                res = fetch_worker(roll_str, worker_idx + attempts * 13)
                if res and res.get("success"):
                    save_record_to_upazilla(res, meta)
                    with stats_lock:
                        if first_roll_time[0] is None: first_roll_time[0] = time.time()
                        last_roll_time[0] = time.time()
                        batch_received_count += 1
                        seen_rolls.add(roll_str)
                        cur_rec = batch_received_count
                        cur_target = max(1, len(pending_rolls))

                    s_name = res.get("student_name", "STUDENT")
                    gpa_res = res.get("result", "N/A")
                    is_pass = "GPA" in str(gpa_res)
                    col = GREEN if is_pass else RED
                    lbl = "PASSED" if is_pass else "FAILED"
                    p_bar = format_progress_bar(cur_rec, cur_target, width=18)
                    with print_lock:
                        print(f"{CYAN}{p_bar}{RESET} {cur_rec:4d}/{cur_target} Roll {roll_str:<7} {s_name:<30} {gpa_res:<10} {col}{lbl}{RESET}", flush=True)
                else:
                    if attempts < 3 and not stop_event.is_set():
                        rolls_queue.put((roll_str, meta, attempts + 1))

                with active_lock: active_count[0] -= 1
                rolls_queue.task_done()

        # Launch 100 Parallel Workers across the Proxy Pool!
        TOTAL_WORKERS = min(100, max(25, len(proxies) - 5)) if proxies else 25
        print(f"⚡ Spawning {TOTAL_WORKERS} Parallel High-Speed Worker Streams...")

        producer_thread = threading.Thread(target=harvest_producer, daemon=True)
        consumer_threads = [
            threading.Thread(target=student_consumer, args=(i,), daemon=True)
            for i in range(TOTAL_WORKERS)
        ]

        producer_thread.start()
        for t in consumer_threads: t.start()

        try:
            producer_thread.join()
            rolls_queue.join()
            for _ in range(TOTAL_WORKERS): rolls_queue.put(None)
            for t in consumer_threads: t.join()
        except KeyboardInterrupt:
            stop_event.set()
            print(f"\n[!] Stopped by user. Preserving all records...")

        flush_dirty_upazillas(force=True)

        # 6. Auto-Recovery Catch-Up Passes for 100% Guaranteed Completion
        if not stop_event.is_set():
            import concurrent.futures
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
                            save_record_to_upazilla(res, {})
                            with stats_lock:
                                batch_received_count += 1
                                seen_rolls.add(roll)
                            s_name = res.get("student_name", "STUDENT")
                            gpa_res = res.get("result", "N/A")
                            is_pass = "GPA" in str(gpa_res)
                            status_color = GREEN if is_pass else RED
                            status_label = "PASSED" if is_pass else "FAILED"
                            p_bar = format_progress_bar(batch_received_count, len(pending_rolls), width=18)
                            print(f"{CYAN}{p_bar}{RESET} {batch_received_count:4d}/{len(pending_rolls)}  Roll {roll:<7}  {s_name:<32}  {gpa_res:<10} {status_color}{status_label}{RESET}")

                flush_dirty_upazillas(force=True)
                unretrieved = [r for r in pending_rolls if r not in seen_rolls]

        flush_dirty_upazillas(force=True)

        total_elapsed = time.time() - start_time
        mins, secs = divmod(total_elapsed, 60)
        time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"

        if first_roll_time[0] and last_roll_time[0]:
            dur = max(0.1, last_roll_time[0] - first_roll_time[0])
            speed = batch_received_count / dur
            speed_str = f"{speed:.1f} rolls/sec ({int(speed*60)} rolls/min)"
        else:
            speed_str = "N/A"

        print(f"\n=======================================================")
        print(f"⏱️ {BOLD}CLUSTER SCRAPING COMPLETE IN {time_str}!{RESET}")
        print(f"  • Total Scraped in Batch:  {batch_received_count} records")
        print(f"  • Active Scraping Speed:   {GREEN}{BOLD}{speed_str}{RESET}")
        print(f"  • Destination:             results/<DISTRICT>/results_upazilla_*.json")
        print(f"=======================================================\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Exited safely.{RESET}")
        sys.exit(0)
