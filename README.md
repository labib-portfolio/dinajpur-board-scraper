# 🚀 Dinajpur Board Result Scraper 2026

An ultra-fast, concurrent result scraping engine and interactive CLI designed for high-throughput marksheet and student data extraction from the Dinajpur Education Board portal (`results.dinajpurboard.gov.bd`).

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

## 🌟 Key Features

- ⚡ **Ultra-Fast Parallel Engine:** Concurrently scrapes institutional gazettes and individual student marksheets at speeds exceeding **10+ rolls/sec**.
- 🔄 **Background Proxy Refresher:** Continuously monitors, tests, and hot-swaps live proxies from 35+ global endpoints every 3 minutes in the background.
- 🛡️ **Dedicated Proxy Support:** Built-in permanent failover pool (`webshare_proxies.txt`) that stays locked in rotation.
- ⏱️ **Real-Time Rolling Speedometer:** Displays instant completion rate (rolls/sec) calculated over an active 8-second rolling window.
- 📱 **Mobile & Termux Optimized:** Seamlessly runs on Android with automatic output saving to `/storage/emulated/0/Result Scraper/`.
- 🔁 **100% Result Delivery:** Automatic exponential backoff, circuit-breaker retry on HTTP 429 rate limits, and guaranteed student roll extraction.

---

## 📁 Repository Structure

```tree
.
├── engine/                       # Core Scraping & Parser Modules
│   ├── fast_student_scraper.py   # High-speed student marksheet extraction
│   ├── institute_fetcher.py      # Institute gazette & roll range resolver
│   ├── captcha_solver.py         # Automated arithmetic CAPTCHA solver
│   ├── proxy_manager.py          # Dynamic proxy rotators & connection pools
│   └── parser_utils.py           # HTML-to-JSON structural converter
├── app.py                        # Web UI Dashboard Server (Flask / SSE)
├── run.py                        # Standalone Terminal Scraper CLI (Interactive)
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

### 2. Running the Interactive CLI Scraper (Recommended)

To launch the high-speed terminal scraper:
```bash
python run.py
```

1. **Enter EIIN Numbers:** Type or paste one or multiple 6-digit EIINs (comma or space-separated, e.g. `120818, 127500, 121064`).
2. **Proxy Auto-Benchmark:** The scraper verifies dedicated proxies and harvests fresh nodes.
3. **Live Extraction:** Watch real-time institutional progress, live speedometer, and auto-export to JSON.

---

### 3. Running the Web UI Dashboard (Optional)

To start the browser-based dashboard:
```bash
python app.py
```
Open your browser and visit: **`http://127.0.0.1:8000`**

---

## ⚙️ Proxy Configuration

- **Dedicated Proxies:** Add your private proxies (e.g. Webshare) into `webshare_proxies.txt` formatted as `ip:port` or `user:pass@ip:port`.
- **Public Nodes:** The background daemon will automatically supplement private proxies with verified `200 OK` public nodes.

---

## 📄 License
Open source under the MIT License.
