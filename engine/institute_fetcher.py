"""
Official EIIN-Based Educational Institution Result Aggregator & Normalizer
"""

import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from collections import Counter
from typing import Dict, Any, Optional, List


class InstituteResultFetcher:
    def __init__(self, base_url: str = "https://results.dinajpurboard.gov.bd"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.base_url}/search/institute"
        })

    def _unlock_session(self) -> Optional[str]:
        url = f"{self.base_url}/search/institute"
        for _ in range(3):
            try:
                r = self.session.get(url, timeout=15)
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Check if gateway challenge is present
                if soup.find('form', class_='challenge-form'):
                    token = soup.find('input', {'name': '_token'})['value']
                    challenge_token = soup.find('input', {'name': 'challenge_token'})['value']
                    choices = soup.select('.symbol-choice')
                    symbols = [(c.find('input')['value'], c.find('span', {'aria-hidden': 'true'}).get_text(strip=True)) for c in choices]
                    counts = Counter([sym for val, sym in symbols])
                    odd_sym = min(counts, key=counts.get)
                    ans_val = next(val for val, sym in symbols if sym == odd_sym)
                    
                    self.session.post(
                        f"{self.base_url}/result-check",
                        data={'_token': token, 'challenge_token': challenge_token, 'answer': ans_val},
                        timeout=15
                    )
                    time.sleep(0.3)
                    continue
                
                form = soup.find('form')
                if form and form.find('input', {'name': '_token'}):
                    return form.find('input', {'name': '_token'})['value']
            except Exception:
                time.sleep(0.5)
        return None

    def fetch_by_eiin(self, eiin: Any, exam_year: str = "2026", board: str = "DINAJPUR") -> Dict[str, Any]:
        token = self._unlock_session()
        if not token:
            return {"error": "Could not get CSRF token", "success": False, "name": None, "students": []}

        post_r = self.session.post(
            f"{self.base_url}/search/institute",
            data={'_token': token, 'eiin_no': str(eiin).strip(), 'submit': '1'},
            timeout=15
        )

        if post_r.status_code == 200:
            soup = BeautifulSoup(post_r.text, 'html.parser')
            # Check if challenge intercepted the POST
            if soup.find('form', class_='challenge-form'):
                token = self._unlock_session()
                post_r = self.session.post(
                    f"{self.base_url}/search/institute",
                    data={'_token': token, 'eiin_no': str(eiin).strip(), 'submit': '1'},
                    timeout=15
                )
                soup = BeautifulSoup(post_r.text, 'html.parser')

            info_table = soup.find('table', class_='inst-info-table')
            if not info_table:
                return {"error": "Institute not found", "success": False, "name": None, "students": []}

            # Parse info
            name, upazila, district = "", "", ""
            stats = {"appeared": 0, "passed": 0, "failed": 0, "gpa5": 0, "pass_rate": 0.0, "avg_gpa": 0.0}

            for tr in info_table.find_all('tr'):
                tds = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if len(tds) >= 4:
                    if "District" in tds[2]: district = tds[3]
                    if "GPA" in tds[0] and tds[1].isdigit(): stats["gpa5"] = int(tds[1])
                    if "Appeared" in tds[2] and tds[3].isdigit(): stats["appeared"] = int(tds[3])
                    if "Passed" in tds[0] and tds[1].isdigit(): stats["passed"] = int(tds[1])
                    if "Pass %" in tds[2]:
                        try: stats["pass_rate"] = float(tds[3])
                        except ValueError: pass
                elif len(tds) >= 2:
                    if "Institute" in tds[0]: name = tds[1]
                    if "Thana/Upazilla" in tds[0] or "Upazilla" in tds[0]: upazila = tds[1]

            stats["failed"] = max(0, stats["appeared"] - stats["passed"])

            # Groups and Student Roster
            students = []
            groups = {
                "science": {"appeared": 0, "passed": 0, "gpa5": 0},
                "humanities": {"appeared": 0, "passed": 0, "gpa5": 0},
                "business_studies": {"appeared": 0, "passed": 0, "gpa5": 0}
            }

            gpa_sum = 0.0
            passed_gpa_count = 0

            for section in soup.find_all("div", class_="result-section"):
                title_el = section.find("div", class_="section-title")
                title_text = title_el.get_text(strip=True).lower() if title_el else ""
                
                group_key = "science"
                if "humanities" in title_text or "arts" in title_text:
                    group_key = "humanities"
                elif "business" in title_text or "commerce" in title_text:
                    group_key = "business_studies"

                for block in section.find_all("div", class_="rest-block"):
                    is_fail = "fail-line" in block.get("class", [])
                    is_abs = "abs-line" in block.get("class", [])

                    for item in block.select(".rest-item"):
                        txt = item.get_text(strip=True)
                        match = re.search(r'\b(\d{6})\[([^\]]+)\]', txt)
                        if match:
                            roll_str, score_str = match.group(1), match.group(2).strip()
                            roll_num = int(roll_str)
                            
                            if is_abs or "ABS" in score_str:
                                status = "ABSENT"
                                gpa_val = "ABS."
                                groups[group_key]["appeared"] += 1
                            elif is_fail or score_str.startswith("F") or "FAIL" in score_str:
                                status = "FAILED"
                                gpa_val = score_str
                                groups[group_key]["appeared"] += 1
                            else:
                                status = "PASSED"
                                gpa_val = score_str
                                groups[group_key]["appeared"] += 1
                                groups[group_key]["passed"] += 1
                                try:
                                    num_gpa = float(score_str)
                                    gpa_sum += num_gpa
                                    passed_gpa_count += 1
                                    if num_gpa == 5.0:
                                        groups[group_key]["gpa5"] += 1
                                except ValueError:
                                    pass

                            students.append({
                                "roll": roll_num,
                                "gpa": gpa_val,
                                "group": group_key.upper(),
                                "status": status,
                                "eiin": int(eiin)
                            })

            if passed_gpa_count > 0:
                stats["avg_gpa"] = round(gpa_sum / passed_gpa_count, 2)

            return {
                "eiin": int(eiin),
                "name": name,
                "district": district,
                "upazila": upazila,
                "board": board.upper(),
                "exam_year": str(exam_year),
                "statistics": stats,
                "groups": groups,
                "students": students,
                "success": True
            }

        return {"error": f"HTTP Status {post_r.status_code}", "success": False, "name": None, "students": []}
