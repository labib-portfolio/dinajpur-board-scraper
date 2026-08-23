# 🚀 Bangladesh Education Board Result Scraper 2026

An ultra-fast, concurrent multi-board result scraping engine and interactive CLI designed for high-throughput marksheet and student data extraction from the **Dinajpur Education Board** (`results.dinajpurboard.gov.bd`) and **Chittagong Education Board** (`sresult.bise-ctg.gov.bd`).

```
=======================================================================
   ____  _             _                   ____                      _ 
  |  _ \(_)_ __   __ _(_)_ __  _   _ _ __ | __ )  ___   __ _ _ __ __| |
  | | | | | '_ \ / _` | | '_ \| | | | '__||  _ \ / _ \ / _` | '__/ _` |
  | |_| | | | | | (_| | | |_) | |_| | |   | |_) | (_) | (_| | | | (_| |
  |____/|_|_| |_|\__,_|_| .__/ \__,_|_|   |____/ \___/ \__,_|_|  \__,_|
                        |_|                                            
=======================================================================
```

---

## 🌟 Supported Boards & Engines

| Education Board | Portal Endpoint | Method | Key Features |
| :--- | :--- | :---: | :--- |
| **Dinajpur Board** | `results.dinajpurboard.gov.bd` | GET / Institutional Search | EIIN-based gazette parsing, roll ranges, multi-threaded proxy pool |
| **Chittagong Board** | `sresult.bise-ctg.gov.bd` | Direct POST (`result.php`) | **Zero CAPTCHA**, roll range scanner, full subject-wise marksheets |

---

## 🌟 Key Features

- ⚡ **Ultra-Fast Parallel Engine:** Concurrently scrapes marksheets at speeds exceeding **15+ rolls/sec**.
- 🏢 **Multi-Board Architecture:** Switch seamlessly between **Dinajpur Board** and **Chittagong Board**.
- 🔄 **Automatic Proxy Pool Rotation:** Uses dedicated nodes (`webshare_proxies.txt`) and harvests live public proxies.
- ⏱️ **Real-Time Rolling Speedometer:** Displays instant completion rate (rolls/sec) calculated over an active rolling window.
- 📱 **Mobile & Termux Optimized:** Seamlessly runs on Android with automatic output saving to `/storage/emulated/0/Result Scraper/`.
- 🔁 **100% Result Delivery:** Automatic exponential backoff, circuit-breaker retry on rate limits, and real-time JSON persistence.

---

## 📁 Repository Structure

```tree
.
├── engine/                       # Core Scraping & Parser Modules
│   ├── ctg_scraper.py            # Chittagong Board high-speed engine
│   ├── fast_student_scraper.py   # Dinajpur Board marksheet extractor
│   ├── institute_fetcher.py      # Institute gazette & roll range resolver
│   ├── captcha_solver.py         # Automated arithmetic CAPTCHA solver
│   ├── proxy_manager.py          # Dynamic proxy rotators & connection pools
│   └── parser_utils.py           # HTML-to-JSON structural converter
├── app.py                        # Web UI Dashboard Server (FastAPI / SSE)
├── run.py                        # Multi-Board Interactive Terminal CLI
├── run_ctg.py                    # Dedicated Chittagong Board Terminal CLI
├── webshare_proxies.txt          # Dedicated permanent proxy list
├── working_proxies.txt           # Active verified proxy cache
├── requirements.txt              # Project dependencies
└── README.md                     # Documentation
```

---

## 🚀 Quick Start Guide

### 1. Installation

#### On PC (Windows / Linux / macOS):
```bash
git clone https://github.com/labib-portfolio/dinajpur-board-scraper.git
cd dinajpur-board-scraper
pip install -r requirements.txt
```

#### On Android (Termux):
```bash
pkg update && pkg upgrade -y
pkg install python git -y
git clone https://github.com/labib-portfolio/dinajpur-board-scraper.git
cd dinajpur-board-scraper
pip install -r requirements.txt
termux-setup-storage
```

---

### 2. Running the Interactive CLI Scraper

#### Launch Multi-Board Menu:
```bash
python run.py
```

#### Launch Chittagong Board Directly:
```bash
# Interactive Chittagong CLI
python run_ctg.py

# Or scrape a specific roll range directly:
python run_ctg.py 129000-129050

# Or via run.py with --board ctg:
python run.py --board ctg 129051
```

#### Launch Dinajpur Board Directly:
```bash
python run.py --board dinajpur
```

---

### 3. Running the Web UI Dashboard (Optional)

To start the browser-based dashboard:
```bash
python app.py
```
Open your browser and visit: **`http://127.0.0.1:8000`**

---

## ⚙️ Proxy Configuration

- **Dedicated Proxies:** Add your private proxies (e.g. Webshare) into `webshare_proxies.txt` formatted as `ip:port` or `ip:port:user:pass`.
- **Public Nodes:** The background daemon automatically supplements private proxies with verified `200 OK` public nodes.

---

## 📄 License & Disclaimer

This software is developed strictly for educational, research, and institutional performance analytics purposes.