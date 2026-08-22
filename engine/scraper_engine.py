import json
import logging
import os
import re
import time
from collections import Counter
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .captcha_solver import NumericalCaptchaSolver
from .parser_utils import parse_html_to_json

logger = logging.getLogger(__name__)


class AutoFormScraper:
    """
    Automated Form Scraper with:
    - Single and Multi-Record Batch Scraping
    - Gateway / Human Check Symbol Solver (e.g. Bangladesh Education Boards)
    - Numerical / Arithmetic CAPTCHA Solver
    - Action / Button Click Trigger
    - Structured JSON Exporter
    """

    def __init__(self, headers: Optional[Dict[str, str]] = None, timeout: int = 25):
        self.session = requests.Session()
        self.timeout = timeout
        default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
        }
        if headers:
            default_headers.update(headers)
        self.session.headers.update(default_headers)

    def reset_session(self):
        """Reset the underlying session cookies and tokens."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
        })

    def scrape(
        self,
        url: str,
        input_fields: Dict[str, Any],
        captcha_selector: Optional[str] = None,
        captcha_input_name: Optional[str] = None,
        button_selector: Optional[str] = None,
        form_selector: Optional[str] = None,
        method: Optional[str] = None,
        output_file: Optional[str] = None,
        include_html: bool = False,
        _retry_count: int = 1
    ) -> Dict[str, Any]:
        """
        Execute a single form scrape flow.
        """
        start_time = time.time()
        result_log = []

        def log(msg: str):
            logger.info(msg)
            result_log.append(msg)

        log(f"Fetching target URL: {url}")
        try:
            get_resp = self.session.get(url, timeout=self.timeout)
            if get_resp.status_code == 429 and _retry_count > 0:
                retry_after = int(get_resp.headers.get('Retry-After', 30))
                log(f"Rate limited on GET (429). Cooldown: {retry_after}s...")
                time.sleep(retry_after)
                self.reset_session()
                return self.scrape(
                    url=url,
                    input_fields=input_fields,
                    captcha_selector=captcha_selector,
                    captcha_input_name=captcha_input_name,
                    button_selector=button_selector,
                    form_selector=form_selector,
                    method=method,
                    output_file=output_file,
                    include_html=include_html,
                    _retry_count=_retry_count - 1
                )
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load page: {str(e)}",
                "logs": result_log,
                "elapsed_seconds": round(time.time() - start_time, 3)
            }

        soup = BeautifulSoup(get_resp.text, 'html.parser')

        # 0. Check and Auto-Solve Gateway / Human Check if present (e.g. Dinajpur/Dhaka Board)
        if self._is_symbol_challenge_page(soup, get_resp.text):
            log("Detected Gateway 'Human Check — Find the different symbol'. Auto-solving gateway challenge...")
            gateway_success, gateway_msg, post_soup = self._solve_symbol_challenge(soup, get_resp.url)
            log(gateway_msg)
            if gateway_success:
                time.sleep(0.4)
                if post_soup and post_soup.find('form') and not self._is_symbol_challenge_page(post_soup, str(post_soup)):
                    soup = post_soup
                else:
                    self.session.headers.update({"Referer": url})
                    get_resp = self.session.get(url, timeout=self.timeout)
                    soup = BeautifulSoup(get_resp.text, 'html.parser')

        # 1. Locate target form
        form = None
        if form_selector:
            form = soup.select_one(form_selector)
        if not form:
            form = soup.find('form')

        # If still no form and retry count left, reset session and retry
        if not form and _retry_count > 0:
            log("No form found on page. Refreshing session and retrying...")
            self.reset_session()
            time.sleep(1.0)
            return self.scrape(
                url=url,
                input_fields=input_fields,
                captcha_selector=captcha_selector,
                captcha_input_name=captcha_input_name,
                button_selector=button_selector,
                form_selector=form_selector,
                method=method,
                output_file=output_file,
                include_html=include_html,
                _retry_count=_retry_count - 1
            )

        # Extract hidden inputs / security tokens
        form_data = {}
        if form:
            for hidden in form.find_all('input', {'type': 'hidden'}):
                h_name = hidden.get('name')
                h_val = hidden.get('value', '')
                if h_name:
                    form_data[h_name] = h_val
                    log(f"Extracted hidden field: {h_name} = {h_val}")

        # 2. Find and solve CAPTCHA
        captcha_text = None
        captcha_answer = None

        if captcha_selector:
            captcha_el = soup.select_one(captcha_selector)
            if captcha_el:
                captcha_text = captcha_el.get_text(separator=' ', strip=True)
                log(f"Found CAPTCHA text using selector '{captcha_selector}': '{captcha_text}'")

        # Auto-detect captcha if not provided or not found
        if not captcha_text:
            log("Auto-detecting numerical CAPTCHA on page...")
            captcha_text, detected_answer = self._auto_detect_captcha(soup)
            if captcha_text:
                captcha_answer = detected_answer
                log(f"Auto-detected CAPTCHA text: '{captcha_text}'")

        if captcha_text and captcha_answer is None:
            captcha_answer = NumericalCaptchaSolver.solve(captcha_text)

        if captcha_answer is not None:
            log(f"Solved CAPTCHA: '{captcha_text}' -> Answer: {captcha_answer}")
        else:
            log("Notice: No numerical CAPTCHA detected or challenge is not arithmetic.")

        # Determine captcha input field name
        if not captcha_input_name:
            captcha_input_name = self._auto_find_captcha_input_name(soup)
            if captcha_input_name:
                log(f"Auto-detected CAPTCHA input field name: '{captcha_input_name}'")

        if captcha_input_name and captcha_answer is not None:
            form_data[captcha_input_name] = str(captcha_answer)

        # 3. Populate user input fields
        for field_key, field_value in input_fields.items():
            form_data[field_key] = str(field_value)
            log(f"Filled input: {field_key} = {field_value}")

        # 4. Handle Submit / Action Button Click
        action_url = url
        form_method = method or "POST"
        button_info = {}

        button_el = None
        if button_selector:
            button_el = soup.select_one(button_selector)
            if button_el:
                log(f"Located button by selector '{button_selector}'")

        if not button_el and form:
            button_el = form.find(['button', 'input'], {'type': ['submit', 'button']}) or form.find('button')

        if button_el:
            btn_name = button_el.get('name')
            btn_val = button_el.get('value', '')
            btn_text = button_el.get_text(strip=True) or btn_val or 'Submit'
            btn_action = button_el.get('formaction')
            btn_method = button_el.get('formmethod')

            button_info = {
                "text": btn_text,
                "name": btn_name,
                "value": btn_val
            }
            log(f"Triggering click on button: '{btn_text}' (name={btn_name}, value={btn_val})")

            # Attach button name/value to payload if present
            if btn_name:
                form_data[btn_name] = btn_val

            if btn_action:
                action_url = urljoin(url, btn_action)
            if btn_method and not method:
                form_method = btn_method.upper()

        if form and (not action_url or action_url == url):
            action = form.get('action')
            if action:
                action_url = urljoin(url, action)
            detected_method = form.get('method')
            if not method and detected_method:
                form_method = detected_method.upper()

        log(f"Submitting request to: {action_url} via {form_method}")

        # 5. Submit Form Request
        try:
            if form_method == "POST":
                post_resp = self.session.post(action_url, data=form_data, timeout=self.timeout)
            else:
                post_resp = self.session.get(action_url, params=form_data, timeout=self.timeout)
        except Exception as e:
            return {
                "success": False,
                "error": f"Form submission failed: {str(e)}",
                "logs": result_log,
                "submitted_payload": form_data,
                "elapsed_seconds": round(time.time() - start_time, 3)
            }

        log(f"Form submission response status: {post_resp.status_code}")

        # 6. Parse ALL info on the resulting page into JSON
        parsed_data = parse_html_to_json(
            html_content=post_resp.text,
            url=post_resp.url,
            status_code=post_resp.status_code,
            include_html=include_html
        )

        is_success = post_resp.status_code in [200, 201, 302]
        error_msg = None
        if not is_success:
            if post_resp.status_code == 429 and _retry_count > 0:
                retry_after = int(post_resp.headers.get('Retry-After', 30))
                log(f"Rate limited on POST (429). Waiting {retry_after}s cooldown and resetting session...")
                time.sleep(retry_after)
                self.reset_session()
                return self.scrape(
                    url=url,
                    input_fields=input_fields,
                    captcha_selector=captcha_selector,
                    captcha_input_name=captcha_input_name,
                    button_selector=button_selector,
                    form_selector=form_selector,
                    method=method,
                    output_file=output_file,
                    include_html=include_html,
                    _retry_count=_retry_count - 1
                )
            elif post_resp.status_code in [419, 401] and _retry_count > 0:
                log(f"Session expired or CSRF token mismatch (HTTP {post_resp.status_code}). Resetting session and retrying...")
                self.reset_session()
                time.sleep(1.0)
                return self.scrape(
                    url=url,
                    input_fields=input_fields,
                    captcha_selector=captcha_selector,
                    captcha_input_name=captcha_input_name,
                    button_selector=button_selector,
                    form_selector=form_selector,
                    method=method,
                    output_file=output_file,
                    include_html=include_html,
                    _retry_count=_retry_count - 1
                )
            elif post_resp.status_code == 404:
                error_msg = "Result Not Found (404). Please verify that the credentials are valid for this examination."
            elif post_resp.status_code == 429:
                error_msg = "Rate limit reached (429). Try adding a small delay between requests."
            else:
                error_msg = f"Server returned status {post_resp.status_code}"

        # Extract clean structured student fields
        kv = parsed_data.get("key_value_data", {})
        tables = parsed_data.get("tables", [])

        subject_grades = []
        for t in tables:
            if "marks-table" in t.get("table_class", ""):
                for row in t.get("rows", []):
                    sub_code = row.get("SUB CODE") or row.get("column_1")
                    sub_name = row.get("SUBJECT NAME") or row.get("column_2")
                    grade = row.get("GRADE") or row.get("column_3")
                    if sub_code or sub_name:
                        subject_grades.append({
                            "sub_code": sub_code,
                            "subject_name": sub_name,
                            "grade": grade
                        })

        roll_val = input_fields.get("roll_no") or input_fields.get("roll") or input_fields.get("id")

        final_result = {
            "roll_no": roll_val,
            "success": is_success,
            "status_code": post_resp.status_code,
            "student_name": kv.get("Name of Student") or kv.get("Student Name") or kv.get("Name"),
            "father_name": kv.get("Father's Name") or kv.get("Father Name"),
            "mother_name": kv.get("Mother's Name") or kv.get("Mother Name"),
            "institute": kv.get("Name of Institute") or kv.get("Institute Name") or kv.get("Institute"),
            "board": kv.get("Board", "DINAJPUR" if "dinajpur" in url.lower() else None),
            "group": kv.get("Group"),
            "result": kv.get("Result") or kv.get("GPA"),
            "total_marks": kv.get("TOTAL MARK") or kv.get("Total Marks") or kv.get("Total Mark"),
            "subject_grades": subject_grades,
            "error": error_msg,
            "captcha_info": {
                "question": captcha_text,
                "solution": captcha_answer,
                "input_field": captcha_input_name
            },
            "button_clicked": button_info,
            "submitted_payload": form_data,
            "target_url": url,
            "submitted_url": post_resp.url,
            "logs": result_log,
            "elapsed_seconds": round(time.time() - start_time, 3),
            "data": parsed_data,
            "full_data": parsed_data
        }

        # Save to JSON file if requested
        if output_file:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, indent=2, ensure_ascii=False)
            log(f"Saved scraped JSON output to: {output_file}")

        return final_result

    def batch_scrape(
        self,
        url: str,
        items_list: List[Dict[str, Any]],
        base_fields: Optional[Dict[str, Any]] = None,
        captcha_selector: Optional[str] = None,
        captcha_input_name: Optional[str] = None,
        button_selector: Optional[str] = None,
        form_selector: Optional[str] = None,
        method: Optional[str] = None,
        delay_seconds: float = 1.0,
        output_file: Optional[str] = None,
        include_html: bool = False
    ) -> Dict[str, Any]:
        """
        Scrape a batch list of records one by one with a configurable delay.
        """
        total_items = len(items_list)
        records = []
        start_batch_time = time.time()
        success_count = 0
        failed_count = 0

        logger.info(f"Starting batch scrape of {total_items} items with {delay_seconds}s delay...")

        for idx, item in enumerate(items_list):
            logger.info(f"--- Processing item {idx + 1}/{total_items}: {item} ---")
            merged_fields = dict(base_fields or {})
            merged_fields.update(item)

            res = self.scrape(
                url=url,
                input_fields=merged_fields,
                captcha_selector=captcha_selector,
                captcha_input_name=captcha_input_name,
                button_selector=button_selector,
                form_selector=form_selector,
                method=method,
                output_file=None,
                include_html=include_html
            )

            record_entry = {
                "index": idx + 1,
                "roll_no": res.get("roll_no") or item.get("roll_no"),
                "success": res.get("success", False),
                "status_code": res.get("status_code"),
                "student_name": res.get("student_name"),
                "father_name": res.get("father_name"),
                "mother_name": res.get("mother_name"),
                "institute": res.get("institute"),
                "board": res.get("board"),
                "group": res.get("group"),
                "result": res.get("result"),
                "total_marks": res.get("total_marks"),
                "subject_grades": res.get("subject_grades", []),
                "error": res.get("error"),
                "captcha_info": res.get("captcha_info"),
                "item_inputs": item,
                "elapsed_seconds": res.get("elapsed_seconds"),
                "data": res.get("data"),
                "full_data": res.get("full_data")
            }

            if res.get("success"):
                success_count += 1
            else:
                failed_count += 1

            records.append(record_entry)

            # Delay before next item (unless last item)
            if idx < total_items - 1 and delay_seconds > 0:
                time.sleep(delay_seconds)

        final_batch_result = {
            "batch_summary": {
                "total_requested": total_items,
                "total_success": success_count,
                "total_failed": failed_count,
                "total_elapsed_seconds": round(time.time() - start_batch_time, 3),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "target_url": url,
            "records": records
        }

        if output_file:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_batch_result, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved batch JSON output to: {output_file}")

        return final_batch_result

    def batch_scrape_stream(
        self,
        url: str,
        items_list: List[Dict[str, Any]],
        base_fields: Optional[Dict[str, Any]] = None,
        captcha_selector: Optional[str] = None,
        captcha_input_name: Optional[str] = None,
        button_selector: Optional[str] = None,
        form_selector: Optional[str] = None,
        method: Optional[str] = None,
        delay_seconds: float = 1.0,
        include_html: bool = False
    ) -> Iterator[Dict[str, Any]]:
        """
        Generator for Server-Sent Events (SSE) streaming individual item completions in real-time.
        """
        total_items = len(items_list)
        start_batch_time = time.time()
        success_count = 0
        failed_count = 0

        yield {
            "type": "start",
            "total": total_items,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        for idx, item in enumerate(items_list):
            merged_fields = dict(base_fields or {})
            merged_fields.update(item)

            res = self.scrape(
                url=url,
                input_fields=merged_fields,
                captcha_selector=captcha_selector,
                captcha_input_name=captcha_input_name,
                button_selector=button_selector,
                form_selector=form_selector,
                method=method,
                include_html=include_html
            )

            if res.get("success"):
                success_count += 1
            else:
                failed_count += 1

            record_entry = {
                "index": idx + 1,
                "roll_no": res.get("roll_no") or item.get("roll_no"),
                "success": res.get("success", False),
                "status_code": res.get("status_code"),
                "student_name": res.get("student_name"),
                "father_name": res.get("father_name"),
                "mother_name": res.get("mother_name"),
                "institute": res.get("institute"),
                "board": res.get("board"),
                "group": res.get("group"),
                "result": res.get("result"),
                "total_marks": res.get("total_marks"),
                "subject_grades": res.get("subject_grades", []),
                "error": res.get("error"),
                "captcha_info": res.get("captcha_info"),
                "item_inputs": item,
                "elapsed_seconds": res.get("elapsed_seconds"),
                "data": res.get("data"),
                "full_data": res.get("full_data")
            }

            yield {
                "type": "item",
                "index": idx + 1,
                "total": total_items,
                "progress_percent": round(((idx + 1) / total_items) * 100, 1),
                "record": record_entry
            }

            if idx < total_items - 1 and delay_seconds > 0:
                time.sleep(delay_seconds)

        yield {
            "type": "complete",
            "summary": {
                "total_requested": total_items,
                "total_success": success_count,
                "total_failed": failed_count,
                "total_elapsed_seconds": round(time.time() - start_batch_time, 3),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }

    def _is_symbol_challenge_page(self, soup: BeautifulSoup, raw_html: str) -> bool:
        """Check if page is a symbol-choice Human Check gateway."""
        if soup.find('form', class_='challenge-form') or soup.select('.symbol-choice'):
            return True
        if 'Find the different symbol' in raw_html or 'Human Check' in raw_html:
            return True
        return False

    def _solve_symbol_challenge(self, soup: BeautifulSoup, current_url: str) -> Tuple[bool, str, Optional[BeautifulSoup]]:
        """Automatically find the odd symbol and submit the gateway challenge."""
        try:
            form = soup.find('form', class_='challenge-form') or soup.find('form')
            if not form:
                return False, "Gateway form not found.", None

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
                return False, "No symbol choices found.", None

            symbols = []
            for c in choices:
                inp = c.find('input')
                sym_el = c.find('span', {'aria-hidden': 'true'}) or c
                sym = sym_el.get_text(strip=True)
                if inp:
                    symbols.append((inp.get('value', '0'), sym))

            if not symbols:
                return False, "Could not extract symbol values.", None

            # Find the odd one out (count == 1)
            counts = Counter([sym for val, sym in symbols])
            odd_sym = min(counts, key=counts.get)
            ans_val = next(val for val, sym in symbols if sym == odd_sym)

            payload['answer'] = ans_val
            self.session.headers.update({"Referer": current_url})
            time.sleep(0.2)
            resp = self.session.post(action_url, data=payload, timeout=self.timeout)

            new_soup = BeautifulSoup(resp.text, 'html.parser')
            return True, f"Gateway solved: Unique symbol identified as option '{ans_val}'. Session unlocked!", new_soup
        except Exception as e:
            return False, f"Failed to solve symbol gateway: {str(e)}", None

    def _auto_detect_captcha(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[int]]:
        """Search through labels, spans, divs, and paragraphs for math captcha questions."""
        candidates = soup.find_all(['label', 'span', 'div', 'p', 'b', 'strong', 'td'])
        for el in candidates:
            if len(el.find_all(['div', 'form', 'table'])) > 0:
                continue
            text = el.get_text(separator=' ', strip=True)
            if 3 <= len(text) <= 80:
                if any(op in text.lower() for op in ['+', '-', '*', 'plus', 'minus', 'times', 'divided', 'calculate', 'sum of', 'captcha']):
                    solution = NumericalCaptchaSolver.solve(text)
                    if solution is not None:
                        return text, solution
        return None, None

    def _auto_find_captcha_input_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Auto-detect the input element intended for the CAPTCHA response."""
        for input_el in soup.find_all('input'):
            input_type = input_el.get('type', 'text').lower()
            if input_type in ['hidden', 'submit', 'button', 'checkbox', 'radio']:
                continue

            name = input_el.get('name', '')
            id_attr = input_el.get('id', '')
            placeholder = input_el.get('placeholder', '')

            check_str = f"{name} {id_attr} {placeholder}".lower()
            if any(k in check_str for k in ['captcha', 'code', 'math', 'calc', 'result', 'ans', 'verify']):
                return name or id_attr

        return "captcha"
