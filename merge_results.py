"""
Merges multiple chunk JSON files into one master scraped_results_all.json.
"""

import os
import sys
import glob
import json

def merge_chunks(chunks_pattern: str = "chunks_output/*.json", output_file: str = "scraped_results_all.json"):
    files = glob.glob(chunks_pattern)
    if not files:
        print(f"[!] No chunk files found matching pattern: {chunks_pattern}")
        return

    print(f"[*] Found {len(files)} chunk files to merge...")
    all_records = []
    total_success = 0

    for fpath in sorted(files):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                records = data.get("records", []) if isinstance(data, dict) else data
                for r in records:
                    all_records.append(r)
                    if r.get("success"):
                        total_success += 1
            print(f"    - Merged {len(records)} records from {fpath}")
        except Exception as e:
            print(f"[!] Error reading {fpath}: {e}")

    # Re-index
    for i, r in enumerate(all_records, 1):
        r["index"] = i

    final_payload = {
        "summary": {
            "total_records": len(all_records),
            "total_success": total_success,
            "total_failed": len(all_records) - total_success,
            "total_chunks_merged": len(files)
        },
        "records": all_records
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_file)) if os.path.dirname(output_file) else ".", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as out_f:
        json.dump(final_payload, out_f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Successfully merged {len(all_records)} total records ({total_success} successful) into: {output_file}")

if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else "chunks_output/*.json"
    output = sys.argv[2] if len(sys.argv) > 2 else "scraped_results_all.json"
    merge_chunks(pattern, output)
