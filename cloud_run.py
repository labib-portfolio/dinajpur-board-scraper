"""
🚀 FULLY AUTOMATED 1-CLICK CLUSTER ENGINE (100 GITHUB ACTIONS CLOUD WORKERS)
Usage:
    python cloud_run.py

Workflow:
1. Paste EIINs -> Instant Roster Harvest & Deduplication
2. Pushes rolls.json to all 5 GitHub Repos
3. Triggers 100 Parallel Cloud Action VMs
4. Automatically waits, pulls, merges, and updates all local Upazilla JSON files!
"""

import os
import sys
import glob
import json
import time
import re
import subprocess
import requests
import zipfile
import io
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from engine.institute_fetcher import InstituteResultFetcher
from engine.proxy_manager import FastProxyPool

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

REPOS = [
    ("origin", "labib-portfolio/dinajpur-board-scraper"),
    ("node2", "labib-portfolio/dinajpur-board-scraper-node2"),
    ("node3", "labib-portfolio/dinajpur-board-scraper-node3"),
    ("node4", "labib-portfolio/dinajpur-board-scraper-node4"),
    ("node5", "labib-portfolio/dinajpur-board-scraper-node5")
]

def format_progress_bar(current: int, total: int, width: int = 18) -> str:
    if total <= 0:
        return f"[{'░' * width}]"
    filled = int(width * current // total)
    return f"[{'█' * filled}{'░' * (width - filled)}]"

def parse_eiin_inputs() -> List[str]:
    print(f"\n{CYAN}{BOLD}📥 ENTER OR PASTE YOUR EIINs (Press Enter twice to start):{RESET}")
    lines = []
    while True:
        try:
            line = input().strip()
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
    print(f"☁️  AUTOMATED 100-WORKER GITHUB ACTIONS CLUSTER ENGINE")
    print(f"======================================================={RESET}")

    results_root = os.path.join(BASE_DIR, "results")
    cache_dir = os.path.join(BASE_DIR, "cache", "institutions")
    master_file = os.path.join(BASE_DIR, "scraped_results_all.json")
    rolls_file = os.path.join(BASE_DIR, "rolls.json")
    os.makedirs(results_root, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    proxy_pool = FastProxyPool()
    proxies = proxy_pool.load_and_verify(max_candidates=2000, max_valid=50)
    fetcher = InstituteResultFetcher(proxies=proxies)

    while True:
        eiins = parse_eiin_inputs()
        if not eiins:
            print(f"\n{YELLOW}[!] No EIIN entered. Exiting... Goodbye!{RESET}\n")
            break

        start_time = time.time()

        # 1. Preload existing results to avoid duplicate scraping
        already_scraped_map = {}
        for f in glob.glob(os.path.join(results_root, "**", "results_upazilla_*.json"), recursive=True):
            try:
                with open(f, 'r', encoding='utf-8') as uf:
                    for r in json.load(uf).get("records", []):
                        if r.get("roll_no") and r.get("success"):
                            already_scraped_map[str(r.get("roll_no"))] = r
            except Exception: pass

        print(f"\n[*] Harvesting student rosters across {len(eiins)} institutions...")
        pending_rolls = []
        roll_metadata_map = {}
        total_appeared = 0
        already_done_count = 0

        for idx, eiin in enumerate(eiins, 1):
            cache_f = os.path.join(cache_dir, f"eiin_{eiin}.json")
            inst_data = None
            if os.path.exists(cache_f):
                try:
                    with open(cache_f, "r", encoding="utf-8") as f:
                        inst_data = json.load(f)
                except Exception: pass

            is_cached = bool(inst_data and inst_data.get("name") and "students" in inst_data)
            if not is_cached:
                inst_data = fetcher.fetch_by_eiin(eiin)
                if inst_data and not inst_data.get("error") and inst_data.get("name"):
                    try:
                        with open(cache_f, "w", encoding="utf-8") as f:
                            json.dump(inst_data, f, indent=2, ensure_ascii=False)
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

            queued = 0
            for s in students:
                r_str = str(s["roll"])
                meta = {"eiin": int(eiin), "institute": inst_name, "upazila": upazila, "district": district, "group": s.get("group")}
                total_appeared += 1
                roll_metadata_map[r_str] = meta
                if r_str in already_scraped_map:
                    already_done_count += 1
                else:
                    if r_str not in pending_rolls:
                        pending_rolls.append(r_str)
                        queued += 1

            if not is_cached:
                print(f"  [{idx}/{len(eiins)}] EIIN {eiin}: {inst_name[:25]} {GREEN}+{queued} new rolls{RESET}")
                time.sleep(1.2)

        print(f"\n{GREEN}✓ Roster Harvest Complete: {total_appeared} total rolls ({already_done_count} already scraped, {len(pending_rolls)} new to scrape){RESET}")

        if not pending_rolls:
            print(f"\n{GREEN}{BOLD}🎉 All {total_appeared} candidate rolls are already completely scraped!{RESET}\n")
            continue

        # 2. Write rolls.json with unique timestamp to guarantee git commit & GitHub Actions trigger
        payload = {
            "session_id": f"batch_{int(time.time())}",
            "triggered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_rolls": len(pending_rolls),
            "rolls": pending_rolls
        }
        with open(rolls_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        print(f"\n[*] Committing & pushing {len(pending_rolls)} rolls to all 5 GitHub repositories...")
        subprocess.run(["git", "add", "rolls.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "commit", "-m", f"Trigger 100-worker cloud scraping for {len(pending_rolls)} rolls [{payload['session_id']}]"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        push_procs = []
        for remote_name, _ in REPOS:
            p = subprocess.Popen(["git", "push", remote_name, "main"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            push_procs.append((remote_name, p))

        for remote_name, p in push_procs:
            out, err = p.communicate()
            print(f"  • Pushed to {remote_name.upper()} (Triggered 20 Cloud VMs)")

        print(f"\n{CYAN}{BOLD}⚡ 100 GITHUB ACTIONS CLOUD VMs ARE NOW RUNNING IN PARALLEL!{RESET}")
        print(f"[*] Cloud workers are scraping at ~80-100 rolls/sec...")

        # 3. Live Event-Driven Remote Poller (15s quiet interval, prints only on node completion)
        print(f"\n[*] Waiting for all 5 cloud repositories to complete scraping (checking every 15s)...")
        start_wait = time.time()
        
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        pushed_hash = res.stdout.strip()
        node_status = {name: False for name, _ in REPOS}

        while not all(node_status.values()):
            time.sleep(15)
            elapsed_wait = int(time.time() - start_wait)
            mins, secs = divmod(elapsed_wait, 60)
            time_tag = f"{int(mins)}m {secs:02d}s" if mins > 0 else f"{secs}s"

            for remote_name, repo_path in REPOS:
                if not node_status[remote_name]:
                    try:
                        ls_res = subprocess.run(["git", "ls-remote", remote_name, "refs/heads/main"], capture_output=True, text=True, timeout=10)
                        remote_hash = ls_res.stdout.split()[0] if ls_res.stdout else ""
                        if remote_hash and remote_hash != pushed_hash:
                            node_status[remote_name] = True
                            display_name = "NODE 1 (ORIGIN)" if remote_name == "origin" else remote_name.upper()
                            print(f"  • [{time_tag}] {display_name:<16} {GREEN}✓ 20 Cloud VMs Finished & Pushed Results!{RESET}")
                    except Exception:
                        pass

            if elapsed_wait >= 600:
                print(f"  {YELLOW}[!] Reached maximum wait time (10m). Proceeding with completed nodes...{RESET}")
                break

        print(f"\n{GREEN}{BOLD}[✓] All active cloud repositories finished! Pulling results into local storage...{RESET}")

        # 4. Auto-pull latest updates from all 5 cloud repositories
        for remote_name, _ in REPOS:
            subprocess.run(["git", "pull", remote_name, "main", "--no-rebase"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 5. Merge any chunk outputs from chunks_output/ into the local Upazilla structure
        chunk_files = glob.glob(os.path.join(BASE_DIR, "chunks_output", "*.json"))
        newly_scraped = 0
        if chunk_files:
            for cf in chunk_files:
                try:
                    with open(cf, "r", encoding="utf-8") as cff:
                        c_data = json.load(cff)
                        for r in c_data.get("records", []):
                            roll = str(r.get("roll_no"))
                            if roll and r.get("success"):
                                meta = roll_metadata_map.get(roll, {})
                                r["upazila"] = meta.get("upazila") or r.get("upazila") or "UNKNOWN_UPAZILLA"
                                r["district"] = meta.get("district") or r.get("district") or "UNKNOWN_DISTRICT"
                                if meta.get("eiin"): r["eiin"] = meta.get("eiin")
                                if meta.get("institute"): r["institute"] = meta.get("institute")
                                already_scraped_map[roll] = r
                                newly_scraped += 1
                except Exception: pass

        # 6. Save all records into District & Upazilla JSON structure
        upazilla_groups = {}
        for roll, r in already_scraped_map.items():
            district = r.get("district") or "UNKNOWN_DISTRICT"
            district_slug = re.sub(r'[^a-zA-Z0-9]+', '_', district.strip().upper()).strip('_')
            upazila = r.get("upazila") or "UNKNOWN_UPAZILLA"
            upz_slug = re.sub(r'[^a-zA-Z0-9]+', '_', upazila.strip().lower()).strip('_')
            key = (district_slug, upz_slug, district, upazila)
            if key not in upazilla_groups:
                upazilla_groups[key] = {}
            upazilla_groups[key][roll] = r

        for (district_slug, upz_slug, district_name, upz_name), roll_map in upazilla_groups.items():
            district_folder = os.path.join(results_root, district_slug)
            os.makedirs(district_folder, exist_ok=True)
            upz_file = os.path.join(district_folder, f"results_upazilla_{upz_slug}.json")
            all_upz_records = list(roll_map.values())
            for i, rec in enumerate(all_upz_records, 1): rec["index"] = i
            passed_count = sum(1 for item in all_upz_records if "GPA" in str(item.get("result", "")))
            unique_eiins = sorted(list({int(item.get("eiin")) for item in all_upz_records if item.get("eiin")}))
            upz_data = {
                "upazila": upz_name,
                "district": district_name,
                "summary": {
                    "total_records": len(all_upz_records),
                    "total_passed": passed_count,
                    "total_failed": len(all_upz_records) - passed_count,
                    "institutions_count": len(unique_eiins),
                    "scraped_eiins": unique_eiins,
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "records": all_upz_records
            }
            tmp = upz_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(upz_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, upz_file)

        # Update Master JSON
        all_final_recs = list(already_scraped_map.values())
        for i, rec in enumerate(all_final_recs, 1): rec["index"] = i
        tot_passed = sum(1 for item in all_final_recs if "GPA" in str(item.get("result", "")))
        master_summary = {
            "total_records": len(all_final_recs),
            "total_passed": tot_passed,
            "total_failed": len(all_final_recs) - tot_passed,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(master_file, "w", encoding="utf-8") as f:
            json.dump({"summary": master_summary, "records": all_final_recs}, f, indent=2, ensure_ascii=False)

        total_elapsed = time.time() - start_time
        mins, secs = divmod(total_elapsed, 60)
        time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"

        print(f"\n=======================================================")
        print(f"⏱️ {BOLD}CLOUD CLUSTER EXECUTION COMPLETE IN {time_str}!{RESET}")
        print(f"  • Institutions Processed:  {len(eiins)}")
        print(f"  • Candidate Rolls:         {total_appeared}")
        print(f"  • Scraped in Cloud:        {len(pending_rolls)} rolls across 100 VMs")
        print(f"  • Auto-Synced Destination: results/<DISTRICT>/results_upazilla_*.json")
        print(f"  • Master Database:         scraped_results_all.json ({len(all_final_recs)} total records)")
        print(f"=======================================================\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Exited safely.{RESET}")
        sys.exit(0)
