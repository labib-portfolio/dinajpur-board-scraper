import asyncio
import aiohttp
import re
import time
import os
import sys
import logging

logging.getLogger("asyncio").setLevel(logging.CRITICAL)

PROXY_SOURCES = [
    # Fast APIs
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,https&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://api.openproxylist.xyz/http.txt",
    "https://proxyspace.pro/http.txt",
    "https://proxyspace.pro/https.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/master/proxy_files/http_proxies.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/master/proxy_files/https_proxies.txt",
    
    # Active GitHub Repositories (HTTP / HTTPS / SOCKS)
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/https.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/https.txt",
    "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt",
    "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_all.txt",
    "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_ssl.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master-List/main/http.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/https.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https/https.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
    "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/http/global/http_checked.txt",
    "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/http.txt",
    "https://raw.githubusercontent.com/andigwandi/free-proxy/main/proxy_list.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/https.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
    "https://raw.githubusercontent.com/casals-ar/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/casals-ar/proxy-list/main/https.txt",
    "https://raw.githubusercontent.com/ObcbO/getproxy/master/http.txt",
    "https://raw.githubusercontent.com/ObcbO/getproxy/master/https.txt",
    "https://raw.githubusercontent.com/B4RC0D3-UA/proxy-list/main/HTTP.txt",
    "https://raw.githubusercontent.com/B4RC0D3-UA/proxy-list/main/HTTPS.txt",
    "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/https.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/https.txt",
    "https://raw.githubusercontent.com/yemix-is/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/yemix-is/proxy-list/main/proxies/https.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/https.txt",
    "https://raw.githubusercontent.com/saisuiu/Lion-proxies/main/http.txt",
    "https://raw.githubusercontent.com/saisuiu/Lion-proxies/main/https.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/almroot/proxylist/master/list.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
    "https://raw.githubusercontent.com/im-notify/free-proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/im-notify/free-proxy-list/main/proxies/https.txt",
    "https://raw.githubusercontent.com/yuc0/free-proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/yuc0/free-proxy-list/main/https.txt",
    "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
    "https://raw.githubusercontent.com/hanwaytech/free-proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/hanwaytech/free-proxy-list/main/https.txt"
]

TARGET_ENDPOINT = (
    "https://results.dinajpurboard.gov.bd/fast/student"
    "?roll=217305&exam=1"
    "&exp=1787224774"
    "&t=769debce061f8471859fb4cd1069e0454aae3b18294e70c8454edd2fc416320a"
)

async def fetch_source(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
            if resp.status == 200:
                text = await resp.text()
                return re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b", text)
    except Exception:
        pass
    return []

async def check_proxy_node(session, proxy, working_list, sem, needed=120, silent=True, max_latency=4.0):
    if len(working_list) >= needed:
        return
    async with sem:
        if len(working_list) >= needed:
            return
        proxy_url = f"http://{proxy}"
        t_start = time.time()
        try:
            timeout = aiohttp.ClientTimeout(total=max_latency)
            async with session.get(TARGET_ENDPOINT, proxy=proxy_url, timeout=timeout) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    if "Student Result" in text:
                        elapsed = time.time() - t_start
                        working_list.append((proxy, elapsed))
                        if not silent:
                            print(f"  [+] ⚡ Live Proxy ({int(elapsed*1000)}ms): {proxy} (Total: {len(working_list)})")
        except Exception:
            pass

async def harvest_and_verify_proxies(needed=120, max_candidates=35000, silent=True, max_latency=4.0):
    try:
        loop = asyncio.get_running_loop()
        def silence_sock_reset(loop, context):
            exc = context.get("exception")
            if isinstance(exc, (ConnectionResetError, OSError, ConnectionAbortedError)):
                return
            try:
                loop.default_exception_handler(context)
            except Exception:
                pass
        loop.set_exception_handler(silence_sock_reset)
    except Exception:
        pass

    existing_proxies = []
    cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "working_proxies.txt")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                existing_proxies = [line.strip() for line in f if ":" in line.strip()]
        except Exception:
            pass

    t0 = time.time()
    connector = aiohttp.TCPConnector(ssl=False, limit=400)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_source(session, url) for url in PROXY_SOURCES]
        results = await asyncio.gather(*tasks)
        all_proxies = list(dict.fromkeys(existing_proxies + [ip for sublist in results for ip in sublist]))

        sem = asyncio.Semaphore(300)
        working_proxies = []
        check_tasks = [
            check_proxy_node(session, p, working_proxies, sem, needed=needed, silent=silent, max_latency=max_latency)
            for p in all_proxies[:max_candidates]
        ]
        await asyncio.gather(*check_tasks)
        
        # Sort by fastest latency first
        working_proxies.sort(key=lambda x: x[1])
        return [p for p, _ in working_proxies]

if __name__ == "__main__":
    live_proxies = asyncio.run(harvest_and_verify_proxies(needed=120, max_candidates=35000, silent=False, max_latency=4.0))
    cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "working_proxies.txt")
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write("\n".join(live_proxies))
    print(f"\nSaved {len(live_proxies)} live proxies to working_proxies.txt (sorted fastest-first)")
