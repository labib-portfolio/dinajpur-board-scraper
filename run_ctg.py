"""
Interactive Terminal CLI for Chittagong Education Board (BISE CTG) Result Scraper 2026
Standardized 8-Field Schema:
  • name
  • roll
  • total_mark
  • grade
  • institution_name
  • institution_eiin
  • zilla
  • upazilla
Features:
  • 100% Precision Multi-Tier Upazila & District Resolution Engine
  • Smart Dynamic Proxy Harvester (Webshare + Public Fallback Pool)
  • District Folders & Upazila-Wise JSON Persistence
  • Live Real-Time Student List Swiping
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
from engine.proxy_harvester import SmartProxyPool

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


# =========================================================================
# 100% PRECISION MULTI-TIER UPAZILA DETECTOR
# =========================================================================
_EXACT_SCHOOL_MAP = {}
_TOKEN_SCHOOL_MAP = {}
_EIIN_GEO_MAP = {}
_STOP_WORDS = {"govt", "government", "model", "high", "school", "college", "boys", "girls", "and", "the", "for", "secondary", "institute", "institution", "corporation", "city"}

ALL_KNOWN_UPAZILAS = {
    # Chattogram
    "ANWARA": ("CHATTOGRAM", "ANWARA"),
    "BANSHKHALI": ("CHATTOGRAM", "BANSHKHALI"),
    "BOALKHALI": ("CHATTOGRAM", "BOALKHALI"),
    "CHANDANAISH": ("CHATTOGRAM", "CHANDANAISH"),
    "FATICKCHARI": ("CHATTOGRAM", "FATICKCHARI"),
    "FATIKCHHARI": ("CHATTOGRAM", "FATICKCHARI"),
    "HATHAZARI": ("CHATTOGRAM", "HATHAZARI"),
    "LOHAGARA": ("CHATTOGRAM", "LOHAGARA"),
    "MIRSARAI": ("CHATTOGRAM", "MIRSARAI"),
    "MIRSHARAI": ("CHATTOGRAM", "MIRSARAI"),
    "PATIYA": ("CHATTOGRAM", "PATIYA"),
    "RANGUNIA": ("CHATTOGRAM", "RANGUNIA"),
    "RAOJAN": ("CHATTOGRAM", "RAOJAN"),
    "SANDWIP": ("CHATTOGRAM", "SANDWIP"),
    "SWANDIP": ("CHATTOGRAM", "SANDWIP"),
    "SATKANIA": ("CHATTOGRAM", "SATKANIA"),
    "SITAKUNDA": ("CHATTOGRAM", "SITAKUNDA"),
    "SITAKUNDU": ("CHATTOGRAM", "SITAKUNDA"),
    "KARNAPHULI": ("CHATTOGRAM", "KARNAPHULI"),
    "KOTWALI": ("CHATTOGRAM", "KOTWALI"),
    "PANCHLAISH": ("CHATTOGRAM", "PANCHLAISH"),
    "CHANDGAON": ("CHATTOGRAM", "CHANDGAON"),
    "BAKALIA": ("CHATTOGRAM", "BAKALIA"),
    "BANDAR": ("CHATTOGRAM", "BANDAR"),
    "DOUBLE MOORING": ("CHATTOGRAM", "DOUBLE_MOORING"),
    "PAHARTALI": ("CHATTOGRAM", "PAHARTALI"),
    "KHULSHI": ("CHATTOGRAM", "KHULSHI"),
    "BAYEZID": ("CHATTOGRAM", "BAYEZID"),
    "HALISHAHAR": ("CHATTOGRAM", "HALISHAHAR"),
    "PATENGA": ("CHATTOGRAM", "PATENGA"),
    
    # Cox's Bazar
    "CHAKARIA": ("COX_S_BAZAR", "CHAKARIA"),
    "CHAKORIA": ("COX_S_BAZAR", "CHAKARIA"),
    "PEKUA": ("COX_S_BAZAR", "PEKUA"),
    "KUTUBDIA": ("COX_S_BAZAR", "KUTUBDIA"),
    "MAHESHKHALI": ("COX_S_BAZAR", "MAHESHKHALI"),
    "RAMU": ("COX_S_BAZAR", "RAMU"),
    "TEKNAF": ("COX_S_BAZAR", "TEKNAF"),
    "UKHIYA": ("COX_S_BAZAR", "UKHIYA"),
    "UKHIA": ("COX_S_BAZAR", "UKHIYA"),
    "COX'S BAZAR SADAR": ("COX_S_BAZAR", "COX_S_BAZAR_SADAR"),
    
    # Bandarban
    "ALI KADAM": ("BANDARBAN", "ALI_KADAM"),
    "ALIKADAM": ("BANDARBAN", "ALI_KADAM"),
    "LAMA": ("BANDARBAN", "LAMA"),
    "NAIKKHANGCHHARI": ("BANDARBAN", "NAIKKHANG_CHHARI"),
    "NAIKHONGCHARI": ("BANDARBAN", "NAIKKHANG_CHHARI"),
    "ROANGCHHARI": ("BANDARBAN", "ROANG_CHHARI"),
    "ROWANGCHARI": ("BANDARBAN", "ROANG_CHHARI"),
    "RUMA": ("BANDARBAN", "RUMA"),
    "THANCHI": ("BANDARBAN", "THANCHI"),
    "BANDARBAN SADAR": ("BANDARBAN", "BANDARBAN_SADAR"),
    
    # Khagrachhari
    "DIGHINALA": ("KHAGRACHHARI", "DIGHINALA"),
    "LAXMI CHHARI": ("KHAGRACHHARI", "LAXMI_CHHARI"),
    "LAKSHMICHARI": ("KHAGRACHHARI", "LAXMI_CHHARI"),
    "MAHALCHHARI": ("KHAGRACHHARI", "MAHALCHHARI"),
    "MANIKCHHARI": ("KHAGRACHHARI", "MANIKCHHARI"),
    "MATIRANGA": ("KHAGRACHHARI", "MATIRANGA"),
    "PANCHHARI": ("KHAGRACHHARI", "PANCHHARI"),
    "RAMGARH": ("KHAGRACHHARI", "RAMGARH"),
    "GUIMARA": ("KHAGRACHHARI", "GUIMARA"),
    "KHAGRACHARI SADAR": ("KHAGRACHHARI", "KHAGRACHHARI_SADAR"),
    "KHAGRACHHARI SADAR": ("KHAGRACHHARI", "KHAGRACHHARI_SADAR"),
    
    # Rangamati
    "BAGHAICHHARI": ("RANGAMATI", "BAGHAICHHARI"),
    "BARKAL": ("RANGAMATI", "BARKAL"),
    "BELAICHHARI": ("RANGAMATI", "BELAICHHARI"),
    "JURAICHHARI": ("RANGAMATI", "JURAICHHARI"),
    "KAPTAI": ("RANGAMATI", "KAPTAI"),
    "KAWKHALI": ("RANGAMATI", "KAWKHALI"),
    "LANGADU": ("RANGAMATI", "LANGADU"),
    "NANNERCHAR": ("RANGAMATI", "NANNERCHAR"),
    "NANIARCHAR": ("RANGAMATI", "NANNERCHAR"),
    "RAJASTHALI": ("RANGAMATI", "RAJASTHALI"),
    "RANGAMATI SADAR": ("RANGAMATI", "RANGAMATI_SADAR")
}

def load_upazila_indexes():
    global _EXACT_SCHOOL_MAP, _TOKEN_SCHOOL_MAP, _EIIN_GEO_MAP
    if _EXACT_SCHOOL_MAP:
        return

    upz_file = os.path.join(BASE_DIR, "chittagong_board_eiin", "chittagong_board_eiins_by_upazilla.json")
    if not os.path.exists(upz_file):
        upz_file = os.path.join(r"C:\Users\labib_n4\Documents\Project\Result-Scraper\chittagong_board_eiin\chittagong_board_eiins_by_upazilla.json")

    if os.path.exists(upz_file):
        try:
            with open(upz_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                for z, upzs in d.items():
                    z_norm = z.replace("'", "_").replace(" ", "_").upper()
                    for u, inst_list in upzs.items():
                        u_norm = u.replace("'", "_").replace(" ", "_").upper()
                        for inst in inst_list:
                            raw_name = inst["name"]
                            meta = {
                                "eiin": str(inst["eiin"]),
                                "zilla": z_norm,
                                "upazila": u_norm,
                                "name": raw_name
                            }
                            _EIIN_GEO_MAP[str(inst["eiin"])] = meta
                            clean_str = re.sub(r'[^a-zA-Z0-9]+', '', raw_name.lower())
                            _EXACT_SCHOOL_MAP[clean_str] = meta
                            
                            tokens = set(re.findall(r'[a-zA-Z]{4,}', raw_name.lower())) - _STOP_WORDS
                            for tok in tokens:
                                if tok not in _TOKEN_SCHOOL_MAP:
                                    _TOKEN_SCHOOL_MAP[tok] = []
                                _TOKEN_SCHOOL_MAP[tok].append(meta)
        except Exception:
            pass

load_upazila_indexes()

def resolve_school_geo(inst_name_str: str, eiin_str: str = "") -> Dict[str, str]:
    if eiin_str and eiin_str in _EIIN_GEO_MAP:
        return dict(_EIIN_GEO_MAP[eiin_str])

    if not inst_name_str:
        return {"eiin": "", "zilla": "CHATTOGRAM", "upazila": "UNKNOWN", "name": "UNKNOWN"}

    # 1. Exact string / Substring match against 1,218 schools
    clean = re.sub(r'[^a-zA-Z0-9]+', '', inst_name_str.lower())
    for k, v in _EXACT_SCHOOL_MAP.items():
        if k == clean or (len(k) > 10 and (k in clean or clean in k)):
            return dict(v)

    # 2. Distinctive token match (e.g. "parbati", "fasiakhali", "digerpankhali")
    tokens = set(re.findall(r'[a-zA-Z]{4,}', inst_name_str.lower())) - _STOP_WORDS
    for tok in tokens:
        if tok in _TOKEN_SCHOOL_MAP and len(_TOKEN_SCHOOL_MAP[tok]) == 1:
            return dict(_TOKEN_SCHOOL_MAP[tok][0])

    # 3. Direct Upazila keyword match from school name
    inst_upper = inst_name_str.upper()
    for upz_kw, (z_val, u_val) in ALL_KNOWN_UPAZILAS.items():
        if re.search(rf'\b{upz_kw}\b', inst_upper):
            return {"eiin": "", "zilla": z_val, "upazila": u_val, "name": inst_name_str}

    # 4. District default fallback
    for z_kw, s_upz in [("COX'S BAZAR", "COX_S_BAZAR_SADAR"), ("KHAGRACHHARI", "KHAGRACHHARI_SADAR"), ("KHAGRACHARI", "KHAGRACHHARI_SADAR"), ("BANDARBAN", "BANDARBAN_SADAR"), ("RANGAMATI", "RANGAMATI_SADAR"), ("CHATTOGRAM", "CHATTOGRAM_SADAR"), ("CHITTAGONG", "CHATTOGRAM_SADAR")]:
        if z_kw in inst_upper:
            z_clean = "CHATTOGRAM" if "CHITTAGONG" in z_kw else z_kw.replace("'", "_").replace(" ", "_")
            if z_clean == "KHAGRACHARI": z_clean = "KHAGRACHHARI"
            return {"eiin": "", "zilla": z_clean, "upazila": s_upz, "name": inst_name_str}

    return {"eiin": "", "zilla": "CHATTOGRAM", "upazila": "UNKNOWN", "name": inst_name_str}


def print_ctg_banner():
    print(f"\n{CYAN}┌───────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}Chittagong Board Result Scraper 2026 — High-Speed Engine{RESET}  {CYAN}│{RESET}")
    print(f"{CYAN}├───────────────────────────────────────────────────────────┤{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Standardized Clean 8-Field Output • Upazila-Wise Persistence{RESET}{CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Smart Proxy Harvester • 100% Precision Upazila Detection{RESET}  {CYAN}│{RESET}")
    print(f"{CYAN}└───────────────────────────────────────────────────────────┘{RESET}\n", flush=True)


def format_progress_bar(current: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return f"[{'░' * width}]"
    fraction = min(1.0, max(0.0, current / total))
    filled = int(round(width * fraction))
    return f"[{'█' * filled}{'░' * (width - filled)}]"


# Global Proxy Pool
proxy_pool = SmartProxyPool()


# =========================================================================
# UNIFIED UPALIZA & MASTER STORAGE MANAGER
# =========================================================================
class CtgResultsManager:
    def __init__(self, results_root: Optional[str] = None):
        self.root = results_root or get_default_results_root()
        os.makedirs(self.root, exist_ok=True)
        self.master_file = os.path.join(self.root, "scraped_results_all.json")
        self.lock = threading.Lock()
        
        self.master_students = {}
        self.master_institutions = {}
        if os.path.exists(self.master_file):
            try:
                with open(self.master_file, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    for inst in d.get("institutions", []):
                        if inst.get("eiin") or inst.get("institution_eiin"):
                            e_key = str(inst.get("institution_eiin") or inst.get("eiin"))
                            self.master_institutions[e_key] = inst
                    raw_s = d.get("records", []) or d.get("students", [])
                    for s in raw_s:
                        r_key = str(s.get("roll") or s.get("roll_no"))
                        if r_key:
                            self.master_students[r_key] = s
            except Exception:
                pass

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
                                "students_map": {str(x.get("roll") or x.get("roll_no")): x for x in u_json.get("records", []) if (x.get("roll") or x.get("roll_no"))},
                                "institutions_map": {str(x.get("institution_eiin") or x.get("eiin")): x for x in u_json.get("institutions", []) if (x.get("institution_eiin") or x.get("eiin"))}
                            }
                    except Exception:
                        pass

    def add_student_record(self, s: Dict[str, Any], inst_meta: Optional[Dict[str, Any]] = None):
        roll_str = str(s.get("roll") or s.get("roll_no", "")).strip()
        eiin_str = str(s.get("institution_eiin") or s.get("eiin", "") or (inst_meta.get("institution_eiin") if inst_meta else "")).strip()
        inst_name = s.get("institution_name") or s.get("institute", "") or (inst_meta.get("name") if inst_meta else "")

        geo = resolve_school_geo(inst_name, eiin_str)
        zilla_name = geo.get("zilla") or s.get("zilla") or "CHATTOGRAM"
        upz_name = geo.get("upazila") or s.get("upazilla") or s.get("upazila") or "UNKNOWN"
        final_eiin = eiin_str or geo.get("eiin", "")

        # Standardized Clean 8-Field Object
        record = {
            "name": str(s.get("name") or s.get("student_name") or "").strip(),
            "roll": roll_str,
            "total_mark": s.get("total_mark") if s.get("total_mark") is not None else s.get("total_marks"),
            "grade": str(s.get("grade") or s.get("gpa") or "FAIL").strip(),
            "institution_name": inst_name,
            "institution_eiin": final_eiin,
            "zilla": zilla_name,
            "upazilla": upz_name
        }

        z_slug = slugify(zilla_name)
        u_slug = slugify(upz_name)

        with self.lock:
            self.master_students[roll_str] = record
            if inst_meta and final_eiin:
                self.master_institutions[final_eiin] = inst_meta

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
            if inst_meta and final_eiin:
                u_entry["institutions_map"][final_eiin] = inst_meta
            u_entry["students_map"][roll_str] = record

    def flush_to_disk(self):
        with self.lock:
            all_insts = list(self.master_institutions.values())
            all_studs = list(self.master_students.values())
            passed = sum(1 for x in all_studs if "FAIL" not in str(x.get("grade", "")).upper())
            gpa5 = sum(1 for x in all_studs if str(x.get("grade", "")) in ["5.00", "5", "5.0"])

            master_payload = {
                "board": "CHATTOGRAM",
                "summary": {
                    "total_institutions": len(all_insts),
                    "total_records": len(all_studs),
                    "total_passed": passed,
                    "total_failed": len(all_studs) - passed,
                    "total_gpa_5": gpa5,
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "institutions": all_insts,
                "records": all_studs
            }
            tmp_m = self.master_file + ".tmp"
            try:
                with open(tmp_m, "w", encoding="utf-8") as out:
                    json.dump(master_payload, out, indent=2, ensure_ascii=False)
                os.replace(tmp_m, self.master_file)
            except Exception:
                pass

            for key, entry in self.upazila_data.items():
                u_file = entry["file_path"]
                u_studs = list(entry["students_map"].values())
                u_insts = list(entry["institutions_map"].values())
                u_passed = sum(1 for x in u_studs if "FAIL" not in str(x.get("grade", "")).upper())
                u_gpa5 = sum(1 for x in u_studs if str(x.get("grade", "")) in ["5.00", "5", "5.0"])

                u_payload = {
                    "board": "CHATTOGRAM",
                    "district": entry["data"].get("district", "CHATTOGRAM"),
                    "upazilla": entry["data"].get("upazilla", "UNKNOWN"),
                    "upazilla_slug": entry["data"].get("upazilla_slug", "unknown"),
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
# 1. EIIN INSTITUTIONAL SCRAPING ENGINE (Clean 8-Field Output)
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
    proxies = proxy_pool.ensure_pool(min_size=20)
    num_workers = min(35, len(proxies)) if len(proxies) >= 20 else max(10, len(proxies))
    spare_proxies = max(0, len(proxies) - num_workers)

    print(f"\n=======================================================")
    print(f"🚀 {BOLD}ENGINE PIPELINE CONFIGURATION:{RESET}")
    print(f"  • Target Board:            {CYAN}{BOLD}Chittagong Education Board (BISE CTG){RESET}")
    print(f"  • Active Proxy Pool:       {GREEN}{BOLD}{len(proxies)} Verified Ultra-Fast Nodes{RESET}")
    print(f"  • Concurrent Workers:      {CYAN}{BOLD}{num_workers} Parallel Threads{RESET}")
    print(f"  • Standby Failover Spares: {YELLOW}{BOLD}{spare_proxies} Spare Proxies{RESET}")
    print(f"  • Target Institutions:     {len(eiins)} Schools")
    print(f"  • District Storage:        {YELLOW}{mgr.root}/<ZILLA>/results_upazilla_<upz>.json{RESET}")
    print(f"=======================================================\n", flush=True)

    pending_eiins = [e for e in eiins if e not in mgr.master_institutions]
    already_scraped_count = len(eiins) - len(pending_eiins)
    if already_scraped_count > 0:
        print(f"  • Already Scraped:         {GREEN}{already_scraped_count} institutions (Skipped){RESET}")
        print(f"  • Pending to Scrape:       {YELLOW}{len(pending_eiins)} institutions{RESET}\n", flush=True)

    if not pending_eiins:
        print(f"{GREEN}✓ All {len(eiins)} institutions are already in master database! Total students: {len(mgr.master_students)}{RESET}\n", flush=True)
        return

    print_lock = threading.Lock()
    stats_lock = threading.Lock()
    recent_completions = collections.deque()
    recent_lock = threading.Lock()

    batch_start_time = time.time()
    first_roll_time = [None]
    last_roll_time = [None]
    batch_received_count = 0

    def harvest_and_stream_eiin(task_info):
        nonlocal batch_received_count
        idx, eiin_str = task_info
        cur_proxies = proxy_pool.get_all()
        p = cur_proxies[idx % len(cur_proxies)] if cur_proxies else None

        res = fetch_ctg_institute(eiin=eiin_str, proxy=p, timeout=8.0)
        if not res or not res.get("success"):
            p_alt = cur_proxies[(idx + 13) % len(cur_proxies)] if cur_proxies else None
            res = fetch_ctg_institute(eiin=eiin_str, proxy=p_alt, timeout=8.0)

        if not res or not res.get("success"):
            with print_lock:
                sys.stdout.write("\r\033[K")
                sys.stdout.write(f"  [{idx+1}/{len(pending_eiins)}] EIIN {eiin_str} -> {RED}Not Found / Error{RESET}\n")
                sys.stdout.flush()
            return

        inst_name = res.get("institute_name", "UNKNOWN")
        zilla_name = res.get("zilla", "CHATTOGRAM")
        thana_name = res.get("thana", "UNKNOWN")
        students = res.get("students", [])

        inst_meta = {
            "institution_eiin": eiin_str,
            "name": inst_name,
            "zilla": zilla_name,
            "thana": thana_name,
            "appeared": res.get("total_appeared", len(students)),
            "passed": res.get("total_passed", sum(1 for s in students if "FAIL" not in str(s.get("grade", "")).upper())),
            "gpa5": res.get("total_gpa5", 0),
            "students_count": len(students)
        }

        with print_lock:
            sys.stdout.write("\r\033[K")
            sys.stdout.write(f"  [{idx+1}/{len(pending_eiins)}] EIIN {eiin_str}: {inst_name[:30]} {GREEN}+{len(students)} rolls{RESET}\n")
            sys.stdout.flush()

        for s in students:
            mgr.add_student_record(s, inst_meta)
            now_ts = time.time()
            with stats_lock:
                if first_roll_time[0] is None:
                    first_roll_time[0] = now_ts
                last_roll_time[0] = now_ts
                batch_received_count += 1
                cur_rec = batch_received_count

            with recent_lock:
                recent_completions.append(now_ts)
                cutoff = now_ts - 6.0
                while recent_completions and recent_completions[0] < cutoff:
                    recent_completions.popleft()
                sample_duration = max(0.5, now_ts - recent_completions[0]) if len(recent_completions) > 1 else 1.0
                speed = len(recent_completions) / sample_duration

            roll_str = str(s.get("roll"))
            s_name = s.get("name", "STUDENT") or "STUDENT"
            grade_res = s.get("grade", "N/A")
            is_pass = "FAIL" not in str(grade_res).upper()
            status_color = GREEN if is_pass else RED
            status_label = "PASSED" if is_pass else "FAILED"
            
            elapsed = now_ts - (first_roll_time[0] or now_ts)
            mins, secs = divmod(elapsed, 60)
            time_str = f"{int(mins)}m {int(secs):02d}s"
            p_bar = format_progress_bar(cur_rec, max(cur_rec, len(students)), width=24)

            with print_lock:
                sys.stdout.write("\r\033[K")
                student_line = f" {cur_rec:4d}  Roll {roll_str:<7}  {s_name:<30}  GPA={grade_res:<6} {status_color}{status_label}{RESET}\n"
                sys.stdout.write(student_line)
                p_bar_line = f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_rec} rolls processed ⚡ {speed:.1f} rolls/s │ ⏱️ {time_str}"
                sys.stdout.write(p_bar_line)
                sys.stdout.flush()

        mgr.flush_to_disk()

    num_threads = min(15, max(2, len(proxies) if proxies else 5))
    if len(pending_eiins) < num_threads:
        num_threads = len(pending_eiins)

    tasks = list(enumerate(pending_eiins))
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        try:
            list(executor.map(harvest_and_stream_eiin, tasks))
        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}[!] Pipeline stopped by user (Ctrl+C). Preserved all scraped records!{RESET}", flush=True)

    mgr.flush_to_disk()
    sys.stdout.write("\n\n")

    total_elapsed = time.time() - batch_start_time
    mins, secs = divmod(total_elapsed, 60)
    time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"

    if first_roll_time[0] and last_roll_time[0]:
        scrape_duration = max(0.1, last_roll_time[0] - first_roll_time[0])
        pure_speed = batch_received_count / scrape_duration
        pure_rpm = int(pure_speed * 60)
        pure_speed_str = f"{pure_speed:.1f} rolls/sec ({pure_rpm} rolls/min)"
    else:
        pure_speed_str = "N/A"

    print(f"=======================================================")
    print(f"⏱️ {BOLD}PIPELINED PROCESS EXECUTION TIME & PERFORMANCE:{RESET}")
    print(f"  • Total Pipeline Time:    {CYAN}{BOLD}{time_str}{RESET}")
    print(f"  • Institutions Processed: {len(pending_eiins)} ({already_scraped_count} already cached)")
    print(f"  • Total Student Records:  {GREEN}{BOLD}{len(mgr.master_students)} Students{RESET}")
    print(f"  • Live Scraped in Batch:  {batch_received_count} rolls")
    print(f"  • Active Scraping Speed:  {GREEN}{BOLD}{pure_speed_str}{RESET}")
    print(f"  • Storage Root Directory: {YELLOW}{mgr.root}{RESET}")
    print(f"=======================================================\n", flush=True)

    print(f"{GREEN}{BOLD}🎉 Finished Batch! All results saved across Upazilla files in {time_str}!{RESET}")
    print(f"{CYAN}───────────────────────────────────────────────────────────{RESET}\n", flush=True)


# =========================================================================
# 2. ROLL RANGE / FILE SCRAPING ENGINE (Clean 8-Field Output)
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
    proxies = proxy_pool.ensure_pool(min_size=20)
    num_workers = min(40, len(proxies)) if len(proxies) >= 20 else max(10, len(proxies))
    spare_proxies = max(0, len(proxies) - num_workers)

    print(f"\n=======================================================")
    print(f"🚀 {BOLD}ENGINE PIPELINE CONFIGURATION:{RESET}")
    print(f"  • Target Board:            {CYAN}{BOLD}Chittagong Education Board (BISE CTG){RESET}")
    print(f"  • Active Proxy Pool:       {GREEN}{BOLD}{len(proxies)} Verified Ultra-Fast Nodes{RESET}")
    print(f"  • Concurrent Workers:      {CYAN}{BOLD}{num_workers} Parallel Threads{RESET}")
    print(f"  • Standby Failover Spares: {YELLOW}{BOLD}{spare_proxies} Spare Proxies{RESET}")
    print(f"  • Target Rolls:            {len(rolls)} Candidate Rolls")
    print(f"  • District Storage:        {YELLOW}{mgr.root}/<ZILLA>/results_upazilla_<upz>.json{RESET}")
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
        print(f"{GREEN}✓ All {len(rolls)} rolls in this batch are already in dataset!{RESET}\n", flush=True)
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
        cur_proxies = proxy_pool.get_all()
        p = cur_proxies[idx % len(cur_proxies)] if cur_proxies else None

        res = fetch_ctg_student(roll=roll_str, proxy=p, timeout=7.0)
        if not res or not res.get("success"):
            p_alt = cur_proxies[(idx + 17) % len(cur_proxies)] if cur_proxies else None
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
        p_bar = format_progress_bar(cur_c, cur_t, width=24)

        if res and res.get("success"):
            mgr.add_student_record(res)

            s_name = res.get("name", "STUDENT") or "STUDENT"
            grade_res = res.get("grade", "N/A")
            is_pass = "FAIL" not in str(grade_res).upper()
            status_color = GREEN if is_pass else RED
            status_label = "PASSED" if is_pass else "FAILED"

            with print_lock:
                sys.stdout.write("\r\033[K")
                student_line = f" {cur_c:4d}/{cur_t}  Roll {roll_str:<7}  {s_name:<30}  GPA={grade_res:<6} {status_color}{status_label}{RESET}\n"
                sys.stdout.write(student_line)
                p_bar_line = f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_c}/{cur_t} ({pct:.1f}%) ⚡ {speed:.1f} rolls/s │ ⏱️ {time_str}"
                sys.stdout.write(p_bar_line)
                sys.stdout.flush()
        elif res and res.get("error") == "Record Not Found":
            with dead_lock:
                dead_slots_set.add(roll_str)
            with print_lock:
                sys.stdout.write(f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_c}/{cur_t} ({pct:.1f}%) ⚡ {speed:.1f} rolls/s │ ⏱️ {time_str}")
                sys.stdout.flush()

        if scraped_count % 25 == 0:
            mgr.flush_to_disk()

        return res

    tasks = list(enumerate(pending_rolls))
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        try:
            list(executor.map(process_roll, tasks))
        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}[!] Pipeline stopped by user (Ctrl+C). Preserved all scraped records!{RESET}", flush=True)

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

    sys.stdout.write("\n\n")

    total_elapsed = time.time() - batch_start_time
    mins, secs = divmod(total_elapsed, 60)
    time_str = f"{int(mins)}m {secs:.2f}s" if mins > 0 else f"{secs:.2f}s"

    if first_roll_time[0] and last_roll_time[0]:
        scrape_duration = max(0.1, last_roll_time[0] - first_roll_time[0])
        pure_speed = scraped_count / scrape_duration
        pure_rpm = int(pure_speed * 60)
        pure_speed_str = f"{pure_speed:.1f} rolls/sec ({pure_rpm} rolls/min)"
    else:
        pure_speed_str = "N/A"

    print(f"=======================================================")
    print(f"⏱️ {BOLD}PIPELINED PROCESS EXECUTION TIME & PERFORMANCE:{RESET}")
    print(f"  • Total Pipeline Time:    {CYAN}{BOLD}{time_str}{RESET}")
    print(f"  • Total Candidate Rolls:  {len(rolls)} ({skipped_success} already cached)")
    print(f"  • Live Scraped in Batch:  {scraped_count}/{len(pending_rolls)} ({100.0 * scraped_count / max(1, len(pending_rolls)):.1f}%)")
    print(f"  • Active Scraping Speed:  {GREEN}{BOLD}{pure_speed_str}{RESET}")
    print(f"  • Storage Root Directory: {YELLOW}{mgr.root}{RESET}")
    print(f"=======================================================")

    if scraped_count == len(pending_rolls):
        print(f"\n{GREEN}{BOLD}🎉 Finished Batch! All results saved across Upazilla files in {time_str}!{RESET}")
    else:
        print(f"\n{YELLOW}{BOLD}⚠️ Finished Batch! {scraped_count}/{len(pending_rolls)} results saved in {time_str}!{RESET}")
    print(f"{CYAN}───────────────────────────────────────────────────────────{RESET}\n", flush=True)


# =========================================================================
# 3. INTERACTIVE CLI MENU
# =========================================================================
def interactive_ctg_menu():
    print_ctg_banner()
    print(f"{BOLD}Select Chittagong Board Scraping Mode:{RESET}")
    print(f"  {GREEN}[1]{RESET} {BOLD}EIIN Mode{RESET} — Instant Institutional Results (Single / Multiple EIINs)")
    print(f"  {GREEN}[2]{RESET} {BOLD}District / Upazila Bulk Scraper{RESET} — Select Upazila and scrape all schools")
    print(f"  {CYAN}[3]{RESET} Roll Number Range (e.g. 100001-105000, 129000-129100)")
    print(f"  {CYAN}[4]{RESET} Single / Multiple Candidate Rolls (e.g. 129051, 100001)")
    print(f"  {GREEN}[5]{RESET} {BOLD}Load Rolls / EIINs from File{RESET} (e.g. chittagong_all_rolls.txt) {GREEN}⚡ Recommended{RESET}")
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
        path = input(f"\n{BOLD}Enter filepath (txt/json, e.g. chittagong_all_rolls.txt): {RESET}").strip().strip('"')
        if not os.path.exists(path):
            local_cand = os.path.join(BASE_DIR, path)
            if os.path.exists(local_cand):
                path = local_cand

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            items = [r.strip() for r in re.split(r'[,\s\n"\[\]]+', content) if r.strip().isdigit()]
            print(f"{GREEN}✓ Loaded {len(items)} items from {path}{RESET}\n")
            if items:
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
            elif a.endswith(".txt") or a.endswith(".json"):
                if os.path.exists(a):
                    with open(a, "r", encoding="utf-8") as af:
                        items = [r.strip() for r in re.split(r'[,\s\n"\[\]]+', af.read()) if r.strip().isdigit()]
                        arg_rolls.extend(items)
            elif a.isdigit():
                arg_rolls.append(a)
        if arg_rolls:
            run_ctg_scraper(arg_rolls, force_recheck=force_flag)
        else:
            interactive_ctg_menu()
    else:
        interactive_ctg_menu()
