# ==============================================================================
#  ⚡ KAGGLE 2xT4 GPU INFERENCE SERVER FOR HERMES AGENT
#  Model: cyjin-yl/Qwen3.8-27B-Uncensored-Cyber-agentic-imatrix-GGUF
#  Quant: Qwen3.8-27B-Uncensored-Cyber-IQ4_XS-imatrix-fromq8.gguf (14.96 GB)
#  Hardware: 2 x Tesla T4 (32 GB total VRAM)
#  Auto-Shutdown Watchdog: Enabled (Shuts down kernel on idle to save quota)
# ==============================================================================

import os
import sys
import time
import subprocess
import threading
import json
import re
from urllib.request import urlopen, Request
import urllib.error

# --- Configuration ---
MODEL_REPO = "cyjin-yl/Qwen3.8-27B-Uncensored-Cyber-agentic-imatrix-GGUF"
MODEL_FILE = "Qwen3.8-27B-Uncensored-Cyber-IQ4_XS-imatrix-fromq8.gguf"
WORKING_DIR = "/kaggle/working" if os.path.exists("/kaggle") else os.getcwd()
MODEL_PATH = os.path.join(WORKING_DIR, MODEL_FILE)
MODEL_NAME = "kaggle"
PROXY_PORT = 8000
OLLAMA_PORT = 11434
IDLE_TIMEOUT_MINUTES = int(os.environ.get("IDLE_TIMEOUT", 30))

# Optional GitHub Gist auto-sync
GIST_ID = os.environ.get("GIST_ID", "bcf6eb4fb00d9441d4655741c3decb13")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

print("=" * 70)
print("🚀 Starting Kaggle 2xT4 Model Server for Hermes...")
print("=" * 70)

# 1. Verify GPUs
print("\n[1/6] 🔍 Checking GPU availability...")
try:
    smi = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], text=True)
    print(smi.strip())
except Exception as e:
    print("⚠️ Warning running nvidia-smi:", e)

# 2. Install Cloudflared (Tunneling)
print("\n[2/6] 🌐 Installing Cloudflare tunnel (cloudflared)...")
if not os.path.exists("/usr/local/bin/cloudflared"):
    cmd = "curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared"
    os.system(cmd)
print("✅ cloudflared is ready.")

# 3. Check / Download Model File with Persistence
print("\n[3/6] 📦 Checking Model File in working directory...")
if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 10 * 1024**3:
    size_gb = os.path.getsize(MODEL_PATH) / (1024**3)
    print(f"✅ Model already exists ({size_gb:.2f} GB)! Reusing from persistence.")
else:
    print(f"📥 Downloading {MODEL_FILE} from Hugging Face ({MODEL_REPO})...")
    print("⚡ Using huggingface_hub with fast download...")
    from huggingface_hub import hf_hub_download
    downloaded_path = hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILE,
        local_dir=WORKING_DIR,
        local_dir_use_symlinks=False
    )
    size_gb = os.path.getsize(MODEL_PATH) / (1024**3)
    print(f"✅ Download complete: {MODEL_PATH} ({size_gb:.2f} GB)")

# 4. Install & Start Ollama Engine
print("\n[4/6] 🦙 Setting up Ollama Engine (2xT4 Multi-GPU)...")
if not os.path.exists("/usr/local/bin/ollama"):
    os.system("apt-get update -qq && apt-get install -y -qq zstd")
    os.system("curl -fsSL https://ollama.com/install.sh | sh")

# Start Ollama daemon in background
os.environ["OLLAMA_HOST"] = f"127.0.0.1:{OLLAMA_PORT}"
os.environ["OLLAMA_NUM_PARALLEL"] = "2"
os.environ["OLLAMA_KEEP_ALIVE"] = "15m"

subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("⏳ Waiting for Ollama service...")
for _ in range(20):
    try:
        with urlopen(f"http://127.0.0.1:{OLLAMA_PORT}/api/tags", timeout=2) as r:
            if r.status == 200:
                break
    except Exception:
        time.sleep(1)

# Create Modelfile for Qwen 27B GGUF
modelfile_path = os.path.join(WORKING_DIR, "Modelfile")
modelfile_content = f"""
FROM {MODEL_PATH}
PARAMETER num_ctx 65536
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
"""
with open(modelfile_path, "w") as f:
    f.write(modelfile_content)

print(f"🔨 Registering model '{MODEL_NAME}' in Ollama...")
os.system(f"ollama create {MODEL_NAME} -f {modelfile_path}")
print(f"✅ Model '{MODEL_NAME}' created successfully.")

# 5. Start Watchdog & Reverse Proxy
# Tracks last request time for idle auto-shutdown & handles /shutdown
print("\n[5/6] 🛡️ Starting Compute Quota Watchdog & Proxy...")
last_request_time = time.time()
session_start_time = time.time()

def shutdown_kaggle():
    print("\n🛑 SHUTDOWN TRIGGERED: Halting kernel to stop compute billing!")
    os.system("pkill -9 cloudflared")
    os.system("pkill -9 ollama")
    time.sleep(1)
    os._exit(0)

def idle_watchdog_thread():
    global last_request_time
    timeout_sec = IDLE_TIMEOUT_MINUTES * 60
    while True:
        time.sleep(30)
        idle_elapsed = time.time() - last_request_time
        if idle_elapsed > timeout_sec:
            print(f"\n⏰ IDLE WATCHDOG: No requests received in {IDLE_TIMEOUT_MINUTES} minutes.")
            print("🛑 Stopping session automatically to preserve your quota!")
            shutdown_kaggle()

threading.Thread(target=idle_watchdog_thread, daemon=True).start()

# Lightweight HTTP Proxy with SSE streaming support & shutdown hook
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.request

class WatchdogProxy(BaseHTTPRequestHandler):
    def do_GET(self):
        global last_request_time
        last_request_time = time.time()
        
        if self.path == "/status" or self.path == "/":
            uptime_min = (time.time() - session_start_time) / 60
            idle_min = (time.time() - last_request_time) / 60
            status_data = {
                "status": "online",
                "model": MODEL_NAME,
                "uptime_minutes": round(uptime_min, 1),
                "idle_minutes": round(idle_min, 1),
                "idle_timeout_minutes": IDLE_TIMEOUT_MINUTES,
                "target": f"http://127.0.0.1:{OLLAMA_PORT}"
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status_data, indent=2).encode())
            return
            
        self.forward_request("GET")

    def do_POST(self):
        global last_request_time
        last_request_time = time.time()

        if self.path == "/shutdown" or self.path == "/v1/shutdown":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "shutting_down", "message": "Kernel stopped."}\n')
            threading.Thread(target=lambda: (time.sleep(1), shutdown_kaggle()), daemon=True).start()
            return

        self.forward_request("POST")

    def forward_request(self, method):
        target_url = f"http://127.0.0.1:{OLLAMA_PORT}{self.path}"
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len) if content_len > 0 else None
        
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ['host', 'content-length']}
        
        req = urllib.request.Request(target_url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                for h, v in resp.getheaders():
                    if h.lower() not in ['transfer-encoding', 'content-length']:
                        self.send_header(h, v)
                self.end_headers()
                
                while True:
                    chunk = resp.read(1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # Client (Hermes / Cloudflare) disconnected, canceled stream, or timed out
            return
        except urllib.error.HTTPError as e:
            try:
                self.send_response(e.code)
                self.end_headers()
                self.wfile.write(e.read())
            except (BrokenPipeError, ConnectionResetError):
                pass
        except Exception as e:
            try:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
            except (BrokenPipeError, ConnectionResetError):
                pass

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        pass

server = ThreadingHTTPServer(("0.0.0.0", PROXY_PORT), WatchdogProxy)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(f"✅ Watchdog proxy active on port {PROXY_PORT}")

# 6. Start Cloudflare Tunnel
print("\n[6/6] 🌍 Launching Cloudflare Tunnel...")
tunnel_proc = subprocess.Popen(
    ["/usr/local/bin/cloudflared", "tunnel", "--url", f"http://127.0.0.1:{PROXY_PORT}", "--no-autoupdate"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

tunnel_url = None
for line in iter(tunnel_proc.stdout.readline, ''):
    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
    if match:
        tunnel_url = match.group(0)
        break

if not tunnel_url:
    print("❌ Failed to obtain Cloudflare tunnel URL.")
    sys.exit(1)

# Update Gist if credentials present
if GIST_ID and GITHUB_TOKEN:
    try:
        gist_payload = json.dumps({
            "files": {
                "endpoint.json": {
                    "content": json.dumps({
                        "endpoint": f"{tunnel_url}/v1",
                        "model": MODEL_NAME,
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                    })
                }
            }
        }).encode('utf-8')
        g_req = Request(f"https://api.github.com/gists/{GIST_ID}", data=gist_payload, headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Hermes-Kaggle-Bridge"
        }, method="PATCH")
        with urlopen(g_req, timeout=5) as resp:
            print("📡 Live endpoint automatically synced to GitHub Gist!")
    except Exception as e:
        print("⚠️ Could not sync to GitHub Gist:", e)

print("\n" + "=" * 70)
print("🎉 KAGGLE INFERENCE SERVER IS LIVE!")
print("=" * 70)
print(f"🌐 PUBLIC ENDPOINT : {tunnel_url}/v1")
print(f"🤖 MODEL NAME      : {MODEL_NAME}")
print("⚡ COMPUTE HARDWARE: 2 x Tesla T4 (32 GB VRAM)")
print(f"⏰ IDLE WATCHDOG   : Auto-shutdown in {IDLE_TIMEOUT_MINUTES} minutes if unused")
print("=" * 70)
print("👉 ON YOUR LOCAL MAC, RUN THIS COMMAND TO CONNECT HERMES:")
print(f"   kaggle-connect {tunnel_url}")
print("=" * 70)
print(f"🛑 TO STOP THIS SESSION REMOTELY AND SAVE COMPUTE QUOTA:")
print(f"   kaggle-connect stop")
print("=" * 70 + "\n")

# Keep the main process alive
try:
    while True:
        time.sleep(10)
except KeyboardInterrupt:
    shutdown_kaggle()
