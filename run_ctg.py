"""
Interactive Terminal CLI for Chittagong Education Board (BISE CTG) Result Scraper 2026
Full District-Folder & Upazila-Wise JSON Persistence System
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


def get_default_results_root() -> str:
    """Auto-detect Android Mobile Internal Storage (Termux) or PC directory."""
    if os.path.exists("/storage/emulated/0"):
        return "/storage/emulated/0/Result Scraper/Chittagong"
    elif os.path.exists("/sdcard"):
        return "/sdcard/Result Scraper/Chittagong"
    elif os.path.exists("/storage/emulated"):
        return "/storage/emulated/Result Scraper/Chittagong"
    return os.path.join(BASE_DIR, "results", "chittagong")


def slugify(text: str) -> str:
    """Converts text into clean filesystem slug."""
    text = re.sub(r'[\(\)\.,\-\s]+', '_', text.strip().lower())
    return text.strip('_') or 'unknown'


# EIIN to District/Upazila lookup cache
_EIIN_GEO_MAP = {}
def load_eiin_geo_map():
    global _EIIN_GEO_MAP
    if _EIIN_GEO_MAP:
        return _EIIN_GEO_MAP
    
    geo_file = os.path.join(BASE_DIR, "chittagong_board_eiin", "chittagong_board_all_eiins.json")
    if not os.path.exists(geo_file):
        geo_file = os.path.join(r"C:\Users\labib_n4\Documents\Project\Result-Scraper\chittagong_board_eiin\chittagong_board_all_eiins.json")
    
    if os.path.exists(geo_file):
        try:
            with open(geo_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                for inst in d.get("institutions", []):
                    e = str(inst.get("eiin"))
                    _EIIN_GEO_MAP[e] = {
                        "zilla": inst.get("zila", "CHATTOGRAM").upper(),
                        "upazila": inst.get("upazilla", "UNKNOWN").upper(),
                        "name": inst.get("name", "")
                    }
        except Exception:
            pass
    return _EIIN_GEO_MAP


def print_ctg_banner():
    print(f"\n{CYAN}┌───────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}Chittagong Board SSC Result Scraper 2026 — High-Speed{RESET}     {CYAN}│{RESET}")
    print(f"{CYAN}├───────────────────────────────────────────────────────────┤{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}District-Folder & Upazila-Wise JSON Architecture{RESET}           {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Zero CAPTCHA • Multi-Threaded Proxies • Total Marks Calc{RESET}    {CYAN}│{RESET}")
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
# UNIFIED DUAL STORAGE ENGINE (Upazila-Wise JSON + District Folders + Master)
# =========================================================================
class CtgResultsManager:
    def __init__(self, results_root: Optional[str] = None):
        self.root = results_root or get_default_results_root()
        os.makedirs(self.root, exist_ok=True)
        self.master_file = os.path.join(self.root, "chittagong_results_all.json")
        self.geo_map = load_eiin_geo_map()
        self.lock = threading.Lock()
        
        # Load Master Cache
        self.master_students = {}
        self.master_institutions = {}
        if os.path.exists(self.master_file):
            try:
                with open(self.master_file, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    for inst in d.get("institutions", []):
                        if inst.get("eiin"):
                            self.master_institutions[str(inst.get("eiin"))] = inst
                    raw_s = d.get("students", []) or d.get("records", [])
                    for s in raw_s:
                        if s.get("roll_no"):
                            self.master_students[str(s.get("roll_no"))] = s
            except Exception:
                pass

        # In-memory upazila datasets: key -> (zilla_slug, upz_slug)
        self.upazila_data = {}
        self._load_existing_upazilas()

    def _load_existing_upazilas(self):
        for z_dir in glob.glob(os.path.join(self.root, "*")):
            if os.path.isdir(z_dir):
                z_name = os.path.basename(z_dir)
                for u_file in glob.glob(os.path.join(z_dir, "results_upazilla_*.json")):
                    try:
                        with open(u_file, "r", encoding="utf-8") as uf:
                            u_json = json.load(uf)
                            u_slug = u_json.get("upazilla_slug") or slugify(u_json.get("upazilla", "unknown"))
                            key = (slugify(z_name), u_slug)
                            self.upazila_data[key] = {
                                "file_path": u_file,
                                "data": u_json,
                                "students_map": {str(x["roll_no"]): x for x in u_json.get("records", []) if x.get("roll_no")},
                                "institutions_map": {str(x["eiin"]): x for x in u_json.get("institutions", []) if x.get("eiin")}
                            }
                    except Exception:
                        pass

    def add_institution_and_students(self, inst_info: Dict[str, Any], students: List[Dict[str, Any]]):
        eiin_str = str(inst_info.get("eiin", "")).strip()
        zilla_raw = inst_info.get("zilla", "")
        upz_raw = inst_info.get("thana", "") or inst_info.get("upazila", "")

        # Fallback to geo map if not provided in gazette
        if not zilla_raw and eiin_str in self.geo_map:
            zilla_raw = self.geo_map[eiin_str].get("zilla", "CHATTOGRAM")
            upz_raw = self.geo_map[eiin_str].get("upazila", "UNKNOWN")

        zilla_name = zilla_raw.upper() if zilla_raw else "CHATTOGRAM"
        upz_name = upz_raw.upper() if upz_raw else "UNKNOWN"
        z_slug = slugify(zilla_name)
        u_slug = slugify(upz_name)

        with self.lock:
            # 1. Update Master
            self.master_institutions[eiin_str] = {
                "eiin": eiin_str,
                "name": inst_info.get("institute_name", ""),
                "zilla": zilla_name,
                "thana": upz_name,
                "appeared": inst_info.get("total_appeared", len(students)),
                "passed": inst_info.get("total_passed", sum(1 for s in students if s.get("status") == "PASSED")),
                "gpa5": inst_info.get("total_gpa5", 0),
                "pass_percentage": inst_info.get("pass_percentage", ""),
                "students_count": len(students)
            }
            for s in students:
                s["zilla"] = zilla_name
                s["upazila"] = upz_name
                self.master_students[str(s["roll_no"])] = s

            # 2. Update Upazila Specific File
            key = (z_slug, u_slug)
            z_folder = os.path.join(self.root, zilla_name)
            os.makedirs(z_folder, exist_ok=True)
            u_file = os.path.join(z_folder, f"results_upazilla_{u_slug}.json")

            if key not in self.upazila_data:
                self.upazila_data[key] = {
                    "file_path": u_file,
                    "data": {
                        "board": "CHATTOGRAM",
                        "district": zilla_name,
                        "upazilla": upz_name,
                        "upazilla_slug": u_slug,
                        "summary": {},
                        "institutions": [],
                        "records": []
                    },
                    "students_map": {},
                    "institutions_map": {}
                }

            u_entry = self.upazila_data[key]
            u_entry["institutions_map"][eiin_str] = self.master_institutions[eiin_str]
            for s in students:
                u_entry["students_map"][str(s["roll_no"])] = s

    def add_single_student(self, s: Dict[str, Any]):
        roll_str = str(s.get("roll_no"))
        eiin_str = str(s.get("eiin", ""))
        zilla_raw = s.get("zilla", "")
        upz_raw = s.get("upazila", "")

        if not zilla_raw and eiin_str in self.geo_map:
            zilla_raw = self.geo_map[eiin_str].get("zilla", "CHATTOGRAM")
            upz_raw = self.geo_map[eiin_str].get("upazila", "UNKNOWN")

        zilla_name = zilla_raw.upper() if zilla_raw else "CHATTOGRAM"
        upz_name = upz_raw.upper() if upz_raw else "UNKNOWN"
        z_slug = slugify(zilla_name)
        u_slug = slugify(upz_name)

        s["zilla"] = zilla_name
        s["upazila"] = upz_name

        with self.lock:
            self.master_students[roll_str] = s
            key = (z_slug, u_slug)
            z_folder = os.path.join(self.root, zilla_name)
            os.makedirs(z_folder, exist_ok=True)
            u_file = os.path.join(z_folder, f"results_upazilla_{u_slug}.json")

            if key not in self.upazila_data:
                self.upazila_data[key] = {
                    "file_path": u_file,
                    "data": {
                        "board": "CHATTOGRAM",
                        "district": zilla_name,
                        "upazilla": upz_name,
                        "upazilla_slug": u_slug,
                        "summary": {},
                        "institutions": [],
                        "records": []
                    },
                    "students_map": {},
                    "institutions_map": {}
                }

            u_entry = self.upazila_data[key]
            u_entry["students_map"][roll_str] = s

    def flush_to_disk(self):
        with self.lock:
            # 1. Save Master File
            all_insts = list(self.master_institutions.values())
            all_studs = list(self.master_students.values())
            passed = sum(1 for x in all_studs if x.get("status") == "PASSED" or "GPA" in str(x.get("result", "")))
            gpa5 = sum(1 for x in all_studs if str(x.get("gpa", "")) in ["5.00", "5", "5.0"])

            master_payload = {
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
            tmp_m = self.master_file + ".tmp"
            try:
                with open(tmp_m, "w", encoding="utf-8") as out:
                    json.dump(master_payload, out, indent=2, ensure_ascii=False)
                os.replace(tmp_m, self.master_file)
            except Exception:
                pass

            # 2. Save Upazila Files
            for key, entry in self.upazila_data.items():
                u_file = entry["file_path"]
                u_studs = list(entry["students_map"].values())
                u_insts = list(entry["institutions_map"].values())
                u_passed = sum(1 for x in u_studs if x.get("status") == "PASSED" or "GPA" in str(x.get("result", "")))
                u_gpa5 = sum(1 for x in u_studs if str(x.get("gpa", "")) in ["5.00", "5", "5.0"])

                u_payload = {
                    "board": "CHATTOGRAM",
                    "district": entry["data"].get("district", "CHATTOGRAM"),
                    "upazilla": entry["data"].get("upazilla", "UNKNOWN"),
                    "summary": {
                        "total_institutions": len(u_insts),
                        "total_records": len(u_studs),
                        "total_passed": u_passed,
                        "total_failed": len(u_studs) - u_passed,
                        "total_gpa_5": u_gpa5,
                        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                    },
                    "institutions": u_insts,
                    "records": u_studs
                }
                tmp_u = u_file + ".tmp"
                try:
                    with open(tmp_u, "w", encoding="utf-8") as uf_out:
                        json.dump(u_payload, uf_out, indent=2, ensure_ascii=False)
                    os.replace(tmp_u, u_file)
                except Exception:
                    pass


# =========================================================================
# 1. EIIN INSTITUTIONAL SCRAPING ENGINE (Writes Upazila JSONs & Master)
# =========================================================================
def run_ctg_eiin_scraper(
    eiins: List[str],
    results_root: Optional[str] = None
):
    eiins = sorted(list(dict.fromkeys(str(e).strip() for e in eiins if str(e).strip().isdigit() and len(str(e).strip()) == 6)))
    if not eiins:
        print(f"{RED}[!] No valid 6-digit EIINs provided.{RESET}", flush=True)
        return

    mgr = CtgResultsManager(results_root)
    proxies = load_proxies()

    print(f"\n=======================================================")
    print(f"🏛️  {BOLD}CHITTAGONG EIIN INSTITUTIONAL PIPELINE:{RESET}")
    print(f"  • Target Institutions: {GREEN}{BOLD}{len(eiins)} School EIINs{RESET}")
    print(f"  • Active Proxy Pool:   {CYAN}{BOLD}{len(proxies)} Dedicated Nodes{RESET}")
    print(f"  • District Storage:    {YELLOW}{mgr.root}/<ZILLA>/results_upazilla_<upz>.json{RESET}")
    print(f"  • Master All File:     {YELLOW}{mgr.master_file}{RESET}")
    print(f"=======================================================\n", flush=True)

    pending_eiins = [e for e in eiins if e not in mgr.master_institutions]
    if len(mgr.master_institutions) > 0:
        print(f"  • Already Scraped:     {GREEN}{len(mgr.master_institutions)} institutions (Skipping){RESET}")
        print(f"  • Pending to Scrape:   {YELLOW}{len(pending_eiins)} institutions{RESET}\n", flush=True)

    if not pending_eiins:
        print(f"{GREEN}✓ All {len(eiins)} institutions are already scraped! Total students in dataset: {len(mgr.master_students)}{RESET}", flush=True)
        return

    completed_inst_count = 0
    stats_lock = threading.Lock()
    print_lock = threading.Lock()
    batch_start_time = time.time()

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
            mgr.add_institution_and_students(res, studs)

            with print_lock:
                sys.stdout.write("\r\033[K")
                print(f" {cur_c:3d}/{cur_t}  EIIN {eiin_str}  {inst_name:<38}  {len(studs):3d} Students  {GREEN}✓ OK{RESET}", flush=True)
                sys.stdout.write(f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_c}/{cur_t} ({pct:.1f}%) │ 👥 {len(mgr.master_students)} Total Students")
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
            mgr.flush_to_disk()

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

    mgr.flush_to_disk()
    sys.stdout.write("\n\n")

    total_elapsed = time.time() - batch_start_time
    mins, secs = divmod(total_elapsed, 60)
    time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"

    print(f"=======================================================")
    print(f"🎉 {GREEN}{BOLD}CHITTAGONG INSTITUTIONAL SCRAPING COMPLETE!{RESET}")
    print(f"  • Institutions Processed: {len(mgr.master_institutions)}")
    print(f"  • Total Student Records:  {GREEN}{BOLD}{len(mgr.master_students)} Students{RESET}")
    print(f"  • Total Time Elapsed:     {CYAN}{time_str}{RESET}")
    print(f"  • District Folders:       {GREEN}{mgr.root}/<ZILLA>/results_upazilla_<upz>.json{RESET}")
    print(f"  • Master All File:        {GREEN}{mgr.master_file}{RESET}")
    print(f"=======================================================\n", flush=True)


# =========================================================================
# 2. INDIVIDUAL ROLL / RANGE SCRAPING ENGINE (Writes Upazila JSONs & Master)
# =========================================================================
def run_ctg_scraper(
    rolls: List[str],
    results_root: Optional[str] = None,
    force_recheck: bool = False
):
    rolls = sorted(list(dict.fromkeys(str(r).strip() for r in rolls if str(r).strip().isdigit())))
    if not rolls:
        print(f"{RED}[!] No valid 6-digit rolls provided.{RESET}", flush=True)
        return

    mgr = CtgResultsManager(results_root)
    cache_file = os.path.join(mgr.root, ".chittagong_memory_cache.json")
    proxies = load_proxies()

    print(f"\n=======================================================")
    print(f"🚀 {BOLD}CHITTAGONG ROLL SCRAPER PIPELINE CONFIGURATION:{RESET}")
    print(f"  • Requested Range:     {GREEN}{BOLD}{len(rolls)} Candidate Rolls{RESET}")
    print(f"  • Active Proxy Pool:   {CYAN}{BOLD}{len(proxies)} Dedicated Nodes{RESET}")
    print(f"  • District Storage:    {YELLOW}{mgr.root}/<ZILLA>/results_upazilla_<upz>.json{RESET}")
    print(f"  • Master All File:     {YELLOW}{mgr.master_file}{RESET}")
    print(f"=======================================================\n", flush=True)

    dead_slots = set()
    if not force_recheck and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as cf:
                cache_data = json.load(cf)
                dead_slots = set(str(x) for x in cache_data.get("dead_slots", []))
        except Exception:
            pass

    if force_recheck:
        pending_rolls = [r for r in rolls if r not in mgr.master_students]
    else:
        pending_rolls = [r for r in rolls if r not in mgr.master_students and r not in dead_slots]

    skipped_success = sum(1 for r in rolls if r in mgr.master_students)
    skipped_dead = sum(1 for r in rolls if r in dead_slots and r not in mgr.master_students)

    if skipped_success > 0 or skipped_dead > 0:
        print(f"🧠 {BOLD}CACHED MEMORY STATUS:{RESET}")
        if skipped_success > 0:
            print(f"  • Already Saved in Master: {GREEN}{skipped_success} rolls (Skipped - 100% Cached){RESET}")
        if skipped_dead > 0:
            print(f"  • Confirmed Dead Slots:    {DIM}{skipped_dead} empty rolls (Skipped - Already Checked){RESET}")
        print(f"  • Pending Live Queries:    {YELLOW}{len(pending_rolls)} rolls{RESET}\n", flush=True)

    if not pending_rolls:
        print(f"{GREEN}✓ All {len(rolls)} rolls in this range are already in dataset!{RESET}", flush=True)
        return

    dead_slots_set = set(dead_slots)
    dead_lock = threading.Lock()
    print_lock = threading.Lock()
    stats_lock = threading.Lock()
    recent_completions = collections.deque()
    recent_lock = threading.Lock()

    scraped_count = 0
    first_roll_time = [None]
    last_roll_time = [None]
    batch_start_time = time.time()

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
            student_obj = {
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
            mgr.add_single_student(student_obj)

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
            mgr.flush_to_disk()
            with dead_lock:
                try:
                    tmp_c = cache_file + ".tmp"
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

        return res

    num_threads = min(30, max(4, len(proxies) if proxies else 10))
    if len(pending_rolls) < num_threads:
        num_threads = len(pending_rolls)

    tasks = list(enumerate(pending_rolls))
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        try:
            list(executor.map(process_roll, tasks))
        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}[!] Pipeline interrupted by user. Saved records safely!{RESET}", flush=True)

    mgr.flush_to_disk()
    sys.stdout.write("\n\n")

    total_elapsed = time.time() - batch_start_time
    mins, secs = divmod(total_elapsed, 60)
    time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"

    print(f"=======================================================")
    print(f"🎉 {GREEN}{BOLD}CHITTAGONG BOARD SCRAPING COMPLETE!{RESET}")
    print(f"  • Total Master Students:  {GREEN}{len(mgr.master_students)}{RESET}")
    print(f"  • Total Dead Slots:       {DIM}{len(dead_slots_set)}{RESET}")
    print(f"  • Total Time Elapsed:     {CYAN}{time_str}{RESET}")
    print(f"  • District Folders:       {GREEN}{mgr.root}/<ZILLA>/results_upazilla_<upz>.json{RESET}")
    print(f"  • Master All File:        {GREEN}{mgr.master_file}{RESET}")
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
                    run_ctg_eiin_scraper(eiins)
            elif u_choice.isdigit() and 1 <= int(u_choice) <= len(upz_files):
                selected_upz_file = upz_files[int(u_choice) - 1]
                upz_name = os.path.splitext(os.path.basename(selected_upz_file))[0]
                with open(selected_upz_file, "r", encoding="utf-8") as uf:
                    eiins = [l.strip() for l in uf if l.strip().isdigit()]
                print(f"\n{GREEN}Selected: {selected_z} -> {upz_name} ({len(eiins)} institutions){RESET}", flush=True)
                run_ctg_eiin_scraper(eiins)
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
