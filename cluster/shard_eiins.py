"""
EIIN Sharder for 5-Node Scraper Cluster
Splits any batch of EIINs into N equal chunks for distributed execution across 5 nodes.
"""

import os
import re
import sys

CLUSTER_DIR = os.path.dirname(os.path.abspath(__file__))
NODES_DIR = os.path.join(CLUSTER_DIR, "nodes")

def parse_eiins(raw_text: str):
    tokens = re.split(r'[\s,;\n\r\t]+', raw_text.strip())
    eiins = [t.strip() for t in tokens if t.strip().isdigit() and len(t.strip()) == 6]
    return list(dict.fromkeys(eiins))

def shard_eiins(eiin_list, num_nodes=5):
    os.makedirs(NODES_DIR, exist_ok=True)
    if not eiin_list:
        print("[!] No valid EIINs provided to shard.")
        return

    k, m = divmod(len(eiin_list), num_nodes)
    chunks = [eiin_list[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(num_nodes)]

    print(f"\n=======================================================")
    print(f"📦 SHARDING {len(eiin_list)} EIINs ACROSS {num_nodes} NODES:")
    print(f"=======================================================")

    for idx, chunk in enumerate(chunks, 1):
        node_dir = os.path.join(NODES_DIR, f"node_{idx}")
        os.makedirs(node_dir, exist_ok=True)
        eiin_file = os.path.join(node_dir, "eiins.txt")
        with open(eiin_file, "w", encoding="utf-8") as f:
            f.write("\n".join(chunk))
        print(f"  • Node {idx} ({node_dir}): {len(chunk)} institutions assigned -> {eiin_file}")

    print(f"=======================================================\n")
    print(f"✓ All {num_nodes} nodes configured! You can now run each node independently or launch all with run_local_cluster.py\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if os.path.isfile(sys.argv[1]):
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                raw = f.read()
        else:
            raw = " ".join(sys.argv[1:])
    else:
        print("\nEnter / Paste EIINs to shard across 5 nodes (press Enter twice to finish):")
        lines = []
        while True:
            try:
                line = input()
                if not line:
                    break
                lines.append(line)
            except EOFError:
                break
        raw = " ".join(lines)

    eiins = parse_eiins(raw)
    shard_eiins(eiins, num_nodes=5)
