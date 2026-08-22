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

    def _solve_gateway_if_needed(self, soup: BeautifulSoup) -> bool:
        """Auto-solves the gateway human check challenge if presented."""
        challenge_form = soup.find('form', class_='challenge-form')
        if not challenge_form:
            return False

        try:
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
            return True
        except Exception:
            return False

    def parse_institution_html(self, html_content: str, eiin: int, exam_year: str = "2026", board: str = "DINAJPUR") -> Dict[str, Any]:
        """Parses the institution summary table and student roster according to standard specification."""
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Base Structured Object
        result = {
            "eiin": int(eiin),
            "name": "",
            "upazila": "",
            "district": "",
            "board": board.upper(),
            "exam_year": str(exam_year),
            "statistics": {
                "appeared": 0,
                "passed": 0,
                "failed": 0,
                "gpa5": 0,
                "pass_rate": 0.0,
                "avg_gpa": 0.0
            },
            "groups": {
                "science": {"appeared": 0, "passed": 0, "gpa5": 0},
                "humanities": {"appeared": 0, "passed": 0, "gpa5": 0},
                "business_studies": {"appeared": 0, "passed": 0, "gpa5": 0}
            },
            "students": []
        }

        # 2. Extract Metadata from Info Table
        info_table = soup.find("table", class_="inst-info-table")
        if info_table:
            for tr in info_table.find_all("tr"):
                tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if len(tds) >= 4:
                    k1, v1, k2, v2 = tds[0], tds[1], tds[2], tds[3]
                    if "District" in k2: result["district"] = v2
                    if "GPA" in k1 and v1.isdigit(): result["statistics"]["gpa5"] = int(v1)
                    if "Appeared" in k2 and v2.isdigit(): result["statistics"]["appeared"] = int(v2)
                    if "Passed" in k1 and v1.isdigit(): result["statistics"]["passed"] = int(v1)
                    if "Pass %" in k2:
                        try: result["statistics"]["pass_rate"] = float(v2)
                        except ValueError: pass
                elif len(tds) >= 2:
                    k, v = tds[0], tds[1]
                    if "Institute" in k: result["name"] = v
                    if "Thana/Upazilla" in k or "Upazilla" in k: result["upazila"] = v

        result["statistics"]["failed"] = max(0, result["statistics"]["appeared"] - result["statistics"]["passed"])

        # 3. Extract Group-Wise Statistics & Student Roster
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
                            result["groups"][group_key]["appeared"] += 1
                        elif is_fail or score_str.startswith("F") or "FAIL" in score_str:
                            status = "FAILED"
                            gpa_val = score_str
                            result["groups"][group_key]["appeared"] += 1
                        else:
                            status = "PASSED"
                            gpa_val = score_str
                            result["groups"][group_key]["appeared"] += 1
                            result["groups"][group_key]["passed"] += 1
                            try:
                                num_gpa = float(score_str)
                                gpa_sum += num_gpa
                                passed_gpa_count += 1
                                if num_gpa == 5.0:
                                    result["groups"][group_key]["gpa5"] += 1
                            except ValueError:
                                pass

                        result["students"].append({
                            "roll": roll_num,
                            "gpa": gpa_val,
                            "group": group_key.upper(),
                            "status": status,
                            "eiin": int(eiin)
                        })

        if passed_gpa_count > 0:
            result["statistics"]["avg_gpa"] = round(gpa_sum / passed_gpa_count, 2)

        return result

    def _unlock_session(self) -> Optional[str]:
        """Resolves gateway check and returns a fresh CSRF token."""
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
                time.sleep(1)
        return None

    def fetch_by_eiin(self, eiin: Any, exam_year: str = "2026", board: str = "DINAJPUR", retry_count: int = 2) -> Optional[Dict[str, Any]]:
        """Queries the official Dinajpur Board portal for a given 6-digit EIIN with rate-limit recovery."""
        eiin_str = str(eiin).strip()
        if not (eiin_str.isdigit() and len(eiin_str) == 6):
            return {"error": "Invalid EIIN format. Must be a 6-digit number.", "status": 400}

        search_url = f"{self.base_url}/search/institute"

        for attempt in range(retry_count + 1):
            try:
                token_val = self._unlock_session()
                if not token_val:
                    if attempt < retry_count:
                        time.sleep(1)
                        continue
                    return {"error": "Could not unlock session", "status": 500}

                # Submit EIIN
                post_r = self.session.post(
                    search_url,
                    data={'_token': token_val, 'eiin_no': eiin_str, 'submit': '1'},
                    timeout=15
                )

                if post_r.status_code == 429:
                    retry_after = int(post_r.headers.get("Retry-After", 30))
                    time.sleep(retry_after)
                    continue

                if post_r.status_code == 200:
                    soup = BeautifulSoup(post_r.text, 'html.parser')
                    if soup.find('form', class_='challenge-form'):
                        token_val = self._unlock_session()
                        post_r = self.session.post(
                            search_url,
                            data={'_token': token_val, 'eiin_no': eiin_str, 'submit': '1'},
                            timeout=15
                        )
                    
                    parsed = self.parse_institution_html(post_r.text, int(eiin_str), exam_year, board)
                    if parsed.get("name") or parsed.get("students"):
                        return parsed
                    elif "No result found" in post_r.text or "Invalid" in post_r.text:
                        return {"error": "EIIN not found", "status": 404, "eiin": int(eiin_str)}
                    return parsed

            except Exception as e:
                if attempt < retry_count:
                    time.sleep(1)
                    continue
                return {"error": str(e), "status": 500, "eiin": int(eiin_str)}

        return {"error": "Request timed out or failed", "status": 504, "eiin": int(eiin_str)}


# Example usage
if __name__ == "__main__":
    fetcher = InstituteResultFetcher()
    test_eiin = 125205
    print(f"[*] Fetching summary data for EIIN: {test_eiin}...")
    res = fetcher.fetch_by_eiin(test_eiin, exam_year="2026")
    print(json.dumps(res, indent=2, ensure_ascii=False))
