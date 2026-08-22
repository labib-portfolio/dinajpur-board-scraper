"""
Distributed Cluster Result Aggregator & Merger
Combines results from all node directories into the unified district/upazilla structure and master database.
"""

import os
import glob
import json
import re
import time

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CLUSTER_DIR = os.path.dirname(os.path.abspath(__file__))
NODES_DIR = os.path.join(CLUSTER_DIR, "nodes")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
MASTER_FILE = os.path.join(BASE_DIR, "scraped_results_all.json")

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

def merge_all_nodes():
    print(f"\n=======================================================")
    print(f"🔄 {BOLD}MERGING ALL CLUSTER NODE RESULTS{RESET}")
    print(f"=======================================================\n")

    node_files = glob.glob(os.path.join(NODES_DIR, "node_*", "results", "node_*_results.json"))
    if not node_files:
        print(f"[!] No node result files found in {NODES_DIR}")
        return

    all_scraped_records = {}
    for nf in sorted(node_files):
        try:
            with open(nf, "r", encoding="utf-8") as f:
                data = json.load(f)
                records = data.get("records", [])
                node_id = data.get("summary", {}).get("node_id", "Unknown")
                print(f"  • Reading {os.path.basename(nf)} (Node {node_id}): {len(records)} records")
                for r in records:
                    roll = str(r.get("roll_no"))
                    if roll:
                        all_scraped_records[roll] = r
        except Exception as e:
            print(f"  [!] Error reading {nf}: {e}")

    print(f"\n[*] Total unique records collected across all nodes: {len(all_scraped_records)}")

    # Group into Upazillas
    upazilla_groups = {}
    for r in all_scraped_records.values():
        district = r.get("district") or "UNKNOWN_DISTRICT"
        district_slug = re.sub(r'[^a-zA-Z0-9]+', '_', district.strip().upper()).strip('_')
        upazila = r.get("upazila") or "UNKNOWN_UPAZILLA"
        upz_slug = re.sub(r'[^a-zA-Z0-9]+', '_', upazila.strip().lower()).strip('_')

        key = (district_slug, upz_slug, district, upazila)
        if key not in upazilla_groups:
            upazilla_groups[key] = {}
        upazilla_groups[key][str(r.get("roll_no"))] = r

    os.makedirs(RESULTS_DIR, exist_ok=True)
    saved_files = 0
    for (district_slug, upz_slug, district_name, upz_name), roll_map in upazilla_groups.items():
        district_folder = os.path.join(RESULTS_DIR, district_slug)
        os.makedirs(district_folder, exist_ok=True)
        upz_file = os.path.join(district_folder, f"results_upazilla_{upz_slug}.json")

        existing_data = {"summary": {}, "records": []}
        if os.path.exists(upz_file):
            try:
                with open(upz_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except Exception: pass

        combined_map = {str(item.get("roll_no")): item for item in existing_data.get("records", [])}
        combined_map.update(roll_map)

        all_upz_records = list(combined_map.values())
        for i, rec in enumerate(all_upz_records, 1): rec["index"] = i
        passed_count = sum(1 for item in all_upz_records if "GPA" in str(item.get("result", "")))
        unique_eiins = sorted(list({int(item.get("eiin")) for item in all_upz_records if item.get("eiin")}))

        upz_data = {
            "upazila": upz_name,
            "district": district_name,
            "summary": {
                "total_records": len(all_upz_records),
                "total_passed": passed_count,
                "total_failed": len(all_upz_records) - passed_count,
                "institutions_count": len(unique_eiins),
                "scraped_eiins": unique_eiins,
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "records": all_upz_records
        }

        with open(upz_file, "w", encoding="utf-8") as f:
            json.dump(upz_data, f, indent=2, ensure_ascii=False)
        saved_files += 1

    # Master File
    all_final_records = list(all_scraped_records.values())
    for i, rec in enumerate(all_final_records, 1): rec["index"] = i
    total_passed = sum(1 for item in all_final_records if "GPA" in str(item.get("result", "")))
    master_summary = {
        "total_records": len(all_final_records),
        "total_passed": total_passed,
        "total_failed": len(all_final_records) - total_passed,
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(MASTER_FILE, "w", encoding="utf-8") as f:
        json.dump({"summary": master_summary, "records": all_final_records}, f, indent=2, ensure_ascii=False)

    print(f"\n{GREEN}✓ Successfully merged all node data across {saved_files} Upazilla files and updated {MASTER_FILE}!{RESET}\n")

if __name__ == "__main__":
    merge_all_nodes()
