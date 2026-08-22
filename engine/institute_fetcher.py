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
from typing import Dict, Any, Optional, List, Callable
from urllib.parse import urljoin


class InstituteResultFetcher:
    def __init__(self, base_url: str = "https://results.dinajpurboard.gov.bd"):
        self.base_url = base_url
        self.reset_session()

    def reset_session(self):
        """Creates a fresh HTTP session with standard browser headers."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.base_url}/search/institute"
        })

    def _solve_gateway(self, soup: BeautifulSoup, current_url: str) -> bool:
        """Solves the symbol challenge (human check) on the gateway."""
        try:
            form = soup.find('form', class_='challenge-form') or soup.find('form')
            if not form:
                return False

            action = form.get('action') or current_url
            action_url = urljoin(current_url, action)

            # Extract tokens
            payload = {}
            for h in form.find_all('input', {'type': 'hidden'}):
                if h.get('name'):
                    payload[h.get('name')] = h.get('value', '')

            # Parse symbol choices
            choices = soup.select('.symbol-choice')
            if not choices:
                return False

            symbols = []
            for c in choices:
                inp = c.find('input')
                sym_el = c.find('span', {'aria-hidden': 'true'}) or c
                sym = sym_el.get_text(strip=True)
                if inp:
                    symbols.append((inp.get('value', '0'), sym))

            if not symbols:
                return False

            # Find the odd one out
            counts = Counter([sym for val, sym in symbols])
            odd_sym = min(counts, key=counts.get)
            ans_val = next(val for val, sym in symbols if sym == odd_sym)

            payload['answer'] = ans_val
            self.session.headers.update({"Referer": current_url})
            time.sleep(0.2)
            resp = self.session.post(action_url, data=payload, timeout=15)
            
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 15))
                time.sleep(min(retry_after + 1, 35))
                return False

            return resp.status_code in [200, 302]
        except Exception:
            return False

    def _unlock_session(self, status_callback: Optional[Callable[[str], None]] = None) -> Optional[str]:
        url = f"{self.base_url}/search/institute"
        for attempt in range(1, 7):
            try:
                r = self.session.get(url, timeout=15)
                
                # If rate limited, wait out cooldown and retry
                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", 15))
                    cooldown = min(retry_after + 1, 35)
                    if status_callback:
                        status_callback(f"Rate limited (429). Waiting {cooldown}s cooldown... (Attempt {attempt}/6)")
                    time.sleep(cooldown)
                    self.reset_session()
                    continue

                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Check if gateway challenge is present
                if soup.find('form', class_='challenge-form') or 'Find the different symbol' in r.text:
                    if status_callback:
                        status_callback(f"Solving gateway pattern challenge... (Attempt {attempt}/6)")
                    solved = self._solve_gateway(soup, r.url)
                    if not solved:
                        time.sleep(1.0)
                        self.reset_session()
                        continue
                    time.sleep(0.5)
                    # Fetch search form after unlock
                    r_after = self.session.get(url, timeout=15)
                    soup = BeautifulSoup(r_after.text, 'html.parser')
                
                # Verify search form has eiin_no
                if soup.find('input', {'name': 'eiin_no'}):
                    token_el = soup.find('input', {'name': '_token'})
                    if token_el:
                        return token_el['value']
            except Exception:
                time.sleep(1.0)
        return None

    def fetch_by_eiin(
        self,
        eiin: Any,
        exam_year: str = "2026",
        board: str = "DINAJPUR",
        status_callback: Optional[Callable[[str], None]] = None,
        max_retries: int = 6
    ) -> Dict[str, Any]:
        """
        Fetches official gazette results for an EIIN with automatic retries for rate limits,
        failed pattern challenges, and session renewals.
        """
        eiin_clean = str(eiin).strip()
        url = f"{self.base_url}/search/institute"

        for attempt in range(1, max_retries + 1):
            try:
                token = self._unlock_session(status_callback=status_callback)
                if not token:
                    if status_callback and attempt < max_retries:
                        status_callback(f"Retrying session unlock (Attempt {attempt}/{max_retries})...")
                    self.reset_session()
                    time.sleep(1.5)
                    continue

                post_r = self.session.post(
                    url,
                    data={'_token': token, 'eiin_no': eiin_clean, 'submit': '1'},
                    timeout=15
                )

                # Rate limit handling on POST
                if post_r.status_code == 429:
                    retry_after = int(post_r.headers.get("Retry-After", 15))
                    cooldown = min(retry_after + 1, 35)
                    if status_callback:
                        status_callback(f"Rate limited on POST (429). Cooldown: {cooldown}s (Attempt {attempt}/{max_retries})")
                    time.sleep(cooldown)
                    self.reset_session()
                    continue

                if post_r.status_code == 200:
                    soup = BeautifulSoup(post_r.text, 'html.parser')
                    
                    # If challenge intercepted the POST response, solve and resubmit
                    if soup.find('form', class_='challenge-form'):
                        if status_callback:
                            status_callback(f"Resolving post-challenge pattern (Attempt {attempt}/{max_retries})...")
                        self._solve_gateway(soup)
                        time.sleep(0.4)
                        token = self._unlock_session(status_callback=status_callback)
                        if token:
                            post_r = self.session.post(
                                url,
                                data={'_token': token, 'eiin_no': eiin_clean, 'submit': '1'},
                                timeout=15
                            )
                            soup = BeautifulSoup(post_r.text, 'html.parser')

                    info_table = soup.find('table', class_='inst-info-table')
                    if not info_table:
                        if attempt < max_retries:
                            if status_callback:
                                status_callback(f"Retrying institute query... (Attempt {attempt}/{max_retries})")
                            self.reset_session()
                            time.sleep(1.5)
                            continue
                        return {"error": "Institute not found or empty response", "success": False, "name": None, "students": []}

                    # Succeeded! Break out of retry loop
                    break
            except Exception as e:
                if attempt < max_retries:
                    if status_callback:
                        status_callback(f"Connection glitch: {str(e)[:30]}... Retrying ({attempt}/{max_retries})")
                    time.sleep(2.0)
                    self.reset_session()
                    continue
                return {"error": f"Request failed: {str(e)}", "success": False, "name": None, "students": []}
        else:
            return {"error": "Max retries exceeded", "success": False, "name": None, "students": []}

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
