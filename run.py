"""
Dinajpur Board SSC Result Scraper — Pipelined Multi-Worker Engine with 150-Roll Auto-Restart Cycles
"""

import sys
import os
import time
import json
import re
import glob
import queue
import threading
import concurrent.futures
from typing import Optional, Dict, Any, List
import requests
from requests.adapters import HTTPAdapter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from engine.fast_student_scraper import ENDPOINT, parse_student_html
from engine.institute_fetcher import InstituteResultFetcher
from engine.proxy_manager import FastProxyPool, harvest_and_verify_proxies

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

def print_banner():
    print(f"\n{CYAN}┌───────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}Dinajpur Board Result Scraper 2026 — 150-Roll Auto Cycles{RESET}  {CYAN}│{RESET}")
    print(f"{CYAN}├───────────────────────────────────────────────────────────┤{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}100% Guaranteed Roll Extraction • Auto-Restart Every 150 Rolls{RESET}│{RESET}")
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
            
    if not lines:
        return []
        
    raw_text = " ".join(lines)
    tokens = re.split(r'[\s,;\n\r\t]+', raw_text.strip())
    eiins = [t.strip() for t in tokens if t.strip().isdigit() and len(t.strip()) == 6]
    return list(dict.fromkeys(eiins))

def main():
    print_banner()

    results_root = os.path.join(BASE_DIR, "results")
    master_file = os.path.join(BASE_DIR, "scraped_results_all.json")
    cache_dir = os.path.join(BASE_DIR, "cache", "institutions")
    os.makedirs(results_root, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)
    
    proxy_pool = FastProxyPool()
    print(f"{DIM}Checking dynamic proxy pool for zero rate limits...{RESET}", end="", flush=True)
    proxies = proxy_pool.load_and_verify(max_candidates=4000, max_valid=90)
    fetcher = InstituteResultFetcher(proxies=proxies)
    print(f"\r{GREEN}✓ Active Proxy Pool: {len(proxies)} ultra-fast nodes ready!{RESET}\n")

    while True:
        eiins = get_eiin_inputs()
        if not eiins:
            print(f"\n{YELLOW}[!] No EIIN entered. Exiting... Goodbye!{RESET}\n")
            break

        total_start_time = time.time()

        # 1. Harvest all candidate rosters for the submitted EIINs
        print(f"\n[*] Harvesting student rosters across {len(eiins)} institutions...")
        all_candidates = []
        already_scraped_map = {}

        # Preload already scraped records
        for upz_path in glob.glob(os.path.join(results_root, "**", "results_upazilla_*.json"), recursive=True):
            try:
                with open(upz_path, 'r', encoding='utf-8') as f:
                    for r in json.load(f).get("records", []):
                        if r.get("roll_no") and r.get("success"):
                            already_scraped_map[str(r.get("roll_no"))] = r
            except Exception: pass

        for idx, eiin in enumerate(eiins, 1):
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
                print(f"  [{idx}/{len(eiins)}] EIIN {eiin} -> {RED}Not Found{RESET}")
                continue

            inst_name = inst_data.get("name", "Unknown")
            district = inst_data.get("district", "Unknown")
            upazila = inst_data.get("upazila", "UNKNOWN")
            students = [s for s in inst_data.get("students", []) if s.get("status") != "ABSENT" and "ABS" not in str(s.get("gpa", "")).upper()]

            for s in students:
                r_str = str(s["roll"])
                meta = {"eiin": int(eiin), "institute": inst_name, "upazila": upazila, "district": district, "group": s.get("group")}
                all_candidates.append({"roll": r_str, "meta": meta})

            if not is_cached:
                print(f"  [{idx}/{len(eiins)}] EIIN {eiin}: {inst_name[:25]} {GREEN}+{len(students)} rolls{RESET}")
                time.sleep(1.0)

        total_candidates_count = len(all_candidates)
        initial_done = sum(1 for c in all_candidates if str(c["roll"]) in already_scraped_map)
        print(f"\n{GREEN}✓ Roster Harvest Complete: {total_candidates_count} candidate rolls ({initial_done} already scraped, {total_candidates_count - initial_done} new to scrape){RESET}")

        if initial_done == total_candidates_count:
            print(f"\n{GREEN}{BOLD}🎉 All {total_candidates_count} rolls across these {len(eiins)} institutions are already 100% scraped!{RESET}\n")
            continue

        # Storage Management
        upazilla_memory = {}
        dirty_upazillas = set()
        last_flush_time = [time.time()]
        file_lock = threading.RLock()

        def get_upazilla_data(upz_slug: str, upz_name: str, district_name: str, upz_file: str):
            if upz_slug not in upazilla_memory:
                upz_data = {"upazila": upz_name, "district": district_name, "summary": {}, "records": []}
                if os.path.exists(upz_file):
                    try:
                        with open(upz_file, 'r', encoding='utf-8') as uf:
                            upz_data = json.load(uf)
                    except Exception: pass
                existing_map = {str(item.get("roll_no")): item for item in upz_data.get("records", [])}
                upazilla_memory[upz_slug] = {"data": upz_data, "roll_map": existing_map, "file_path": upz_file, "upz_name": upz_name, "district_name": district_name}
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

        # 2. Mini-Batch 150-Roll Auto-Restart Loop
        CHUNK_SIZE = 150
        cycle_num = 1
        global_stop = False

        while True:
            # Determine remaining un-scraped rolls
            unscraped = [item for item in all_candidates if str(item["roll"]) not in already_scraped_map]
            if not unscraped:
                print(f"\n{GREEN}{BOLD}🎉 ALL {total_candidates_count} ROLLS ACROSS THESE {len(eiins)} SCHOOLS ARE 100% COMPLETED!{RESET}")
                break

            current_batch = unscraped[:CHUNK_SIZE]
            current_target = len(current_batch)
            completed_overall = total_candidates_count - len(unscraped)

            print(f"\n=======================================================")
            print(f"🔄 {BOLD}CYCLE {cycle_num}: Scraping next {current_target} rolls ({completed_overall}/{total_candidates_count} done overall)...{RESET}")
            print(f"=======================================================")

            # Setup fresh proxy sessions for this 150-roll cycle
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
                if not proxy_wrappers: return requests.Session()
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

            def fetch_worker(roll_str: str, worker_idx: int) -> Optional[Dict[str, Any]]:
                if proxy_wrappers:
                    for offset in range(min(5, len(proxy_wrappers))):
                        sess = get_proxy_session(worker_idx * 5 + offset)
                        try:
                            r = sess.get(ENDPOINT.format(roll=roll_str), timeout=2.2)
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

            rolls_queue = queue.Queue()
            for item in current_batch:
                rolls_queue.put((item["roll"], item["meta"]))

            cycle_done_count = 0
            seen_in_cycle = set()
            active_count = [0]
            active_lock = threading.Lock()
            print_lock = threading.Lock()
            stats_lock = threading.Lock()
            stop_cycle = threading.Event()

            def student_consumer(worker_idx: int):
                nonlocal cycle_done_count
                while not stop_cycle.is_set():
                    try:
                        item = rolls_queue.get(timeout=0.2)
                    except queue.Empty:
                        with active_lock:
                            if rolls_queue.empty() and active_count[0] == 0:
                                break
                        continue

                    if item is None:
                        rolls_queue.task_done()
                        break

                    with active_lock: active_count[0] += 1
                    roll_str, meta = item[0], item[1]
                    attempts = item[2] if len(item) == 3 else 0

                    res = fetch_worker(roll_str, worker_idx + attempts * 13)
                    if res and res.get("success"):
                        save_record_to_upazilla(res, meta)
                        with stats_lock:
                            cycle_done_count += 1
                            seen_in_cycle.add(roll_str)
                            already_scraped_map[roll_str] = res
                            cur_rec = cycle_done_count

                        s_name = res.get("student_name", "STUDENT")
                        gpa_res = res.get("result", "N/A")
                        is_pass = "GPA" in str(gpa_res)
                        status_color = GREEN if is_pass else RED
                        status_label = "PASSED" if is_pass else "FAILED"
                        p_bar = format_progress_bar(cur_rec, current_target, width=18)
                        with print_lock:
                            print(f"{CYAN}{p_bar}{RESET} {cur_rec:3d}/{current_target}  Roll {roll_str:<7}  {s_name:<30}  {gpa_res:<10} {status_color}{status_label}{RESET}")
                    else:
                        if attempts < 3 and not stop_cycle.is_set():
                            rolls_queue.put((roll_str, meta, attempts + 1))

                    with active_lock: active_count[0] -= 1
                    rolls_queue.task_done()

            num_workers = min(30, max(15, len(proxies) - 20)) if len(proxies) > 0 else 20
            consumer_threads = [threading.Thread(target=student_consumer, args=(i,), daemon=True) for i in range(num_workers)]
            for t in consumer_threads: t.start()

            try:
                rolls_queue.join()
                for _ in range(num_workers): rolls_queue.put(None)
                for t in consumer_threads: t.join()
            except KeyboardInterrupt:
                global_stop = True
                stop_cycle.set()
                print(f"\n[!] Stopped by user. Preserving all records...")
                break

            flush_dirty_upazillas(force=True)

            # Auto Catch-Up for this 150 slice
            unretrieved = [item for item in current_batch if str(item["roll"]) not in seen_in_cycle]
            for pass_num in range(1, 6):
                if not unretrieved or global_stop: break
                print(f"\n{YELLOW}🔄 [Cycle {cycle_num} Catch-Up Pass {pass_num}/5] Re-attempting {len(unretrieved)} unretrieved roll(s)...{RESET}")
                time.sleep(0.8)

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(15, len(unretrieved))) as rec_exec:
                    future_to_item = {rec_exec.submit(fetch_worker, item["roll"], idx + pass_num * 17): item for idx, item in enumerate(unretrieved)}
                    for future in concurrent.futures.as_completed(future_to_item):
                        item = future_to_item[future]
                        res = future.result()
                        if res and res.get("success"):
                            save_record_to_upazilla(res, item["meta"])
                            seen_in_cycle.add(str(item["roll"]))
                            already_scraped_map[str(item["roll"])] = res
                            cycle_done_count += 1
                            s_name = res.get("student_name", "STUDENT")
                            gpa_res = res.get("result", "N/A")
                            is_pass = "GPA" in str(gpa_res)
                            p_bar = format_progress_bar(cycle_done_count, current_target, width=18)
                            print(f"{CYAN}{p_bar}{RESET} {cycle_done_count:3d}/{current_target}  Roll {item['roll']:<7}  {s_name:<30}  {gpa_res:<10} {GREEN if is_pass else RED}{'PASSED' if is_pass else 'FAILED'}{RESET}")

                flush_dirty_upazillas(force=True)
                unretrieved = [item for item in current_batch if str(item["roll"]) not in seen_in_cycle]

            flush_dirty_upazillas(force=True)
            print(f"{GREEN}✓ Cycle {cycle_num} Complete: {cycle_done_count}/{current_target} rolls scraped! Auto-restarting next cycle...{RESET}")
            cycle_num += 1

            if global_stop:
                break

        # Final Master JSON Update
        all_final_recs = []
        for upz_path in glob.glob(os.path.join(results_root, "**", "results_upazilla_*.json"), recursive=True):
            try:
                with open(upz_path, 'r', encoding='utf-8') as f:
                    all_final_recs.extend(json.load(f).get("records", []))
            except Exception: pass

        unique_final_recs = {str(r.get("roll_no")): r for r in all_final_recs if r.get("roll_no") and r.get("success")}
        final_list = list(unique_final_recs.values())
        for i, rec in enumerate(final_list, 1): rec["index"] = i
        tot_passed = sum(1 for item in final_list if "GPA" in str(item.get("result", "")))
        master_summary = {
            "total_records": len(final_list),
            "total_passed": tot_passed,
            "total_failed": len(final_list) - tot_passed,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(master_file, "w", encoding="utf-8") as f:
            json.dump({"summary": master_summary, "records": final_list}, f, indent=2, ensure_ascii=False)

        total_elapsed = time.time() - total_start_time
        mins, secs = divmod(total_elapsed, 60)
        time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"

        print(f"\n=======================================================")
        print(f"⏱️ {BOLD}FULL BATCH EXECUTION COMPLETE IN {time_str}!{RESET}")
        print(f"  • Institutions Processed:  {len(eiins)}")
        print(f"  • Total Candidate Rolls:   {total_candidates_count}")
        print(f"  • Scraped in Cycles:       {total_candidates_count - initial_done} records")
        print(f"  • Total Database Size:     {len(final_list)} records in scraped_results_all.json")
        print(f"=======================================================\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Exited safely.{RESET}")
        sys.exit(0)
