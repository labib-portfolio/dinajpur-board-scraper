"""
Chittagong Education Board (BISE CTG) Result Scraping Engine
Standardized Clean 8-Field Output:
  • name
  • roll
  • total_mark
  • grade
  • institution_name
  • institution_eiin
  • zilla
  • upazilla
Endpoints:
  • Individual: https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/result.php
  • Institutional: https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/resultm.php
"""

import re
import html
import requests
from typing import Dict, Any, Optional, List
from requests.adapters import HTTPAdapter

INDIVIDUAL_ENDPOINT = "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/result.php"
INSTITUTION_ENDPOINT = "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/resultm.php"


def create_ctg_session(proxy: Optional[str] = None) -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=5, pool_maxsize=5, max_retries=0)
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


def parse_ctg_student_html(html_text: str, roll_no: str) -> Optional[Dict[str, Any]]:
    if not html_text or "No Result Found" in html_text or "Invalid Roll" in html_text or "Record Not Found" in html_text:
        return {"success": False, "error": "Record Not Found", "roll": roll_no}

    def get_cell(label: str) -> str:
        m = re.search(rf'>{label}</td>\s*<td[^>]*>([^<]+)</td>', html_text, re.IGNORECASE)
        if m:
            return html.unescape(m.group(1)).strip()
        return ""

    student_name = get_cell("Name")
    if not student_name:
        m = re.search(r'Name of Student.*?<td[^>]*>([^<]+)</td>', html_text, re.IGNORECASE | re.DOTALL)
        if m:
            student_name = html.unescape(m.group(1)).strip()

    result_raw = get_cell("Result")
    institute = get_cell("Institute")
    
    if not student_name and not result_raw and "GPA" not in html_text:
        return {"success": False, "error": "Record Not Found", "roll": roll_no}

    gpa_val = "FAIL"
    m_gpa = re.search(r'GPA\s*=?\s*([\d.]+)', result_raw, re.IGNORECASE)
    if m_gpa:
        gpa_val = m_gpa.group(1).strip()
    elif "PASS" in result_raw.upper():
        gpa_val = "PASSED"

    # Extract subject marks and calculate total marks
    subject_rows = re.findall(
        r'<td class="bg_grey">(\d+)</td>\s*<td class="bg_grey cap_lt">[^<]+</td>\s*<td class="bg_grey cap_lt">(\d{2,3})\(([A-Za-z0-9+\s-]+)\)</td>',
        html_text
    )

    total_marks = 0
    if subject_rows:
        for code, mark_str, _ in subject_rows:
            if code not in ['147', '152', '156']:  # Omit continuous assessment subjects
                total_marks += int(mark_str)
    else:
        raw_marks = re.findall(r'<td[^>]*>(\d{2,3})\([A-Za-z0-9+\s-]+\)</td>', html_text)
        if raw_marks:
            for m_str in raw_marks:
                total_marks += int(m_str)
        else:
            total_marks = None

    return {
        "success": True,
        "name": student_name,
        "roll": str(roll_no),
        "total_mark": total_marks if (total_marks is not None and total_marks > 0) else None,
        "grade": gpa_val,
        "institution_name": institute,
        "institution_eiin": "",
        "zilla": "",
        "upazilla": ""
    }


def parse_ctg_institute_gazette(html_text: str, eiin: str) -> Optional[Dict[str, Any]]:
    if not html_text or "No Result Found" in html_text or "Invalid EIIN" in html_text:
        return {"success": False, "error": "EIIN Not Found", "eiin": eiin}

    def get_meta(label: str) -> str:
        m = re.search(rf'{label}\s*:\s*</td>\s*<td[^>]*>([^<(\n]+)', html_text, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    institute_name = get_meta('INSTITUTE NAME') or f"EIIN_{eiin}"
    zilla_name = get_meta('ZILLA').upper() or "CHATTOGRAM"
    thana_name = get_meta('THANA').upper() or "UNKNOWN"

    stat_m = re.search(r'APP\s*:\s*</td>\s*<td[^>]*>\s*(\d+)', html_text, re.IGNORECASE)
    total_appeared = int(stat_m.group(1)) if stat_m else 0
    pass_m = re.search(r'PASS\s*:\s*</td>\s*<td[^>]*>\s*(\d+)', html_text, re.IGNORECASE)
    total_passed = int(pass_m.group(1)) if pass_m else 0
    gpa5_m = re.search(r'GPA5\s*:\s*</td>\s*<td[^>]*>\s*(\d+)', html_text, re.IGNORECASE)
    total_gpa5 = int(gpa5_m.group(1)) if gpa5_m else 0

    students: List[Dict[str, Any]] = []

    # Parse PASSED examinees with marks
    passed_pattern = re.compile(r'(\d{6})\[([\d.]+)\]:([0-9A-Z:(),+\-\s]+?)(?=(?:\s+\d{6}\[|\s*<|\s*$))')
    for p_match in passed_pattern.finditer(html_text):
        r_no = p_match.group(1).strip()
        gpa_val = p_match.group(2).strip()
        raw_marks_block = p_match.group(3).strip()

        calc_total = 0
        subject_entries = raw_marks_block.split(',')
        for entry in subject_entries:
            score_m = re.search(r':(\d{2,3})\(', entry)
            if score_m:
                calc_total += int(score_m.group(1))

        students.append({
            "name": "",
            "roll": r_no,
            "total_mark": calc_total if calc_total > 0 else None,
            "grade": gpa_val,
            "institution_name": institute_name,
            "institution_eiin": str(eiin),
            "zilla": zilla_name,
            "upazilla": thana_name
        })

    # Parse FAILED examinees
    failed_pattern = re.compile(r'(\d{6})\[([A-Z0-9]+)\](?!\:)')
    for f_match in failed_pattern.finditer(html_text):
        r_no = f_match.group(1).strip()
        fail_code = f_match.group(2).strip()
        if not any(s["roll"] == r_no for s in students):
            students.append({
                "name": "",
                "roll": r_no,
                "total_mark": None,
                "grade": f"FAIL ({fail_code})",
                "institution_name": institute_name,
                "institution_eiin": str(eiin),
                "zilla": zilla_name,
                "upazilla": thana_name
            })

    if not students and total_appeared == 0:
        return {"success": False, "error": "EIIN Not Found", "eiin": eiin}

    return {
        "success": True,
        "eiin": str(eiin),
        "institute_name": institute_name,
        "zilla": zilla_name,
        "thana": thana_name,
        "total_appeared": total_appeared,
        "total_passed": total_passed,
        "total_gpa5": total_gpa5,
        "students": students
    }


def fetch_ctg_student(roll: str, proxy: Optional[str] = None, timeout: float = 7.0) -> Optional[Dict[str, Any]]:
    session = create_ctg_session(proxy=proxy)
    try:
        payload = {"roll": str(roll).strip(), "button2": "Submit"}
        r = session.post(INDIVIDUAL_ENDPOINT, data=payload, timeout=timeout)
        if r.status_code == 200:
            return parse_ctg_student_html(r.text, str(roll).strip())
        return {"success": False, "status_code": r.status_code, "error": f"HTTP {r.status_code}", "roll": roll}
    except Exception as e:
        return {"success": False, "error": type(e).__name__, "roll": roll}
    finally:
        session.close()


def fetch_ctg_institute(eiin: str, proxy: Optional[str] = None, timeout: float = 8.0) -> Optional[Dict[str, Any]]:
    session = create_ctg_session(proxy=proxy)
    session.headers.update({
        "Referer": "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/resultm.php",
        "Content-Type": "application/x-www-form-urlencoded"
    })
    try:
        payload = {"eiin": str(eiin).strip()}
        r = session.post(INSTITUTION_ENDPOINT, data=payload, timeout=timeout)
        if r.status_code == 200:
            return parse_ctg_institute_gazette(r.text, str(eiin).strip())
        return {"success": False, "status_code": r.status_code, "error": f"HTTP {r.status_code}", "eiin": eiin}
    except Exception as e:
        return {"success": False, "error": type(e).__name__, "eiin": eiin}
    finally:
        session.close()
