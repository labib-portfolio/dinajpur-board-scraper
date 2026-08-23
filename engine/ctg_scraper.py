"""
Chittagong Education Board (BISE CTG) High-Throughput Result Scraper Engine
Endpoints:
  • Institutional Gazette (with subject marks): https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/resultm.php
  • Individual Marksheet (by roll): https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/result.php
"""

import html
import json
import re
import time
import requests
import urllib3
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List, Callable

urllib3.disable_warnings()

CTG_BASE_URL = "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg"
CTG_INSTITUTE_URL = f"{CTG_BASE_URL}/resultm.php"
CTG_INDIVIDUAL_URL = f"{CTG_BASE_URL}/individual/result.php"
CTG_REFERER = f"{CTG_BASE_URL}/"

# Common SSC Subject Code Map
SUBJECT_CODE_MAP = {
    "101": "BANGLA",
    "107": "ENGLISH",
    "109": "MATHEMATICS",
    "110": "GEOGRAPHY & ENVIRONMENT",
    "111": "ISLAM & MORAL EDUCATION",
    "112": "HINDU RELIGION & MORAL EDUCATION",
    "113": "BUDDHIST RELIGION & MORAL EDUCATION",
    "114": "CHRISTIAN RELIGION & MORAL EDUCATION",
    "126": "HIGHER MATHEMATICS",
    "127": "GENERAL SCIENCE",
    "134": "AGRICULTURE STUDIES",
    "136": "PHYSICS",
    "137": "CHEMISTRY",
    "138": "BIOLOGY",
    "140": "CIVICS & CITIZENSHIP",
    "143": "FINANCE & BANKING",
    "146": "BUSINESS ENTREPRENEURSHIP",
    "150": "BANGLADESH & GLOBAL STUDIES",
    "152": "ACCOUNTING",
    "153": "HISTORY OF BANGLADESH & WORLD CIVILIZATION",
    "154": "INFORMATION & COMMUNICATION TECHNOLOGY (ICT)"
}


def parse_ctg_institute_gazette(html_text: str, eiin: str) -> Dict[str, Any]:
    """
    Parses the full institutional mark sheet response from resultm.php.
    Calculates total marks automatically by summing up individual subject marks.
    """
    if not html_text or "RESULTS OF SSC EXAMINATION" not in html_text or "INSTITUTE NAME" not in html_text:
        if "not found" in html_text.lower() or "invalid" in html_text.lower():
            return {
                "success": False,
                "eiin": str(eiin),
                "board": "CHATTOGRAM",
                "error": "EIIN Not Found"
            }
        return {"success": False, "eiin": str(eiin), "error": "Invalid HTML Response"}

    soup = BeautifulSoup(html_text, "html.parser")
    
    # 1. Header Information
    info = {}
    tbl = soup.find("table")
    if tbl:
        for tr in tbl.find_all("tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) >= 2:
                k = tds[0].rstrip(":").strip()
                v = tds[1].strip()
                info[k] = v

    inst_name = info.get("INSTITUTE NAME", "")
    zilla = info.get("ZILLA", "")
    thana = info.get("THANA", "")
    appeared = int(info.get("APP", 0)) if info.get("APP", "").isdigit() else 0
    passed = int(info.get("PASS", 0)) if info.get("PASS", "").isdigit() else 0
    gpa5 = int(info.get("GPA5", 0)) if info.get("GPA5", "").isdigit() else 0
    percent = info.get("PERCENT", "")

    inst_clean = re.sub(r'\(\d+\)', '', inst_name).strip() if inst_name else f"EIIN {eiin}"
    zilla_clean = re.sub(r'\(\d+\)', '', zilla).strip() if zilla else ""
    thana_clean = re.sub(r'\(\d+\)', '', thana).strip() if thana else ""

    # 2. Parse Students Section
    students = []
    full_text = html_text
    group_blocks = re.split(r'(SCIENCE\s*:|BUSINESS\s*STUDIES\s*:|HUMANITIES\s*:)', full_text, flags=re.IGNORECASE)
    
    current_group = "GENERAL"
    for idx, block in enumerate(group_blocks):
        block_clean = block.strip()
        if re.match(r'^(SCIENCE\s*:|BUSINESS\s*STUDIES\s*:|HUMANITIES\s*:)$', block_clean, re.IGNORECASE):
            current_group = block_clean.rstrip(':').strip().upper()
            continue
        
        if "EXAMINEES WHO HAVE BEEN UNSUCCESSFUL" in block:
            content_part = block.split("EXAMINEES WHO HAVE BEEN UNSUCCESSFUL")[0]
        else:
            content_part = block
            
        # Match pattern: 129051[4.50]:101:T:152(A ),107:T:145(A )...
        matches = re.finditer(r'(\d{6,7})\[([\d\.]+)\]:([^\n<]+)', content_part)
        for m in matches:
            roll = m.group(1).strip()
            gpa = m.group(2).strip()
            raw_subs = m.group(3).strip()
            
            sub_list = []
            total_marks = 0
            has_marks = False
            
            sub_items = re.findall(r'(\d{3}):[A-Z]:(?:(\d{3}))?\(([A-Z\+\-\s]+)\)', raw_subs)
            for sub_code, marks_str, grade in sub_items:
                marks_int = int(marks_str) if marks_str and marks_str.isdigit() else None
                if marks_int is not None:
                    total_marks += marks_int
                    has_marks = True
                    
                sub_list.append({
                    "code": sub_code,
                    "subject_name": SUBJECT_CODE_MAP.get(sub_code, f"SUBJECT {sub_code}"),
                    "marks": marks_int if marks_int is not None else "",
                    "grade": grade.strip()
                })
                
            students.append({
                "roll_no": roll,
                "gpa": gpa,
                "total_marks": total_marks if has_marks else None,
                "result": f"GPA={gpa}",
                "group": current_group,
                "status": "PASSED",
                "eiin": str(eiin),
                "institute": inst_clean,
                "zilla": zilla_clean,
                "upazila": thana_clean,
                "subjects": sub_list
            })

    # 3. Parse Failed Students
    failed_match = re.search(r'EXAMINEES WHO HAVE BEEN UNSUCCESSFUL/OTHERS\s*:\s*<br\s*/?>\s*(.+?)(?:</div>|\*{5,}|$)', full_text, re.DOTALL | re.IGNORECASE)
    if failed_match:
        failed_raw = failed_match.group(1)
        f_items = re.findall(r'(\d{6,7})\[([A-Z\d]+)\]', failed_raw)
        for f_roll, f_reason in f_items:
            students.append({
                "roll_no": f_roll,
                "gpa": "FAIL",
                "total_marks": None,
                "result": f"FAILED ({f_reason})",
                "fail_detail": f_reason,
                "status": "FAILED",
                "group": "GENERAL",
                "eiin": str(eiin),
                "institute": inst_clean,
                "zilla": zilla_clean,
                "upazila": thana_clean,
                "subjects": []
            })

    return {
        "success": True,
        "eiin": str(eiin),
        "institute_name": inst_clean,
        "zilla": zilla_clean,
        "thana": thana_clean,
        "total_appeared": appeared or len(students),
        "total_passed": passed or sum(1 for s in students if s["status"] == "PASSED"),
        "total_failed": (appeared - passed) if (appeared and passed) else sum(1 for s in students if s["status"] == "FAILED"),
        "total_gpa5": gpa5,
        "pass_percentage": percent,
        "total_parsed_students": len(students),
        "students": students,
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


def fetch_ctg_institute(
    session: Optional[requests.Session] = None,
    eiin: str = "",
    proxy: Optional[str] = None,
    timeout: float = 10.0,
    max_retries: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Fetches and parses all student results and marksheets for a given EIIN in one request.
    """
    s = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Origin": "https://sresult.bise-ctg.gov.bd",
        "Referer": "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    proxies_dict = None
    if proxy:
        parts = proxy.split(":")
        if len(parts) == 4:
            ip, port, user, pwd = parts
            proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
        else:
            proxy_url = f"http://{proxy}"
        proxies_dict = {"http": proxy_url, "https": proxy_url}

    payload = {
        "eiin": str(eiin).strip()
    }

    for attempt in range(1, max_retries + 1):
        try:
            r = s.post(
                CTG_INSTITUTE_URL,
                data=payload,
                headers=headers,
                proxies=proxies_dict,
                timeout=timeout,
                verify=False
            )
            if r.status_code == 200:
                parsed = parse_ctg_institute_gazette(r.text, eiin)
                if parsed and parsed.get("success"):
                    return parsed
                elif parsed and parsed.get("error") == "EIIN Not Found":
                    return parsed
        except Exception:
            if attempt < max_retries:
                time.sleep(0.3 * attempt)
    return None


def parse_ctg_student_html(html_text: str, roll: str) -> Optional[Dict[str, Any]]:
    """
    Parses the HTML response from Chittagong Board individual result portal.
    """
    if not html_text or "SSC Result" not in html_text or "Roll No" not in html_text:
        if "not found" in html_text.lower() or "invalid" in html_text.lower():
            return {
                "success": False,
                "roll_no": str(roll),
                "board": "CHATTOGRAM",
                "error": "Record Not Found"
            }
        return None

    soup = BeautifulSoup(html_text, "html.parser")
    profile_data = {}
    prof_tbl = soup.find("table", class_="tftable") or soup.find("table")
    if prof_tbl:
        for tr in prof_tbl.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) >= 2:
                for i in range(0, len(cells) - 1, 2):
                    key = cells[i].rstrip(":").strip()
                    val = cells[i+1].strip()
                    if key and val:
                        profile_data[key] = val

    name = profile_data.get("Name") or profile_data.get("name")
    if not name:
        name_m = re.search(r'Name</td>\s*<td[^>]*>([^<]+)</td>', html_text, re.IGNORECASE)
        name = html.unescape(name_m.group(1).strip()) if name_m else None

    if not name:
        return None

    father = profile_data.get("Father's Name", "")
    mother = profile_data.get("Mother's Name", "")
    reg_no = profile_data.get("Reg. NO", "") or profile_data.get("Reg. No", "")
    group = profile_data.get("Group", "GENERAL")
    session = profile_data.get("Session", "")
    cand_type = profile_data.get("Type", "REGULAR")
    institute = profile_data.get("Institute", "")
    result_str = profile_data.get("Result", "")
    dob = profile_data.get("DATE OF BIRTH", "") or profile_data.get("Date of Birth", "")

    gpa_val = result_str
    if "GPA=" in result_str:
        gpa_val = result_str.replace("GPA=", "").strip()

    subjects = []
    ca_subjects = []
    is_ca_section = False
    total_marks = 0
    has_marks = False

    grade_tbl = soup.find("table", class_="tftable2")
    if grade_tbl:
        for tr in grade_tbl.find_all("tr"):
            if "Result of CA" in tr.get_text():
                is_ca_section = True
                continue
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) == 3:
                code, sub_name, grade_mark = cells[0], cells[1], cells[2]
                if code.lower() in ["code", "subject", "grade"]:
                    continue
                
                m_num = re.search(r'\((\d+)\)|\b(\d+)\b', grade_mark)
                if m_num and not is_ca_section:
                    val = int(m_num.group(1) or m_num.group(2))
                    total_marks += val
                    has_marks = True

                sub_entry = {
                    "code": code,
                    "subject": sub_name,
                    "grade_and_marks": grade_mark
                }
                if is_ca_section:
                    ca_subjects.append(sub_entry)
                else:
                    subjects.append(sub_entry)

    return {
        "success": True,
        "status_code": 200,
        "roll_no": str(roll),
        "student_name": name,
        "father_name": father,
        "mother_name": mother,
        "registration_no": reg_no,
        "board": "CHATTOGRAM",
        "group": group,
        "session": session,
        "type": cand_type,
        "institute": institute,
        "result": result_str,
        "gpa": gpa_val,
        "total_marks": total_marks if has_marks else None,
        "dob": dob,
        "subjects": subjects,
        "ca_subjects": ca_subjects,
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }


def fetch_ctg_student(
    session: Optional[requests.Session] = None,
    roll: str = "",
    proxy: Optional[str] = None,
    timeout: float = 8.0,
    max_retries: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Fetches and parses a single student result from Chittagong Board by Roll Number.
    """
    s = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Origin": "https://sresult.bise-ctg.gov.bd",
        "Referer": f"{CTG_BASE_URL}/individual/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    proxies_dict = None
    if proxy:
        parts = proxy.split(":")
        if len(parts) == 4:
            ip, port, user, pwd = parts
            proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
        else:
            proxy_url = f"http://{proxy}"
        proxies_dict = {"http": proxy_url, "https": proxy_url}

    payload = {
        "roll": str(roll).strip(),
        "button2": "Submit"
    }

    for attempt in range(1, max_retries + 1):
        try:
            r = s.post(
                CTG_INDIVIDUAL_URL,
                data=payload,
                headers=headers,
                proxies=proxies_dict,
                timeout=timeout,
                verify=False
            )
            if r.status_code == 200:
                parsed = parse_ctg_student_html(r.text, roll)
                if parsed:
                    return parsed
        except Exception:
            if attempt < max_retries:
                time.sleep(0.3 * attempt)
    return None
