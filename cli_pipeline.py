"""
EIIN-to-Student Results CLI Pipeline:
1. Input EIIN number(s)
2. Scrape Institute Result page from Dinajpur Board
3. Extract Institute Metadata (Name, District, Thana/Upazilla) and ALL student roll numbers
4. Group rolls by Upazilla
5. Scrape full student results (or generate chunks for 20-worker parallel cloud runners)
6. Save structured student datasets into separate JSON files per Upazilla (e.g. results_upazilla_kishoreganj.json)
"""

import sys
import os
import re
import json
import time
import argparse
import logging
from bs4 import BeautifulSoup
from collections import Counter
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from engine.scraper_engine import AutoFormScraper

class InstituteResultPipeline:
    def __init__(self, output_dir: str = "upazilla_results"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.scraper = AutoFormScraper()

    def scrape_institute_by_eiin(self, eiin: str) -> Dict[str, Any]:
        """Scrapes Dinajpur board institute result and extracts metadata and student roll numbers."""
        import requests
        from collections import Counter
        
        eiin_clean = str(eiin).strip()
        logger.info(f"[*] Querying Institute Result for EIIN: {eiin_clean}...")

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://results.dinajpurboard.gov.bd/search/institute"
        })

        url = "https://results.dinajpurboard.gov.bd/search/institute"
        try:
            r = session.get(url, timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')

            if soup.find('form', class_='challenge-form'):
                token = soup.find('input', {'name': '_token'})['value']
                challenge_token = soup.find('input', {'name': 'challenge_token'})['value']
                choices = soup.select('.symbol-choice')
                symbols = [(c.find('input')['value'], c.find('span', {'aria-hidden': 'true'}).get_text(strip=True)) for c in choices]
                counts = Counter([sym for val, sym in symbols])
                odd_sym = min(counts, key=counts.get)
                ans_val = next(val for val, sym in symbols if sym == odd_sym)
                session.post('https://results.dinajpurboard.gov.bd/result-check', data={'_token': token, 'challenge_token': challenge_token, 'answer': ans_val}, timeout=15)
                time.sleep(0.3)
                r = session.get(url, timeout=15)
                soup = BeautifulSoup(r.text, 'html.parser')

            form = soup.find('form')
            if not form:
                return {"eiin": eiin_clean, "success": False, "thana_upazilla": "UNKNOWN_UPAZILLA", "rolls": []}

            token_val = form.find('input', {'name': '_token'})['value']
            post_r = session.post(url, data={'_token': token_val, 'eiin_no': eiin_clean, 'submit': '1'}, timeout=15)
            html = post_r.text
            soup = BeautifulSoup(html, "html.parser")

            meta = {
                "eiin": eiin_clean,
                "success": True,
                "institute_name": None,
                "district": None,
                "thana_upazilla": "UNKNOWN_UPAZILLA",
                "stats": {}
            }

            info_table = soup.find("table", class_="inst-info-table")
            if info_table:
                for tr in info_table.find_all("tr"):
                    tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if len(tds) >= 4:
                        k1, v1, k2, v2 = tds[0], tds[1], tds[2], tds[3]
                        if "District" in k2: meta["district"] = v2
                        if "GPA" in k1: meta["stats"]["gpa_5"] = v1
                        if "Appeared" in k2: meta["stats"]["appeared"] = v2
                        if "Passed" in k1: meta["stats"]["passed"] = v1
                        if "Pass %" in k2: meta["stats"]["pass_percentage"] = v2
                    elif len(tds) >= 2:
                        k, v = tds[0], tds[1]
                        if "Institute" in k: meta["institute_name"] = v
                        if "Thana/Upazilla" in k or "Upazilla" in k: meta["thana_upazilla"] = v

            # Extract all roll numbers from rest-item tags: e.g. 479675[3.89], 479674[F2], 479691[ABS.]
            extracted_rolls = []
            for item in soup.select(".rest-item"):
                txt = item.get_text(strip=True)
                match = re.search(r'\b(\d{6})\[', txt)
                if match:
                    extracted_rolls.append(match.group(1))

            # Fallback 6-digit regex excluding EIIN
            if not extracted_rolls:
                all_6digits = re.findall(r'\b\d{6}\b', html)
                extracted_rolls = [r for r in all_6digits if r != eiin_clean]

            unique_rolls = list(dict.fromkeys(extracted_rolls))
            meta["rolls"] = unique_rolls
            meta["total_rolls_found"] = len(unique_rolls)

            upazilla = meta.get("thana_upazilla") or "UNKNOWN_UPAZILLA"
            inst_name = meta.get("institute_name") or "Unknown Institute"
            logger.info(f"    ✅ Extracted: {inst_name} | Upazilla: {upazilla} | Rolls Found: {len(unique_rolls)}")
            return meta

        except Exception as e:
            logger.error(f"[!] Error scraping EIIN {eiin_clean}: {e}")
            return {"eiin": eiin_clean, "success": False, "thana_upazilla": "UNKNOWN_UPAZILLA", "rolls": []}

    def process_eiins_and_organize_by_upazilla(self, eiin_list: List[str]) -> Dict[str, Dict[str, Any]]:
        """Processes multiple EIINs and groups rolls and metadata by Upazilla."""
        upazilla_groups = {}

        for idx, eiin in enumerate(eiin_list, 1):
            print(f"\n[{idx}/{len(eiin_list)}] Processing EIIN: {eiin}")
            meta = self.scrape_institute_by_eiin(eiin)
            upazilla_raw = meta.get("thana_upazilla") or "UNKNOWN_UPAZILLA"
            upazilla_key = re.sub(r'[^a-zA-Z0-9]+', '_', upazilla_raw.strip().upper()).strip('_')

            if upazilla_key not in upazilla_groups:
                upazilla_groups[upazilla_key] = {
                    "upazilla_name": upazilla_raw.upper(),
                    "district": meta.get("district", "UNKNOWN"),
                    "institutes": [],
                    "all_rolls": []
                }

            upazilla_groups[upazilla_key]["institutes"].append({
                "eiin": meta["eiin"],
                "institute_name": meta.get("institute_name"),
                "rolls_count": len(meta.get("rolls", []))
            })
            upazilla_groups[upazilla_key]["all_rolls"].extend(meta.get("rolls", []))

            # Small delay between institute queries
            time.sleep(1.0)

        # Deduplicate rolls per upazilla
        for upz, data in upazilla_groups.items():
            data["all_rolls"] = list(dict.fromkeys(data["all_rolls"]))
            data["total_unique_rolls"] = len(data["all_rolls"])

            # Save Upazilla Rolls List
            rolls_path = os.path.join(self.output_dir, f"rolls_upazilla_{upz.lower()}.json")
            with open(rolls_path, "w", encoding="utf-8") as f:
                json.dump(data["all_rolls"], f, indent=2)
            logger.info(f"[+] Saved {len(data['all_rolls'])} rolls for Upazilla '{data['upazilla_name']}' to: {rolls_path}")

        return upazilla_groups

    def scrape_and_save_upazilla_students(self, upazilla_groups: Dict[str, Dict[str, Any]], delay: float = 3.2, webhook_url: Optional[str] = None):
        """Scrapes student details and saves separate JSON result files per Upazilla."""
        for upz, data in upazilla_groups.items():
            upazilla_name = data["upazilla_name"]
            rolls = data["all_rolls"]
            output_file = os.path.join(self.output_dir, f"results_upazilla_{upz.lower()}.json")

            print(f"\n=======================================================")
            print(f"🚀 Scraping {len(rolls)} Student Results for Upazilla: {upazilla_name}")
            print(f"📁 Output Destination: {output_file}")
            print("=======================================================")

            existing_records = []
            if os.path.exists(output_file):
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        prev = json.load(f)
                        existing_records = prev.get("records", [])
                except Exception:
                    pass

            done_rolls = {r.get("roll_no") for r in existing_records}
            pending_rolls = [r for r in rolls if r not in done_rolls]

            print(f"[*] Already Scraped: {len(done_rolls)} | Remaining: {len(pending_rolls)}")

            for idx, roll in enumerate(pending_rolls, 1):
                print(f"[{idx}/{len(pending_rolls)}] [{upazilla_name}] Scraping Roll {roll}...")
                res = self.scraper.scrape(
                    url="https://results.dinajpurboard.gov.bd/search/student",
                    input_fields={"roll_no": roll},
                    captcha_input_name="captcha",
                    button_selector='button[name="submit"]',
                    method="POST",
                    _retry_count=2
                )

                kv = res.get("data", {}).get("key_value_data", {})
                structured_entry = {
                    "index": len(existing_records) + 1,
                    "roll_no": roll,
                    "upazilla": upazilla_name,
                    "district": data.get("district"),
                    "success": res.get("success", False),
                    "status_code": res.get("status_code"),
                    "student_name": res.get("student_name") or kv.get("Name of Student") or kv.get("Student Name"),
                    "father_name": res.get("father_name") or kv.get("Father's Name"),
                    "mother_name": res.get("mother_name") or kv.get("Mother's Name"),
                    "institute": res.get("institute") or kv.get("Name of Institute"),
                    "board": res.get("board", "DINAJPUR"),
                    "group": res.get("group") or kv.get("Group"),
                    "result": res.get("result") or kv.get("Result"),
                    "total_marks": res.get("total_marks") or kv.get("TOTAL MARK"),
                    "subject_grades": res.get("subject_grades", []),
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }

                if res.get("success"):
                    print(f"    ✅ {structured_entry.get('student_name', 'Unknown')} | GPA: {structured_entry.get('result', 'N/A')}")
                else:
                    print(f"    ❌ Not Found (Status {res.get('status_code')})")

                existing_records.append(structured_entry)

                # Webhook streaming if enabled
                if webhook_url:
                    try:
                        import requests
                        requests.post(webhook_url, json=structured_entry, headers={"Bypass-Tunnel-Reminder": "true"}, timeout=2)
                    except Exception:
                        pass

                # Save Upazilla JSON checkpoint
                payload = {
                    "upazilla": upazilla_name,
                    "district": data.get("district"),
                    "summary": {
                        "total_rolls": len(rolls),
                        "scraped_so_far": len(existing_records),
                        "total_success": sum(1 for r in existing_records if r.get("success")),
                        "total_failed": sum(1 for r in existing_records if not r.get("success")),
                        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                    },
                    "records": existing_records
                }

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)

                if delay > 0:
                    time.sleep(delay)

            print(f"\n🎉 Finished Upazilla: {upazilla_name}! Saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="EIIN to Student Results Pipeline by Upazilla")
    parser.add_argument("--eiin", type=str, help="Single EIIN number (e.g. --eiin 125001)")
    parser.add_argument("--eiin-list", nargs="+", help="Multiple EIIN numbers (e.g. --eiin-list 125001 125002 125003)")
    parser.add_argument("--eiin-file", type=str, help="Path to text or JSON file containing EIINs")
    parser.add_argument("--output-dir", type=str, default="upazilla_results", help="Directory to save Upazilla JSON files")
    parser.add_argument("--scrape-students", action="store_true", help="Automatically scrape individual student results after extracting rolls")
    parser.add_argument("--delay", type=float, default=3.2, help="Delay between student requests (default 3.2s for zero penalties)")
    parser.add_argument("--webhook-url", type=str, default="", help="Optional live webhook streaming URL")
    args = parser.parse_args()

    eiins = []
    if args.eiin:
        eiins.append(args.eiin.strip())
    if args.eiin_list:
        eiins.extend([e.strip() for e in args.eiin_list])
    if args.eiin_file:
        if os.path.exists(args.eiin_file):
            with open(args.eiin_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content.startswith("["):
                    eiins.extend([str(x).strip() for x in json.loads(content)])
                else:
                    eiins.extend([l.strip() for l in content.splitlines() if l.strip()])

    if not eiins:
        print("Usage examples:")
        print("  python cli_pipeline.py --eiin 125001")
        print("  python cli_pipeline.py --eiin-list 125001 125002 125003 --scrape-students")
        print("  python cli_pipeline.py --eiin-file eiin_list.txt --scrape-students --output-dir upazilla_results")
        sys.exit(0)

    eiins = list(dict.fromkeys(eiins))
    print(f"[*] Starting EIIN Pipeline for {len(eiins)} Institution(s)...")

    pipeline = InstituteResultPipeline(output_dir=args.output_dir)
    upazilla_groups = pipeline.process_eiins_and_organize_by_upazilla(eiins)

    print("\n=======================================================")
    print("📊 SUMMARY OF EXTRACTED UPAZILLAS & ROLLS:")
    for upz, data in upazilla_groups.items():
        print(f"  • Upazilla: {data['upazilla_name']} ({data['district']})")
        print(f"    - Institutions: {len(data['institutes'])}")
        print(f"    - Total Student Rolls: {data['total_unique_rolls']}")
    print("=======================================================")

    if args.scrape_students:
        pipeline.scrape_and_save_upazilla_students(
            upazilla_groups=upazilla_groups,
            delay=args.delay,
            webhook_url=args.webhook_url or None
        )
    else:
        print("\n💡 Roll extraction complete! To scrape student grades for these rolls, run with --scrape-students")
        print(f"   Or upload the generated Upazilla roll files in '{args.output_dir}/' to GitHub Actions for 40x cloud scraping!")


if __name__ == "__main__":
    main()
