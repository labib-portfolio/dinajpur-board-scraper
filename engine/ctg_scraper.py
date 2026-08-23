"""
Chittagong Education Board (BISE CTG) High-Throughput Result Scraper Engine
Endpoint: https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/result.php
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

CTG_RESULT_URL = "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/result.php"
CTG_REFERER = "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/"


def parse_ctg_student_html(html_text: str, roll: str) -> Optional[Dict[str, Any]]:
    """
    Parses the HTML response from Chittagong Board SSC result portal into a structured dictionary.
    Extracts student metadata, GPA, institute, registration number, and subject-wise grades/marks.
    """
    if not html_text or "SSC Result" not in html_text or "Roll No" not in html_text:
        # Check for invalid roll or not found
        if "not found" in html_text.lower() or "invalid" in html_text.lower():
            return {
                "success": False,
                "roll_no": str(roll),
                "board": "CHATTOGRAM",
                "error": "Record Not Found"
            }
        return None

    soup = BeautifulSoup(html_text, "html.parser")
    
    # 1. Profile Table (table.tftable)
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
        # Regex fallback
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

    # Clean GPA
    gpa_val = result_str
    if "GPA=" in result_str:
        gpa_val = result_str.replace("GPA=", "").strip()

    # 2. Subject-wise Marksheet Table (table.tftable2)
    subjects = []
    ca_subjects = []
    is_ca_section = False

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
    Fetches and parses a single student result from Chittagong Board.
    """
    s = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Origin": "https://sresult.bise-ctg.gov.bd",
        "Referer": CTG_REFERER,
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
                CTG_RESULT_URL,
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