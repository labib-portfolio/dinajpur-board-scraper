import html
import json
import re
import time
import requests
from typing import Optional, Dict, Any, List

ENDPOINT = (
    "https://results.dinajpurboard.gov.bd/fast/student"
    "?roll={roll}&exam=1"
    "&exp=1787224774"
    "&t=769debce061f8471859fb4cd1069e0454aae3b18294e70c8454edd2fc416320a"
)

def parse_student_html(html_text: str, roll: str) -> Optional[Dict[str, Any]]:
    """Ultra-fast regex-based extraction of Dinajpur Board student marksheets."""
    if not html_text or "Student Result" not in html_text:
        return None

    # Student Name
    name_m = re.search(r'Name of Student:?</b></td>\s*<td[^>]*><b>([^<]+)</b></td>', html_text, re.IGNORECASE)
    if not name_m:
        name_m = re.search(r'Name of Student:?</td>\s*<td[^>]*>([^<]+)</td>', html_text, re.IGNORECASE)
    name = html.unescape(name_m.group(1).strip()) if name_m else None
    if not name:
        return None

    # Parents
    father_m = re.search(r"Father'?s?\s*Name</b></td>\s*<td[^>]*><b>([^<]+)</b></td>", html_text, re.IGNORECASE)
    mother_m = re.search(r"Mother'?s?\s*Name</b></td>\s*<td[^>]*><b>([^<]+)</b></td>", html_text, re.IGNORECASE)
    father = html.unescape(father_m.group(1).strip()) if father_m else ""
    mother = html.unescape(mother_m.group(1).strip()) if mother_m else ""

    # Institute & Group
    inst_m = re.search(r'Name of Institute</b></td>\s*<td[^>]*>\s*([^<]+)\s*</td>', html_text, re.IGNORECASE)
    inst = html.unescape(inst_m.group(1).strip()) if inst_m else ""
    
    group_m = re.search(r'Group</b></td>\s*<td[^>]*>\s*([^<]+)\s*</td>', html_text, re.IGNORECASE)
    group = group_m.group(1).strip() if group_m else "GENERAL"

    # Result & GPA & Total Marks
    result_val = "N/A"
    res_m = re.search(r'Result</b></td>\s*<td[^>]*><b>([^<]+)</b></td>', html_text, re.IGNORECASE)
    if res_m:
        result_val = res_m.group(1).strip()

    marks_val = "N/A"
    mark_m = re.search(r'TOTAL MARK</b></td>\s*<td[^>]*><b>([^<]+)</b></td>', html_text, re.IGNORECASE)
    if mark_m:
        marks_val = mark_m.group(1).strip()

    # Subject Grades
    subject_grades = []
    for m in re.finditer(
        r'<td class="l">([^<]+)</td>\s*<td class="c"><span class="grade-mark">'
        r'<span class="grade-letter">([^<]+)</span>\s*<span class="grade-mod">([^<]*)</span>',
        html_text, re.IGNORECASE
    ):
        subj_name = html.unescape(m.group(1).strip())
        grade_str = m.group(2).strip() + m.group(3).strip()
        subject_grades.append({
            "subject_name": subj_name,
            "grade": grade_str
        })

    # Fallback subject grades if different table layout
    if not subject_grades:
        for tr_m in re.finditer(r'<tr>\s*<td>(\d{3})</td>\s*<td>([^<]+)</td>\s*<td>([^<]+)</td>', html_text, re.IGNORECASE):
            subject_grades.append({
                "sub_code": tr_m.group(1).strip(),
                "subject_name": html.unescape(tr_m.group(2).strip()),
                "grade": tr_m.group(3).strip()
            })

    return {
        "success": True,
        "status_code": 200,
        "roll_no": str(roll),
        "student_name": name,
        "father_name": father,
        "mother_name": mother,
        "institute": inst,
        "board": "DINAJPUR",
        "group": group,
        "result": result_val,
        "total_marks": marks_val,
        "subject_grades": subject_grades,
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

def fetch_single_student(session: requests.Session, roll: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """Fetches and parses a single student result with exponential retry backoff."""
    url = ENDPOINT.format(roll=roll)
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=8)
            if resp.status_code == 200:
                parsed = parse_student_html(resp.text, roll)
                if parsed:
                    return parsed
            elif resp.status_code == 429:
                cooldown = min(int(resp.headers.get("Retry-After", 2)), 5)
                time.sleep(cooldown)
                continue
        except Exception:
            time.sleep(0.5 * attempt)
    return None
