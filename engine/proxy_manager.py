import asyncio
import aiohttp
import re
import time
import os

PROXY_SOURCES = [
    # Fast APIs
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,https&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://api.openproxylist.xyz/http.txt",
    
    # Active GitHub Repositories (HTTP / HTTPS)
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
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
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/master/proxy_files/http_proxies.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/master/proxy_files/https_proxies.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https/https.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
    "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/http/global/http_checked.txt",
    "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/http.txt",
    "https://raw.githubusercontent.com/andigwandi/free-proxy/main/proxy_list.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/https.txt"
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

async def check_proxy_node(session, proxy, working_list, sem, needed=30):
    if len(working_list) >= needed:
        return
    async with sem:
        if len(working_list) >= needed:
            return
        proxy_url = f"http://{proxy}"
        try:
            timeout = aiohttp.ClientTimeout(total=3.5)
            async with session.get(TARGET_ENDPOINT, proxy=proxy_url, timeout=timeout) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    if "Student Result" in text:
                        working_list.append(proxy)
                        print(f"  [+] Active Dinajpur Proxy: {proxy} (Total: {len(working_list)})")
        except Exception:
            pass

async def harvest_and_verify_proxies(needed=30, max_candidates=250):
    t0 = time.time()
    connector = aiohttp.TCPConnector(ssl=False, limit=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        print(f"Harvesting raw proxies from {len(PROXY_SOURCES)} sources...")
        tasks = [fetch_source(session, url) for url in PROXY_SOURCES]
        results = await asyncio.gather(*tasks)
        all_proxies = list(dict.fromkeys(ip for sublist in results for ip in sublist))
        print(f"Harvested {len(all_proxies)} unique candidate proxies in {time.time()-t0:.2f}s.")

        print(f"Testing responsiveness directly on Dinajpur Board target...")
        sem = asyncio.Semaphore(150)
        working_proxies = []
        check_tasks = [
            check_proxy_node(session, p, working_proxies, sem, needed=needed)
            for p in all_proxies[:max_candidates]
        ]
        await asyncio.gather(*check_tasks)
        
        print(f"Verification complete: {len(working_proxies)} live proxies ready in {time.time()-t0:.2f}s!")
        return working_proxies

if __name__ == "__main__":
    live_proxies = asyncio.run(harvest_and_verify_proxies(needed=25))
    with open("working_proxies.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(live_proxies))
    print("Saved to working_proxies.txt")
