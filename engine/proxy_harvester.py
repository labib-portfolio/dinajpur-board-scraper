"""
High-Performance Dynamic Proxy Harvester & Validation Engine
Prioritizes dedicated Webshare proxies, with automatic fallback to verified public proxy sources.
Features non-blocking background auto-refill when pool size drops below threshold.
"""

import os
import re
import sys
import time
import random
import logging
import threading
from typing import List, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PUBLIC_PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,https&timeout=8000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt"
]

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
RESET = "\033[0m"


class SmartProxyPool:
    def __init__(self, validation_url: str = "https://sresult.bise-ctg.gov.bd/to_ssc_26_ctg/individual/"):
        self.validation_url = validation_url
        self.proxies: List[str] = []
        self.lock = threading.Lock()
        self._is_fetching = False
        self.min_pool_size = 15
        self.max_candidates = 250
        self.validation_timeout = 4.5
        self.validation_workers = 40
        self.load_local_proxies()

    def load_local_proxies(self) -> int:
        """Loads proxies from webshare_proxies.txt or local proxy file."""
        local_file = os.path.join(BASE_DIR, "webshare_proxies.txt")
        loaded = []
        if os.path.exists(local_file):
            try:
                with open(local_file, "r", encoding="utf-8") as f:
                    for line in f:
                        l = line.strip()
                        if l and not l.startswith("#") and ":" in l:
                            loaded.append(l)
            except Exception:
                pass
        with self.lock:
            for p in loaded:
                if p not in self.proxies:
                    self.proxies.append(p)
        return len(loaded)

    def fetch_public_proxies(self, target_count: int = 30) -> List[str]:
        """Fetches and validates fresh public proxies from multiple reliable endpoints."""
        with self.lock:
            if self._is_fetching:
                return []
            self._is_fetching = True

        try:
            candidates: Set[str] = set()
            sys.stdout.write(f"{DIM}\n[ProxyHarvester] Fetching fresh proxies from public mirror pools...{RESET}\n")
            sys.stdout.flush()

            def harvest_source(url: str):
                try:
                    resp = requests.get(url, timeout=7)
                    if resp.status_code == 200:
                        lines = resp.text.splitlines()
                        for line in lines:
                            l = line.strip()
                            if l and not l.startswith("#"):
                                if re.match(r'^\d{1,3}(\.\d{1,3}){3}:\d+$', l):
                                    candidates.add(l)
                except Exception:
                    pass

            with ThreadPoolExecutor(max_workers=len(PUBLIC_PROXY_SOURCES)) as harvester_pool:
                list(harvester_pool.map(harvest_source, PUBLIC_PROXY_SOURCES))

            cand_list = list(candidates)
            random.shuffle(cand_list)
            cand_list = cand_list[:self.max_candidates]

            if not cand_list:
                return []

            valid_proxies = []

            def validate_candidate(proxy_str: str) -> Optional[str]:
                parts = proxy_str.split(":")
                if len(parts) == 4:
                    ip, port, user, pwd = parts
                    proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
                else:
                    proxy_url = f"http://{proxy_str}"

                proxies = {"http": proxy_url, "https": proxy_url}
                try:
                    s = requests.Session()
                    r = s.get(self.validation_url, proxies=proxies, timeout=self.validation_timeout)
                    if r.status_code == 200:
                        return proxy_str
                except Exception:
                    pass
                return None

            with ThreadPoolExecutor(max_workers=self.validation_workers) as validator_pool:
                futures = [validator_pool.submit(validate_candidate, p) for p in cand_list]
                for fut in as_completed(futures):
                    res = fut.result()
                    if res:
                        valid_proxies.append(res)
                        if len(valid_proxies) >= target_count:
                            break

            with self.lock:
                for vp in valid_proxies:
                    if vp not in self.proxies:
                        self.proxies.append(vp)

            sys.stdout.write(f"{GREEN}✓ [ProxyHarvester] Added {len(valid_proxies)} verified active nodes to rotation!{RESET}\n")
            sys.stdout.flush()
            return valid_proxies
        finally:
            with self.lock:
                self._is_fetching = False

    def get_all(self) -> List[str]:
        with self.lock:
            if not self.proxies:
                self.load_local_proxies()
            return list(self.proxies)

    def ensure_pool(self, min_size: int = 20) -> List[str]:
        """Ensures at least min_size proxies are available, harvesting if needed."""
        self.load_local_proxies()
        with self.lock:
            cur_len = len(self.proxies)
        if cur_len < min_size:
            self.fetch_public_proxies(target_count=min_size - cur_len + 10)
        return self.get_all()

    def remove_proxy(self, proxy_str: str):
        with self.lock:
            if proxy_str in self.proxies:
                self.proxies.remove(proxy_str)
                if len(self.proxies) < self.min_pool_size and not self._is_fetching:
                    threading.Thread(target=self.fetch_public_proxies, daemon=True).start()
