"""
Splits rolls into N chunks for distributed parallel runners (e.g. GitHub Actions matrix).
"""

import json
import os
import sys

def split_rolls_into_chunks(input_file: str, num_chunks: int = 10, output_dir: str = "chunks"):
    with open(input_file, 'r', encoding='utf-8') as f:
        rolls = json.load(f)

    # Standardize list of roll numbers
    roll_list = []
    for item in rolls:
        if isinstance(item, (int, str)):
            roll_list.append(str(item).strip())
        elif isinstance(item, dict):
            r = item.get("roll_no") or item.get("roll") or item.get("id")
            if r:
                roll_list.append(str(r).strip())

    total = len(roll_list)
    os.makedirs(output_dir, exist_ok=True)

    chunk_size = (total + num_chunks - 1) // num_chunks
    created_files = []

    for i in range(num_chunks):
        chunk_data = roll_list[i * chunk_size : (i + 1) * chunk_size]
        if not chunk_data:
            continue
        chunk_file = os.path.join(output_dir, f"chunk_{i}.json")
        with open(chunk_file, 'w', encoding='utf-8') as out_f:
            json.dump(chunk_data, out_f, indent=2)
        created_files.append((chunk_file, len(chunk_data)))

    print(f"[*] Split {total} rolls into {len(created_files)} chunk files in '{output_dir}/':")
    for fname, count in created_files:
        print(f"    - {fname}: {count} rolls")

if __name__ == "__main__":
    input_path = r"C:\Users\labib_n4\Downloads\rolls.json"
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    chunks = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    split_rolls_into_chunks(input_path, chunks)
