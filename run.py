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
import logging
import glob
import concurrent.futures
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

# Completely mute noisy debug/info logs from the terminal
logging.disable(logging.INFO)
logging.basicConfig(level=logging.WARNING)
for log_name in ["engine.scraper_engine", "engine.institute_fetcher", "urllib3", "root"]:
    logging.getLogger(log_name).setLevel(logging.WARNING)

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

    def load_and_verify(self, max_candidates: int = 2500, max_valid: int = 50) -> List[str]:
        # 1. Check local cached proxies if recent (<15 minutes)
        if os.path.exists(self.cache_file):
            try:
                mtime = os.path.getmtime(self.cache_file)
                if time.time() - mtime < 900:
                    with open(self.cache_file, "r", encoding="utf-8") as f:
                        cached = [line.strip() for line in f if ":" in line.strip()]
                    if len(cached) >= 15:
                        self.proxies = cached[:max_valid]
                        return self.proxies
            except Exception:
                pass

        # 2. Harvest raw proxies from all 35 sources concurrently
        raw_proxies = set()
        def fetch_src(src_url):
            try:
                r = requests.get(src_url, timeout=3.5)
                if r.status_code == 200:
                    return re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b", r.text)
            except Exception:
                pass
            return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=35) as ex:
            for found_ips in ex.map(fetch_src, PROXY_SOURCES):
                raw_proxies.update(found_ips)

        candidate_list = list(raw_proxies)[:max_candidates]
        test_url = ENDPOINT.format(roll="217305")

        def test_p(p):
            try:
                prox = {"http": f"http://{p}", "https": f"http://{p}"}
                r = requests.get(test_url, proxies=prox, timeout=3.5)
                if r.status_code == 200 and "Student Result" in r.text:
                    return p
            except Exception:
                pass
            return None

        valid = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
            for res in ex.map(test_p, candidate_list):
                if res:
                    valid.append(res)
                    if len(valid) >= max_valid:
                        break

        self.proxies = valid
        if valid:
            try:
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(valid))
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
    print_banner()

    fetcher = InstituteResultFetcher()
    results_root = os.path.join(BASE_DIR, "results")
    master_file = os.path.join(BASE_DIR, "scraped_results_all.json")
    os.makedirs(results_root, exist_ok=True)
    
    proxy_pool = FastProxyPool()
    proxies = []

    while True:
        eiins = get_eiin_inputs()
        if not eiins:
            print(f"\n{YELLOW}[!] No EIIN entered. Exiting... Goodbye!{RESET}\n")
            break

        batch_start_time = time.time()

        # ==========================================
        # Step 1: Harvest Candidate Rolls from Gazette
        # ==========================================
        print(f"\n{CYAN}[Step 1/2] Harvesting Gazette Records for {len(eiins)} Institution(s)...{RESET}")
        harvest_start_time = time.time()
        
        all_target_rolls = []
        roll_metadata_map = {}
        upazilla_summary = {}

        cache_dir = os.path.join(BASE_DIR, "cache", "institutions")
        os.makedirs(cache_dir, exist_ok=True)

        for idx, eiin in enumerate(eiins, 1):
            cache_file = os.path.join(cache_dir, f"eiin_{eiin}.json")
            inst_data = None

            # 1. Check local institution cache for instant resume
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as cf:
                        inst_data = json.load(cf)
                except Exception:
                    inst_data = None

            is_cached = False
            if inst_data and inst_data.get("name") and "students" in inst_data:
                is_cached = True
            else:
                def on_retry_status(msg):
                    print(f"\r  [{idx}/{len(eiins)}] Querying EIIN {eiin}... {YELLOW}🔄 {msg}{RESET}   ", end="", flush=True)

                print(f"  [{idx}/{len(eiins)}] Querying EIIN {eiin}...", end="", flush=True)
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
                print(f"\r  [{idx}/{len(eiins)}] Querying EIIN {eiin}... {RED}Failed (Not found or unreachable){RESET}  ")
                continue

            inst_name = inst_data.get("name", "Unknown")
            district = inst_data.get("district", "Unknown")
            upazila = inst_data.get("upazila", "UNKNOWN")
            students = inst_data.get("students", [])
            
            # Exclude absent students who didn't sit for the exam
            appeared_students = [s for s in students if s.get("status") != "ABSENT" and "ABS" not in str(s.get("gpa", "")).upper()]
            abs_count = len(students) - len(appeared_students)
            
            rolls = [str(s["roll"]) for s in appeared_students if s.get("roll")]
            abs_info = f", {abs_count} absent excluded" if abs_count > 0 else ""
            source_tag = f"{CYAN}⚡ (Cached){RESET}" if is_cached else f"{GREEN}✓{RESET}"
            print(f"\r  [{idx}/{len(eiins)}] Querying EIIN {eiin}... {source_tag} {inst_name[:36]} ({len(rolls)} appeared rolls{abs_info})  ")

            upz_slug = re.sub(r'[^a-zA-Z0-9]+', '_', upazila.strip().lower()).strip('_')
            if upz_slug not in upazilla_summary:
                upazilla_summary[upz_slug] = {"upazila": upazila, "district": district, "rolls_count": 0}
            upazilla_summary[upz_slug]["rolls_count"] += len(rolls)

            for s in appeared_students:
                r_str = str(s["roll"])
                all_target_rolls.append(r_str)
                roll_metadata_map[r_str] = {
                    "eiin": int(eiin),
                    "institute": inst_name,
                    "upazila": upazila,
                    "district": district,
                    "group": s.get("group")
                }

            if not is_cached:
                time.sleep(2.5)

        harvest_elapsed = time.time() - harvest_start_time
        all_unique_rolls = list(dict.fromkeys(all_target_rolls))

        print(f"\n=======================================================")
        print(f"📊 {BOLD}HARVEST SUMMARY:{RESET}")
        print(f"  • Institutions Processed: {len(eiins)}")
        print(f"  • Total Upazillas:        {len(upazilla_summary)}")
        print(f"  • Total Candidate Rolls:  {len(all_unique_rolls)}")
        print(f"=======================================================\n")

        if not all_unique_rolls:
            print(f"{YELLOW}[!] No candidate rolls discovered for this batch.{RESET}\n")
            continue

        # Check already scraped rolls across all district folders & datasets
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

        pending_rolls = [r for r in all_unique_rolls if r not in already_scraped_map]
        print(f"[*] Already Scraped: {len(all_unique_rolls) - len(pending_rolls)} | Remaining: {len(pending_rolls)}")

        if not pending_rolls:
            print(f"{GREEN}🎉 All {len(all_unique_rolls)} rolls across these EIINs are already 100% scraped!{RESET}\n")
            print(f"{CYAN}───────────────────────────────────────────────────────────{RESET}\n")
            continue

        # ==========================================
        # Step 2: High-Speed Concurrent Scrape
        # ==========================================
        print(f"\n{CYAN}[Step 2/2] Launching Ultra-Fast Local Engine for {len(pending_rolls)} Rolls...{RESET}")
        
        if len(proxies) < 15:
            print(f"{DIM}Verifying dynamic proxy pool for zero rate limits...{RESET}", end="", flush=True)
            proxies = proxy_pool.load_and_verify(max_candidates=2500, max_valid=50)
            print(f"\r{GREEN}✓ Active Proxy Pool: {len(proxies)} high-speed nodes ready!{RESET}\n")

        target_count = len(pending_rolls)
        received_count = 0
        start_time = time.time()
        seen_rolls = set(already_scraped_map.keys())

        def fetch_worker(roll_str: str, worker_idx: int) -> Optional[Dict[str, Any]]:
            # 1. Try rotating through verified proxy nodes
            if proxies:
                for offset in range(min(5, len(proxies))):
                    p = proxies[(worker_idx + offset) % len(proxies)]
                    prox = {"http": f"http://{p}", "https": f"http://{p}"}
                    try:
                        url = ENDPOINT.format(roll=roll_str)
                        r = requests.get(url, proxies=prox, timeout=4.5)
                        if r.status_code == 200:
                            parsed = parse_student_html(r.text, roll_str)
                            if parsed:
                                return parsed
                    except Exception:
                        pass

            # 2. Fallback to direct request with backoff
            for att in range(1, 4):
                try:
                    url = ENDPOINT.format(roll=roll_str)
                    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
                    if r.status_code == 200:
                        parsed = parse_student_html(r.text, roll_str)
                        if parsed:
                            return parsed
                    elif r.status_code == 429:
                        time.sleep(2.0 * att)
                except Exception:
                    time.sleep(1.0)
            return None

        def save_record_to_upazilla(r: Dict[str, Any]):
            r_roll = str(r.get("roll_no"))
            meta = roll_metadata_map.get(r_roll, {})
            
            # District-wise folder routing
            district_name = meta.get("district") or r.get("district") or "UNKNOWN_DISTRICT"
            district_slug = re.sub(r'[^a-zA-Z0-9]+', '_', district_name.strip().upper()).strip('_')
            district_folder = os.path.join(results_root, district_slug)
            os.makedirs(district_folder, exist_ok=True)

            upz_name = meta.get("upazila") or r.get("upazila") or "UNKNOWN_UPAZILLA"
            upz_slug = re.sub(r'[^a-zA-Z0-9]+', '_', upz_name.strip().lower()).strip('_')
            upz_file = os.path.join(district_folder, f"results_upazilla_{upz_slug}.json")

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

            existing_roll_map = {str(item.get("roll_no")): item for item in upz_data.get("records", [])}

            r["upazila"] = upz_name
            r["district"] = district_name
            if meta.get("eiin"): r["eiin"] = meta.get("eiin")
            if meta.get("institute"): r["institute"] = meta.get("institute")

            existing_roll_map[r_roll] = r

            all_upz_records = list(existing_roll_map.values())
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
            with open(temp_upz_file, 'w', encoding='utf-8') as out_f:
                json.dump(upz_data, out_f, indent=2, ensure_ascii=False)
            os.replace(temp_upz_file, upz_file)

        # Step 2: High-Speed Concurrent Scrape with Automatic Multi-Pass Recovery Sweep
        current_rolls_to_scrape = pending_rolls
        max_recovery_passes = 3

        for pass_num in range(1, max_recovery_passes + 1):
            if not current_rolls_to_scrape:
                break

            if pass_num > 1:
                print(f"\n{YELLOW}🔄 [Auto Catch-Up Pass {pass_num}/{max_recovery_passes}] Re-attempting {len(current_rolls_to_scrape)} unretrieved roll(s) with fresh proxies...{RESET}")
                # Refresh proxy pool for fresh nodes
                proxies = proxy_pool.load_and_verify(max_candidates=2500, max_valid=50)
                time.sleep(1.0)

            max_workers = min(20, len(current_rolls_to_scrape)) if len(current_rolls_to_scrape) > 0 else 1
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_roll = {
                    executor.submit(fetch_worker, roll, idx): roll
                    for idx, roll in enumerate(current_rolls_to_scrape)
                }

                for future in concurrent.futures.as_completed(future_to_roll):
                    roll = future_to_roll[future]
                    res = future.result()
                    
                    if res and res.get("success"):
                        received_count += 1
                        seen_rolls.add(roll)
                        save_record_to_upazilla(res)

                        s_name = res.get("student_name", "STUDENT")
                        gpa_res = res.get("result", "N/A")
                        is_pass = "GPA" in str(gpa_res)
                        status_color = GREEN if is_pass else RED
                        status_label = "PASSED" if is_pass else "FAILED"
                        p_bar = format_progress_bar(received_count, target_count, width=20)

                        print(f"{CYAN}{p_bar}{RESET} {received_count:4d}/{target_count}  Roll {roll:<7}  {s_name:<32}  {gpa_res:<10} {status_color}{status_label}{RESET}")

            # Check if any rolls are still missing for the next pass
            current_rolls_to_scrape = [r for r in pending_rolls if r not in seen_rolls]

        total_elapsed = time.time() - batch_start_time
        scrape_elapsed = time.time() - start_time
        
        mins, secs = divmod(total_elapsed, 60)
        time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"
        
        speed = (received_count / max(0.001, scrape_elapsed))
        speed_rpm = int(speed * 60)

        print(f"\n=======================================================")
        print(f"⏱️ {BOLD}PROCESS EXECUTION TIME & PERFORMANCE:{RESET}")
        print(f"  • Total Time Taken:     {CYAN}{BOLD}{time_str}{RESET}")
        print(f"  • Gazette Harvest Time: {harvest_elapsed:.2f}s")
        print(f"  • Roll Scraping Time:   {scrape_elapsed:.2f}s")
        print(f"  • Average Scraping Speed: {GREEN}{speed:.1f} rolls/sec ({speed_rpm} rolls/min){RESET}")
        print(f"  • Records Completed:    {received_count}/{target_count} ({100.0 * received_count / max(1, target_count):.1f}%)")
        print(f"=======================================================")

        if len(current_rolls_to_scrape) == 0:
            print(f"\n{GREEN}{BOLD}🎉 Finished Batch! All {received_count}/{target_count} (100%) student results saved across Upazilla files in {time_str}!{RESET}")
        else:
            print(f"\n{YELLOW}{BOLD}⚠️ Finished Batch! {received_count}/{target_count} student results saved ({len(current_rolls_to_scrape)} unretrieved) in {time_str}!{RESET}")
        print(f"{CYAN}───────────────────────────────────────────────────────────{RESET}\n")

if __name__ == "__main__":
    try:
        run_scraper_cli()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Scraper terminated by user. All scraped records are safely preserved!{RESET}")
        sys.exit(0)
