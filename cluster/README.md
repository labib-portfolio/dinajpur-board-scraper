# 🚀 5-Node Distributed Scraper Cluster (100 Workers)

This directory provides a multi-node scraping cluster capable of scraping **60–80 rolls/second (~4,500 rolls/minute)** across 5 parallel nodes.

---

## 📁 Directory Structure:

```text
cluster/
├── shard_eiins.py         # Splits any EIIN list into 5 node chunks
├── node_worker.py         # Autonomous 20-worker scraping engine for each node
├── run_local_cluster.py   # Spawns all 5 nodes concurrently on your machine
├── merge_nodes.py         # Combines all node results into your master database
└── nodes/
    ├── node_1/eiins.txt
    ├── node_2/eiins.txt
    ├── node_3/eiins.txt
    ├── node_4/eiins.txt
    └── node_5/eiins.txt
```

---

## ⚡ How to Use in 3 Simple Steps:

### Step 1: Shard Your EIINs
Paste your entire list of 50, 100, or 500 EIINs:
```bash
python cluster/shard_eiins.py
```
*(This automatically splits the workload evenly into `nodes/node_1` through `nodes/node_5`)*

---

### Step 2: Run the Cluster

#### Option A: Run all 5 nodes automatically on your local machine:
```bash
python cluster/run_local_cluster.py
```

#### Option B: Run on 5 different terminals, machines, or repos:
* **Terminal/Node 1:** `python cluster/node_worker.py --node 1`
* **Terminal/Node 2:** `python cluster/node_worker.py --node 2`
* **Terminal/Node 3:** `python cluster/node_worker.py --node 3`
* **Terminal/Node 4:** `python cluster/node_worker.py --node 4`
* **Terminal/Node 5:** `python cluster/node_worker.py --node 5`

---

### Step 3: Merge Results
Merge all 5 node results back into your main `results/` hierarchy and `scraped_results_all.json` in 1 second:
```bash
python cluster/merge_nodes.py
```
