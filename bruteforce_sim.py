# bruteforce.py
"""
Brute-force simulator (safe): ONLY targets localhost.
Usage example:
python bruteforce.py --url http://127.0.0.1:5000/login --username admin --wordlist wordlist.txt --threads 4 --delay 0.2
"""

import argparse
import requests
from urllib.parse import urlparse
import threading
import time
from queue import Queue
import sys

def is_localhost(url):
    p = urlparse(url)
    host = p.hostname
    # allow localhost addresses only
    return host in ("127.0.0.1", "localhost", "::1")

def worker(q, stop_event, args, session, tried_lock, tried_set):
    while not q.empty() and not stop_event.is_set():
        pw = q.get()
        with tried_lock:
            if pw in tried_set:
                q.task_done()
                continue
            tried_set.add(pw)
        try:
            if stop_event.is_set():
                q.task_done()
                break
            resp = session.post(args.url, data={"username": args.username, "password": pw}, timeout=6)
        except requests.RequestException as e:
            print(f"[!] request error for '{pw}': {e}")
            q.task_done()
            time.sleep(args.delay)
            continue

        # handle responses
        if resp.status_code == 429:
            print("[!] Server rate-limited (429). Backing off a bit...")
            time.sleep(max(1.0, args.delay * 5))
            q.put(pw)  # requeue this password later
        else:
            # Try to detect success using JSON or text heuristics
            success = False
            try:
                j = resp.json()
                if j.get("result") == "success":
                    success = True
            except Exception:
                if "welcome" in resp.text.lower() or "success" in resp.text.lower():
                    success = True

            if success:
                print(f"[+] PASSWORD FOUND: {pw}")
                with open("found.txt", "w") as f:
                    f.write(pw + "\n")
                stop_event.set()
                q.task_done()
                break
            else:
                print(f"[-] tried: {pw} (status {resp.status_code})")

        q.task_done()
        time.sleep(args.delay)

def main():
    parser = argparse.ArgumentParser(description="Safe brute-force simulator (localhost only)")
    parser.add_argument("--url", required=True, help="Target login URL (must be localhost)")
    parser.add_argument("--username", required=True)
    parser.add_argument("--wordlist", required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between attempts per worker (seconds)")
    args = parser.parse_args()

    if not is_localhost(args.url):
        print("ERROR: This tool only runs against localhost addresses for safety. Set --url to http://127.0.0.1:5000/login")
        sys.exit(1)

    # load wordlist
    with open(args.wordlist, "r", encoding="utf-8", errors="ignore") as f:
        words = [line.strip() for line in f if line.strip()]

    q = Queue()
    for w in words:
        q.put(w)

    stop_event = threading.Event()
    tried_lock = threading.Lock()
    tried_set = set()

    session = requests.Session()
    workers = []
    for i in range(args.threads):
        t = threading.Thread(target=worker, args=(q, stop_event, args, session, tried_lock, tried_set), daemon=True)
        t.start()
        workers.append(t)

    try:
        # wait until queue empty or password found
        while any(t.is_alive() for t in workers):
            if stop_event.is_set():
                break
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("[*] Interrupted by user. Stopping...")
        stop_event.set()

    # ensure all done
    for t in workers:
        t.join(timeout=1)

    if stop_event.is_set():
        print("[*] Done: password found (check found.txt).")
    else:
        print("[*] Finished: no password found in wordlist.")

if __name__ == "__main__":
    main()
