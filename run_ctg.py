"""
Interactive Terminal CLI for Chittagong Education Board (BISE CTG) Result Scraper 2026
High-Speed Non-Blocking Asynchronous Streaming Architecture (Zero-Freeze / Zero-Stuck)
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
import requests
from requests.adapters import HTTPAdapter

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
    fetch_ctg_institute,
    INDIVIDUAL_ENDPOINT,
    INSTITUTION_ENDPOINT
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
# 100% PRECISION MULTI-TIER UPAZILA DETECTOR (WITH O(1) MEMOIZATION CACHE)
# =========================================================================
_EXACT_SCHOOL_MAP = {}
_TOKEN_SCHOOL_MAP = {}
_EIIN_GEO_MAP = {}
_GEO_RESOLVER_CACHE = {}
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
    cache_key = (inst_name_str, eiin_str)
    if cache_key in _GEO_RESOLVER_CACHE:
        return _GEO_RESOLVER_CACHE[cache_key]

    if eiin_str and eiin_str in _EIIN_GEO_MAP:
        res = dict(_EIIN_GEO_MAP[eiin_str])
        _GEO_RESOLVER_CACHE[cache_key] = res
        return res

    if not inst_name_str:
        res = {"eiin": "", "zilla": "CHATTOGRAM", "upazila": "UNKNOWN", "name": "UNKNOWN"}
        _GEO_RESOLVER_CACHE[cache_key] = res
        return res

    clean = re.sub(r'[^a-zA-Z0-9]+', '', inst_name_str.lower())
    for k, v in _EXACT_SCHOOL_MAP.items():
        if k == clean or (len(k) > 10 and (k in clean or clean in k)):
            res = dict(v)
            _GEO_RESOLVER_CACHE[cache_key] = res
            return res

    tokens = set(re.findall(r'[a-zA-Z]{4,}', inst_name_str.lower())) - _STOP_WORDS
    for tok in tokens:
        if tok in _TOKEN_SCHOOL_MAP and len(_TOKEN_SCHOOL_MAP[tok]) == 1:
            res = dict(_TOKEN_SCHOOL_MAP[tok][0])
            _GEO_RESOLVER_CACHE[cache_key] = res
            return res

    inst_upper = inst_name_str.upper()
    for upz_kw, (z_val, u_val) in ALL_KNOWN_UPAZILAS.items():
        if re.search(rf'\b{upz_kw}\b', inst_upper):
            res = {"eiin": "", "zilla": z_val, "upazila": u_val, "name": inst_name_str}
            _GEO_RESOLVER_CACHE[cache_key] = res
            return res

    for z_kw, s_upz in [("COX'S BAZAR", "COX_S_BAZAR_SADAR"), ("KHAGRACHHARI", "KHAGRACHHARI_SADAR"), ("KHAGRACHARI", "KHAGRACHHARI_SADAR"), ("BANDARBAN", "BANDARBAN_SADAR"), ("RANGAMATI", "RANGAMATI_SADAR"), ("CHATTOGRAM", "CHATTOGRAM_SADAR"), ("CHITTAGONG", "CHATTOGRAM_SADAR")]:
        if z_kw in inst_upper:
            z_clean = "CHATTOGRAM" if "CHITTAGONG" in z_kw else z_kw.replace("'", "_").replace(" ", "_")
            if z_clean == "KHAGRACHARI": z_clean = "KHAGRACHHARI"
            res = {"eiin": "", "zilla": z_clean, "upazila": s_upz, "name": inst_name_str}
            _GEO_RESOLVER_CACHE[cache_key] = res
            return res

    res = {"eiin": "", "zilla": "CHATTOGRAM", "upazila": "UNKNOWN", "name": inst_name_str}
    _GEO_RESOLVER_CACHE[cache_key] = res
    return res


def print_ctg_banner():
    print(f"\n{CYAN}┌───────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}Chittagong Board Result Scraper 2026 — High-Speed Engine{RESET}  {CYAN}│{RESET}")
    print(f"{CYAN}├───────────────────────────────────────────────────────────┤{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Standardized Clean 8-Field Output • Subject Breakdown Mode{RESET}  {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Zero-Freeze Non-Blocking Stream • 100% Upazila Detection{RESET}   {CYAN}│{RESET}")
    print(f"{CYAN}└───────────────────────────────────────────────────────────┘{RESET}\n", flush=True)


def format_progress_bar(current: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return f"[{'░' * width}]"
    fraction = min(1.0, max(0.0, current / total))
    filled = int(round(width * fraction))
    return f"[{'█' * filled}{'░' * (width - filled)}]"


proxy_pool = SmartProxyPool()


def create_isolated_session(proxy: Optional[str] = None) -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=0)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    if proxy:
        parts = proxy.split(":")
        if len(parts) == 4:
            ip, port, user, pwd = parts
            proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
        else:
            proxy_url = f"http://{proxy}"
        session.proxies.update({"http": proxy_url, "https": proxy_url})

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Origin": "https://sresult.bise-ctg.gov.bd",
        "Referer": "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/",
        "Connection": "keep-alive"
    })
    return session


# =========================================================================
# ULTRA-LOW CPU PERSISTENCE MANAGER WITH INSTITUTION AGGREGATOR
# =========================================================================
class CtgResultsManager:
    def __init__(self, results_root: Optional[str] = None):
        self.root = results_root or get_default_results_root()
        os.makedirs(self.root, exist_ok=True)
        self.master_file = os.path.join(self.root, "scraped_results_all.json")
        self.lock = threading.Lock()
        
        self.master_students = {}
        self.master_institutions = {}
        self.dirty_upazilas = set()
        self.last_flush_time = time.time()

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

        # Include subject breakdown if present
        if "subjects" in s:
            record["subjects"] = s["subjects"]

        z_slug = slugify(zilla_name)
        u_slug = slugify(upz_name)
        key = (z_slug, u_slug)

        with self.lock:
            self.master_students[roll_str] = record
            if inst_meta and final_eiin:
                self.master_institutions[final_eiin] = inst_meta

            if key not in self.upazila_data:
                z_folder = os.path.join(self.root, zilla_name)
                os.makedirs(z_folder, exist_ok=True)
                u_file = os.path.join(z_folder, f"results_upazilla_{u_slug}.json")
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
            self.dirty_upazilas.add(key)

    def _build_institutions_summary(self, records: List[Dict[str, Any]], existing_insts: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        groups = collections.defaultdict(list)
        for r in records:
            eiin_raw = str(r.get("institution_eiin") or "").strip()
            inst_name_raw = str(r.get("institution_name") or "").strip()
            key = eiin_raw if (eiin_raw and eiin_raw != "0") else (inst_name_raw or "UNKNOWN")
            groups[key].append(r)

        inst_map = {}
        if existing_insts:
            for k, v in existing_insts.items():
                inst_map[str(k)] = dict(v)

        for key, studs in groups.items():
            appeared = len(studs)
            passed = sum(1 for s in studs if "FAIL" not in str(s.get("grade", "")).upper())
            gpa5 = sum(1 for s in studs if str(s.get("grade", "")) in ["5.00", "5", "5.0"])
            pass_pct = f"{(passed / max(1, appeared) * 100):.2f}%"
            inst_name = studs[0].get("institution_name") or key
            eiin_val = str(studs[0].get("institution_eiin") or "")
            z_val = studs[0].get("zilla") or "CHATTOGRAM"
            u_val = studs[0].get("upazilla") or "UNKNOWN"

            inst_obj = {
                "eiin": eiin_val,
                "name": inst_name,
                "zilla": z_val,
                "thana": u_val,
                "appeared": appeared,
                "passed": passed,
                "gpa5": gpa5,
                "pass_percentage": pass_pct,
                "students_count": appeared
            }
            lookup_key = eiin_val if (eiin_val and eiin_val != "0") else key
            inst_map[lookup_key] = inst_obj

        inst_list = list(inst_map.values())
        inst_list.sort(key=lambda x: str(x.get("name", "")))
        return inst_list

    def maybe_flush(self, force: bool = False):
        """Flushes dirty upazila files and master file every 15s to keep CPU < 5%."""
        now = time.time()
        if not force and (now - self.last_flush_time < 15.0 or not self.dirty_upazilas):
            return

        with self.lock:
            self.last_flush_time = now
            keys_to_flush = list(self.dirty_upazilas)
            self.dirty_upazilas.clear()

            all_studs = list(self.master_students.values())
            all_insts = self._build_institutions_summary(all_studs, self.master_institutions)

            # 1. Save Master File
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

            # 2. Save only dirty Upazila files
            for key in keys_to_flush:
                entry = self.upazila_data.get(key)
                if not entry:
                    continue
                u_file = entry["file_path"]
                u_studs = list(entry["students_map"].values())
                u_insts = self._build_institutions_summary(u_studs, entry.get("institutions_map", {}))
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
# 1. EIIN INSTITUTIONAL SCRAPING ENGINE (NON-BLOCKING STREAM)
# =========================================================================
def run_ctg_eiin_scraper(
    eiins: List[str],
    results_root: Optional[str] = None,
    with_subjects: bool = True
):
    eiins = sorted(list(dict.fromkeys(str(e).strip() for e in eiins if str(e).strip().isdigit() and len(str(e).strip()) == 6)))
    if not eiins:
        print(f"{RED}[!] No valid 6-digit EIINs provided.{RESET}", flush=True)
        return

    mgr = CtgResultsManager(results_root)
    proxies = proxy_pool.ensure_pool(min_size=20)
    num_workers = min(20, max(6, len(proxies))) if proxies else 10
    spare_proxies = max(0, len(proxies) - num_workers)

    mode_label = "Subject-Wise Marks Detailed" if with_subjects else "Standard 8-Field Clean"

    print(f"\n=======================================================")
    print(f"🚀 {BOLD}ENGINE PIPELINE CONFIGURATION:{RESET}")
    print(f"  • Target Board:            {CYAN}{BOLD}Chittagong Education Board (BISE CTG){RESET}")
    print(f"  • Extraction Mode:         {GREEN}{BOLD}{mode_label}{RESET}")
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
    last_ui_draw = [0.0]

    batch_start_time = time.time()
    first_roll_time = [None]
    last_roll_time = [None]
    batch_received_count = 0

    def harvest_eiin_worker(task_info):
        idx, eiin_str = task_info
        cur_proxies = proxy_pool.get_all()
        p = cur_proxies[idx % len(cur_proxies)] if cur_proxies else None

        res = fetch_ctg_institute(eiin=eiin_str, proxy=p, timeout=5.0, with_subjects=with_subjects)
        if not res or not res.get("success"):
            p_alt = cur_proxies[(idx + 13) % len(cur_proxies)] if cur_proxies else None
            res = fetch_ctg_institute(eiin=eiin_str, proxy=p_alt, timeout=5.0, with_subjects=with_subjects)

        return (idx, eiin_str, res)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(harvest_eiin_worker, (i, e)) for i, e in enumerate(pending_eiins)]
        try:
            for fut in concurrent.futures.as_completed(futures):
                idx, eiin_str, res = fut.result()
                if not res or not res.get("success"):
                    with print_lock:
                        sys.stdout.write(f"  EIIN {eiin_str} -> {RED}Not Found / Error{RESET}\n")
                        sys.stdout.flush()
                    continue

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
                    sys.stdout.write(f"  EIIN {eiin_str}: {inst_name[:30]} {GREEN}+{len(students)} rolls{RESET}\n")
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
                        cutoff = now_ts - 5.0
                        while recent_completions and recent_completions[0] < cutoff:
                            recent_completions.popleft()
                        sample_duration = max(0.5, now_ts - recent_completions[0]) if len(recent_completions) > 1 else 1.0
                        speed = len(recent_completions) / sample_duration

                    elapsed = now_ts - (first_roll_time[0] or now_ts)
                    mins, secs = divmod(elapsed, 60)
                    time_str = f"{int(mins)}m {int(secs):02d}s"
                    p_bar = format_progress_bar(cur_rec, max(cur_rec, len(students)), width=24)

                    with print_lock:
                        if now_ts - last_ui_draw[0] > 0.10:
                            last_ui_draw[0] = now_ts
                            sys.stdout.write(f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_rec} rolls processed ⚡ {speed:.1f} rolls/s │ ⏱️ {time_str}")
                            sys.stdout.flush()

                mgr.maybe_flush()
        except KeyboardInterrupt:
            print(f"\n\n{YELLOW}[!] Pipeline stopped by user (Ctrl+C). Preserved all scraped records!{RESET}", flush=True)

    mgr.maybe_flush(force=True)
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
    print(f"  • Extraction Mode:        {GREEN}{BOLD}{mode_label}{RESET}")
    print(f"  • Institutions Processed: {len(pending_eiins)} ({already_scraped_count} already cached)")
    print(f"  • Total Student Records:  {GREEN}{BOLD}{len(mgr.master_students)} Students{RESET}")
    print(f"  • Live Scraped in Batch:  {batch_received_count} rolls")
    print(f"  • Active Scraping Speed:  {GREEN}{BOLD}{pure_speed_str}{RESET}")
    print(f"  • Storage Root Directory: {YELLOW}{mgr.root}{RESET}")
    print(f"=======================================================")

    print(f"\n{GREEN}{BOLD}🎉 Finished Batch! All results saved across Upazilla files in {time_str}!{RESET}")
    print(f"{CYAN}───────────────────────────────────────────────────────────{RESET}\n", flush=True)


# =========================================================================
# 2. ROLL RANGE / FILE SCRAPING ENGINE (NON-BLOCKING STREAM)
# =========================================================================
def run_ctg_scraper(
    rolls: List[str],
    results_root: Optional[str] = None,
    force_recheck: bool = False,
    with_subjects: bool = True
):
    rolls = sorted(list(dict.fromkeys(str(r).strip() for r in rolls if str(r).strip().isdigit())))
    if not rolls:
        print(f"{RED}[!] No valid 6-digit rolls provided.{RESET}", flush=True)
        return

    mgr = CtgResultsManager(results_root)
    cache_file = os.path.join(mgr.root, ".chittagong_memory_cache.json")
    proxies = proxy_pool.ensure_pool(min_size=25)
    num_workers = min(30, max(10, len(proxies))) if proxies else 15
    spare_proxies = max(0, len(proxies) - num_workers)

    mode_label = "Subject-Wise Marks Detailed" if with_subjects else "Standard 8-Field Clean"

    print(f"\n=======================================================")
    print(f"🚀 {BOLD}ENGINE PIPELINE CONFIGURATION:{RESET}")
    print(f"  • Target Board:            {CYAN}{BOLD}Chittagong Education Board (BISE CTG){RESET}")
    print(f"  • Extraction Mode:         {GREEN}{BOLD}{mode_label}{RESET}")
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

    def is_cached(r_str):
        if r_str not in mgr.master_students:
            return False
        if with_subjects and "subjects" not in mgr.master_students[r_str]:
            return False
        return True

    if force_recheck:
        pending_rolls = [r for r in rolls if not is_cached(r)]
    else:
        pending_rolls = [r for r in rolls if not is_cached(r) and r not in dead_slots]

    skipped_success = sum(1 for r in rolls if is_cached(r))
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
    last_ui_draw = [0.0]

    scraped_count = 0
    first_roll_time = [None]
    last_roll_time = [None]
    batch_start_time = time.time()

    # Pre-allocate robust session pool with dual timeouts and fallback
    worker_sessions = []
    for i in range(num_workers):
        p = proxies[i % len(proxies)] if proxies else None
        worker_sessions.append(create_isolated_session(p))

    # Fast direct session for fallback
    direct_session = create_isolated_session(None)

    def process_roll_worker(task_info):
        idx, roll_str = task_info
        worker_id = idx % num_workers
        sess = worker_sessions[worker_id]

        res = None
        # Strict dual timeout (2.5s connect, 4.0s read)
        try:
            r = sess.post(INDIVIDUAL_ENDPOINT, data={"roll": roll_str, "button2": "Submit"}, timeout=(2.5, 4.0))
            if r.status_code == 200:
                res = parse_ctg_student_html(r.text, roll_str, with_subjects=with_subjects)
        except Exception:
            # Immediate failover to alternative session
            alt_worker_id = (worker_id + 7) % num_workers
            sess_alt = worker_sessions[alt_worker_id]
            try:
                r = sess_alt.post(INDIVIDUAL_ENDPOINT, data={"roll": roll_str, "button2": "Submit"}, timeout=(2.5, 4.0))
                if r.status_code == 200:
                    res = parse_ctg_student_html(r.text, roll_str, with_subjects=with_subjects)
            except Exception:
                # Direct fallback
                try:
                    r = direct_session.post(INDIVIDUAL_ENDPOINT, data={"roll": roll_str, "button2": "Submit"}, timeout=(2.5, 4.0))
                    if r.status_code == 200:
                        res = parse_ctg_student_html(r.text, roll_str, with_subjects=with_subjects)
                except Exception:
                    pass

        return (roll_str, res)

    # Chunk processing into non-blocking streams of 1,000 rolls
    CHUNK_SIZE = 1000
    total_to_scrape = len(pending_rolls)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        for chunk_idx in range(0, total_to_scrape, CHUNK_SIZE):
            chunk = pending_rolls[chunk_idx: chunk_idx + CHUNK_SIZE]
            futures = [executor.submit(process_roll_worker, (chunk_idx + j, r)) for j, r in enumerate(chunk)]
            
            try:
                for fut in concurrent.futures.as_completed(futures):
                    roll_str, res = fut.result()
                    now_ts = time.time()
                    with stats_lock:
                        if first_roll_time[0] is None:
                            first_roll_time[0] = now_ts
                        last_roll_time[0] = now_ts
                        scraped_count += 1
                        cur_c = scraped_count
                        cur_t = total_to_scrape

                    with recent_lock:
                        recent_completions.append(now_ts)
                        cutoff = now_ts - 5.0
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
                            if now_ts - last_ui_draw[0] > 0.08:
                                last_ui_draw[0] = now_ts
                                sys.stdout.write(f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_c}/{cur_t} ({pct:.1f}%) ⚡ {speed:.1f} rolls/s │ ⏱️ {time_str}")
                            sys.stdout.flush()
                    elif res and res.get("error") == "Record Not Found":
                        with dead_lock:
                            dead_slots_set.add(roll_str)
                        with print_lock:
                            if now_ts - last_ui_draw[0] > 0.08:
                                last_ui_draw[0] = now_ts
                                sys.stdout.write(f"\r\033[K{CYAN}{p_bar}{RESET}  {cur_c}/{cur_t} ({pct:.1f}%) ⚡ {speed:.1f} rolls/s │ ⏱️ {time_str}")
                                sys.stdout.flush()

                    mgr.maybe_flush()
            except KeyboardInterrupt:
                print(f"\n\n{YELLOW}[!] Pipeline stopped by user (Ctrl+C). Preserved all scraped records!{RESET}", flush=True)
                break

    for s in worker_sessions:
        try:
            s.close()
        except Exception:
            pass
    try:
        direct_session.close()
    except Exception:
        pass

    mgr.maybe_flush(force=True)
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
    print(f"  • Extraction Mode:        {GREEN}{BOLD}{mode_label}{RESET}")
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
    print(f"  {GREEN}[5]{RESET} {BOLD}Load Rolls from File{RESET} (e.g. chittagong_all_rolls.txt)")
    print(f"  {YELLOW}{BOLD}[6]{RESET} {BOLD}Scrape Top 51 Institutes Rolls{RESET} ({CYAN}top_51_institutes_all_rolls.txt{RESET} — 14,586 examinees)")
    print(f"  {GREEN}{BOLD}[7]{RESET} {BOLD}Scrape with Subject-Wise Marks Breakdown{RESET} (Include all subject scores)")
    print(f"  {CYAN}[0]{RESET} Exit\n", flush=True)

    choice = input(f"{BOLD}Enter choice [1-7]: {RESET}").strip()

    if choice == "1":
        print(f"\n{BOLD}Enter EIIN number(s) (e.g. 103086 or space/comma-separated list):{RESET}")
        raw = input(f"{BOLD}EIIN: {RESET}").strip()
        eiins = [e.strip() for e in re.split(r'[,\s\n]+', raw) if e.strip().isdigit() and len(e.strip()) == 6]
        if eiins:
            run_ctg_eiin_scraper(eiins, with_subjects=True)
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
                    run_ctg_eiin_scraper(eiins, with_subjects=True)
            elif u_choice.isdigit() and 1 <= int(u_choice) <= len(upz_files):
                selected_upz_file = upz_files[int(u_choice) - 1]
                upz_name = os.path.splitext(os.path.basename(selected_upz_file))[0]
                with open(selected_upz_file, "r", encoding="utf-8") as uf:
                    eiins = [l.strip() for l in uf if l.strip().isdigit()]
                print(f"\n{GREEN}Selected: {selected_z} -> {upz_name} ({len(eiins)} institutions){RESET}", flush=True)
                run_ctg_eiin_scraper(eiins, with_subjects=True)
    elif choice == "3":
        raw = input(f"\n{BOLD}Enter Roll Range (e.g. 100001-100500, 129000-129050): {RESET}").strip()
        m = re.match(r'(\d+)\s*[-:]\s*(\d+)', raw)
        if m:
            start_r, end_r = int(m.group(1)), int(m.group(2))
            if start_r > end_r:
                start_r, end_r = end_r, start_r
            rolls = [str(r) for r in range(start_r, end_r + 1)]
            run_ctg_scraper(rolls, with_subjects=True)
        else:
            print(f"{RED}[!] Invalid range format. Example: 129000-129050{RESET}", flush=True)
    elif choice == "4":
        raw = input(f"\n{BOLD}Enter Roll number(s): {RESET}").strip()
        rolls = [r.strip() for r in re.split(r'[,\s\n]+', raw) if r.strip().isdigit()]
        if rolls:
            run_ctg_scraper(rolls, with_subjects=True)
    elif choice == "5":
        path = input(f"\n{BOLD}Enter filepath (txt/json, default chittagong_all_rolls.txt): {RESET}").strip().strip('"')
        if not path:
            path = "chittagong_all_rolls.txt"
        if not os.path.exists(path):
            local_cand = os.path.join(BASE_DIR, path)
            if os.path.exists(local_cand):
                path = local_cand

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            items = [r.strip() for r in re.split(r'[,\s\n"\[\]]+', content) if r.strip().isdigit()]
            print(f"{GREEN}✓ Loaded {len(items):,} items from {path}{RESET}\n")
            if items:
                run_ctg_scraper(items, with_subjects=True)
        else:
            print(f"{RED}[!] File not found: {path}{RESET}", flush=True)
    elif choice == "6":
        path = os.path.join(BASE_DIR, "top_51_institutes_all_rolls.txt")
        if not os.path.exists(path):
            path = r"C:\Users\labib_n4\Documents\Project\Result-Scraper-Antygravity-Project\top_51_institutes_all_rolls.txt"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                items = [r.strip() for r in re.split(r'[,\s\n"\[\]]+', f.read()) if r.strip().isdigit()]
            print(f"{GREEN}✓ Loaded {len(items):,} candidate rolls from Top 51 Institutes!{RESET}\n")
            
            default_out = os.path.join(BASE_DIR, "results", "chittagong_top_51_with_marks")
            out_prompt = input(f"{BOLD}Save folder [default: {default_out}]: {RESET}").strip()
            dest_dir = out_prompt if out_prompt else default_out
            
            run_ctg_scraper(items, results_root=dest_dir, with_subjects=True, force_recheck=True)
        else:
            print(f"{RED}[!] File top_51_institutes_all_rolls.txt not found.{RESET}", flush=True)
    elif choice == "7":
        print(f"\n{BOLD}Select Source for Subject-Wise Marks Scrape:{RESET}")
        print(f"  [1] Top 51 Institutes ({CYAN}top_51_institutes_all_rolls.txt{RESET})")
        print(f"  [2] Master Roll File ({CYAN}chittagong_all_rolls.txt{RESET})")
        print(f"  [3] Custom Roll Range (e.g. 112250-112300)")
        print(f"  [4] Custom File Path")
        sub_choice = input(f"{BOLD}Enter choice [1-4]: {RESET}").strip()
        
        rolls_to_scrape = []
        default_dir_name = "chittagong_with_marks"
        if sub_choice == "1":
            p = os.path.join(BASE_DIR, "top_51_institutes_all_rolls.txt")
            if not os.path.exists(p):
                p = r"C:\Users\labib_n4\Documents\Project\Result-Scraper-Antygravity-Project\top_51_institutes_all_rolls.txt"
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    rolls_to_scrape = [r.strip() for r in re.split(r'[,\s\n"\[\]]+', f.read()) if r.strip().isdigit()]
            default_dir_name = "chittagong_top_51_with_marks"
        elif sub_choice == "2":
            p = os.path.join(BASE_DIR, "chittagong_all_rolls.txt")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    rolls_to_scrape = [r.strip() for r in re.split(r'[,\s\n"\[\]]+', f.read()) if r.strip().isdigit()]
        elif sub_choice == "3":
            raw = input(f"{BOLD}Enter Roll Range: {RESET}").strip()
            m = re.match(r'(\d+)\s*[-:]\s*(\d+)', raw)
            if m:
                s, e = int(m.group(1)), int(m.group(2))
                rolls_to_scrape = [str(x) for x in range(min(s, e), max(s, e) + 1)]
        elif sub_choice == "4":
            p = input(f"{BOLD}Enter file path: {RESET}").strip().strip('"')
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    rolls_to_scrape = [r.strip() for r in re.split(r'[,\s\n"\[\]]+', f.read()) if r.strip().isdigit()]

        if rolls_to_scrape:
            default_out = os.path.join(BASE_DIR, "results", default_dir_name)
            out_prompt = input(f"{BOLD}Save folder [default: {default_out}]: {RESET}").strip()
            dest_dir = out_prompt if out_prompt else default_out
            run_ctg_scraper(rolls_to_scrape, results_root=dest_dir, with_subjects=True, force_recheck=True)


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    with_sub_flag = "--no-marks" not in sys.argv
    
    custom_out_dir = None
    clean_argv = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ("--out-dir", "--output") and i + 1 < len(sys.argv):
            custom_out_dir = sys.argv[i + 1]
            i += 2
        elif arg not in ("--force", "--with-marks", "--subjects", "--no-marks"):
            clean_argv.append(arg)
            i += 1
        else:
            i += 1

    if "--eiin" in clean_argv:
        e_idx = clean_argv.index("--eiin")
        eiin_args = clean_argv[e_idx + 1:]
        if eiin_args:
            run_ctg_eiin_scraper(eiin_args, results_root=custom_out_dir, with_subjects=with_sub_flag)
        else:
            interactive_ctg_menu()
    elif clean_argv:
        arg_rolls = []
        for a in clean_argv:
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
            if not custom_out_dir and any("top_51" in a.lower() for a in clean_argv):
                custom_out_dir = os.path.join(BASE_DIR, "results", "chittagong_top_51_with_marks" if with_sub_flag else "chittagong_top_51")
            
            run_ctg_scraper(arg_rolls, results_root=custom_out_dir, force_recheck=force_flag, with_subjects=with_sub_flag)
        else:
            interactive_ctg_menu()
    else:
        interactive_ctg_menu()
