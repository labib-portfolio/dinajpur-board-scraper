"""
Chittagong Education Board (BISE CTG) Result Scraping Engine
Ultra-Fast Pre-Compiled Regex Parsing Architecture
"""

import re
import html
import requests
from typing import Dict, Any, Optional, List
from requests.adapters import HTTPAdapter

INDIVIDUAL_ENDPOINT = "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/result.php"
INSTITUTION_ENDPOINT = "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/resultm.php"

# Pre-compiled Regexes for Sub-Millisecond Execution
RE_NAME = re.compile(r'>Name</td>\s*<td[^>]*>([^<]+)</td>', re.IGNORECASE)
RE_NAME_FALLBACK = re.compile(r'Name of Student.*?<td[^>]*>([^<]+)</td>', re.IGNORECASE | re.DOTALL)
RE_RESULT = re.compile(r'>Result</td>\s*<td[^>]*>([^<]+)</td>', re.IGNORECASE)
RE_INSTITUTE = re.compile(r'>Institute</td>\s*<td[^>]*>([^<]+)</td>', re.IGNORECASE)
RE_GPA = re.compile(r'GPA\s*=?\s*([\d.]+)', re.IGNORECASE)
RE_SUBJECT_ROWS = re.compile(
    r'<td class="bg_grey">(\d+)</td>\s*<td class="bg_grey cap_lt">[^<]+</td>\s*<td class="bg_grey cap_lt">(\d{2,3})\(([A-Za-z0-9+\s-]+)\)</td>'
)
RE_RAW_MARKS = re.compile(r'<td[^>]*>(\d{2,3})\([A-Za-z0-9+\s-]+\)</td>')

# Institutional Gazette Regexes
RE_INST_NAME = re.compile(r'INSTITUTE NAME\s*:\s*</td>\s*<td[^>]*>([^<(\n]+)', re.IGNORECASE)
RE_ZILLA = re.compile(r'ZILLA\s*:\s*</td>\s*<td[^>]*>([^<(\n]+)', re.IGNORECASE)
RE_THANA = re.compile(r'THANA\s*:\s*</td>\s*<td[^>]*>([^<(\n]+)', re.IGNORECASE)
RE_APP = re.compile(r'APP\s*:\s*</td>\s*<td[^>]*>\s*(\d+)', re.IGNORECASE)
RE_PASS = re.compile(r'PASS\s*:\s*</td>\s*<td[^>]*>\s*(\d+)', re.IGNORECASE)
RE_GPA5 = re.compile(r'GPA5\s*:\s*</td>\s*<td[^>]*>\s*(\d+)', re.IGNORECASE)
RE_PASSED_STUDENTS = re.compile(r'(\d{6})\[([\d.]+)\]:([0-9A-Z:(),+\-\s]+?)(?=(?:\s+\d{6}\[|\s*<|\s*$))')
RE_FAILED_STUDENTS = re.compile(r'(\d{6})\[([A-Z0-9]+)\](?!\:)')
RE_SCORE = re.compile(r':(\d{2,3})\(')


def create_ctg_session(proxy: Optional[str] = None) -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
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

    m_name = RE_NAME.search(html_text)
    student_name = html.unescape(m_name.group(1)).strip() if m_name else ""
    if not student_name:
        m_fb = RE_NAME_FALLBACK.search(html_text)
        if m_fb:
            student_name = html.unescape(m_fb.group(1)).strip()

    m_res = RE_RESULT.search(html_text)
    result_raw = html.unescape(m_res.group(1)).strip() if m_res else ""

    m_inst = RE_INSTITUTE.search(html_text)
    institute = html.unescape(m_inst.group(1)).strip() if m_inst else ""

    if not student_name and not result_raw and "GPA" not in html_text:
        return {"success": False, "error": "Record Not Found", "roll": roll_no}

    gpa_val = "FAIL"
    m_gpa = RE_GPA.search(result_raw)
    if m_gpa:
        gpa_val = m_gpa.group(1).strip()
    elif "PASS" in result_raw.upper():
        gpa_val = "PASSED"

    subject_rows = RE_SUBJECT_ROWS.findall(html_text)
    total_marks = 0
    if subject_rows:
        for code, mark_str, _ in subject_rows:
            if code not in ('147', '152', '156'):
                total_marks += int(mark_str)
    else:
        raw_marks = RE_RAW_MARKS.findall(html_text)
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

    m_inst = RE_INST_NAME.search(html_text)
    institute_name = m_inst.group(1).strip() if m_inst else f"EIIN_{eiin}"

    m_z = RE_ZILLA.search(html_text)
    zilla_name = m_z.group(1).strip().upper() if m_z else "CHATTOGRAM"

    m_t = RE_THANA.search(html_text)
    thana_name = m_t.group(1).strip().upper() if m_t else "UNKNOWN"

    stat_m = RE_APP.search(html_text)
    total_appeared = int(stat_m.group(1)) if stat_m else 0
    pass_m = RE_PASS.search(html_text)
    total_passed = int(pass_m.group(1)) if pass_m else 0
    gpa5_m = RE_GPA5.search(html_text)
    total_gpa5 = int(gpa5_m.group(1)) if gpa5_m else 0

    students: List[Dict[str, Any]] = []

    for p_match in RE_PASSED_STUDENTS.finditer(html_text):
        r_no = p_match.group(1).strip()
        gpa_val = p_match.group(2).strip()
        raw_marks_block = p_match.group(3).strip()

        calc_total = 0
        for entry in raw_marks_block.split(','):
            score_m = RE_SCORE.search(entry)
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

    for f_match in RE_FAILED_STUDENTS.finditer(html_text):
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
