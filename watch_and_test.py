#!/usr/bin/env python3
import sys
import os
import re
import time
import subprocess
import urllib.request
import json

print("=" * 70)
print("👀 Kaggle Hermes Auto-Bridge & 'hi' Verification Watcher")
print("=" * 70)

def detect_url():
    script = '''
    tell application "Safari"
        try
            set pageText to (do JavaScript "document.body.innerText" in current tab of front window)
            return pageText
        on error
            return ""
        end try
    end tell
    '''
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
        matches = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', res.stdout)
        if matches:
            return matches[-1]
    except Exception:
        pass
    return None

def test_hermes(url):
    print(f"\n🔗 Detected Cloudflare Tunnel: {url}")
    print("⚙️ Configuring ~/.hermes/config.yaml ...")
    subprocess.run(["/Users/hritish/.local/bin/kaggle-connect", url])
    
    base_v1 = f"{url.rstrip('/')}/v1"
    print("\n⏳ Testing model availability on Kaggle...")
    for attempt in range(30):
        try:
            req = urllib.request.Request(f"{base_v1}/models")
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status == 200:
                    print("✅ Kaggle model endpoint is healthy!")
                    break
        except Exception:
            time.sleep(2)
            print(".", end="", flush=True)

    print("\n🚀 Sending 'hi' through Hermes Agent via Kaggle model...")
    res = subprocess.run(["/Users/hritish/.local/bin/hermes", "-z", "hi", "-m", "kaggle"], capture_output=True, text=True)
    print("\n" + "=" * 70)
    print("💬 HERMES AGENT REPLY (from Kaggle 2xT4 Qwen-27B):")
    print("=" * 70)
    print(res.stdout)
    if res.stderr:
        print("STDERR:", res.stderr)
    print("=" * 70)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        test_hermes(sys.argv[1])
        sys.exit(0)

    print("🔍 Waiting for Cloudflare URL to appear in your Kaggle notebook...")
    print("👉 (Make sure you pasted the code with Cmd+V into the cell and pressed Shift+Enter)")
    
    url = None
    for i in range(120): # wait up to 6 minutes
        url = detect_url()
        if url:
            break
        time.sleep(3)
        if i % 5 == 0:
            print(f"⏳ Waiting for model server to boot... ({i*3}s)")

    if url:
        test_hermes(url)
    else:
        print("❌ Timed out waiting for URL. If the URL is printed, run:")
        print("   python3 watch_and_test.py https://<your-id>.trycloudflare.com")
