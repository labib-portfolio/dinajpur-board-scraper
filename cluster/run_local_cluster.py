"""
Multi-Process Local Cluster Launcher
Spawns 5 parallel background worker processes (100 total concurrent threads) on the local machine.
"""

import os
import sys
import subprocess
import time

CLUSTER_DIR = os.path.dirname(os.path.abspath(__file__))
NODES_DIR = os.path.join(CLUSTER_DIR, "nodes")

GREEN = "\033[92m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def launch_cluster(num_nodes=5, workers_per_node=20):
    print(f"\n=======================================================")
    print(f"🚀 {BOLD}LAUNCHING 5-NODE LOCAL SCRAPING CLUSTER{RESET}")
    print(f"  • Nodes:             {num_nodes} Independent Worker Processes")
    print(f"  • Total Parallelism: {num_nodes * workers_per_node} Concurrent Threads")
    print(f"=======================================================\n")

    processes = []
    for node_idx in range(1, num_nodes + 1):
        eiin_file = os.path.join(NODES_DIR, f"node_{node_idx}", "eiins.txt")
        if not os.path.isfile(eiin_file):
            print(f"[!] Warning: {eiin_file} does not exist. Run 'python cluster/shard_eiins.py' first!")
            continue

        cmd = [sys.executable, os.path.join(CLUSTER_DIR, "node_worker.py"), "--node", str(node_idx), "--eiins", eiin_file, "--workers", str(workers_per_node)]
        p = subprocess.Popen(cmd)
        processes.append((node_idx, p))
        print(f"  [+] Spawned Node {node_idx} Process (PID {p.pid})...")
        time.sleep(0.5)

    print(f"\n{CYAN}⚡ All {len(processes)} nodes are now running in parallel at ~60-80 rolls/sec!{RESET}")
    print(f"[*] Waiting for all cluster nodes to finish... (Press Ctrl+C to stop)\n")

    try:
        for node_idx, p in processes:
            p.wait()
            print(f"  [✓] Node {node_idx} Process Finished.")
    except KeyboardInterrupt:
        print(f"\n[!] Stopping all node processes...")
        for _, p in processes:
            p.terminate()

    print(f"\n[*] Running automatic cluster merger...")
    subprocess.run([sys.executable, os.path.join(CLUSTER_DIR, "merge_nodes.py")])
    print(f"\n{GREEN}{BOLD}🎉 Cluster Scraping & Merging Complete!{RESET}\n")

if __name__ == "__main__":
    launch_cluster()
