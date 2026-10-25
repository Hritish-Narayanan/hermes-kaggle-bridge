# ⚡ Hermes Kaggle Bridge (2xT4 Multi-GPU + Auto-Watchdog)

Run large open-weights models (`cyjin-yl/Qwen3.8-27B-Uncensored-Cyber-agentic-imatrix-GGUF`) across **2 x Tesla T4 GPUs** on Kaggle's free compute tier and connect them directly to your local **Hermes Agent**.

---

## 🚀 1-Line Run on ANY Kaggle Account

In any Kaggle notebook, set:
- **Accelerator:** `GPU T4 x2`
- **Internet:** `On`
- **Persistence:** `Variables and Files`

Then run this single line in a cell:

```python
!rm -rf /tmp/bridge && git clone https://github.com/Hritish-Narayanan/hermes-kaggle-bridge.git /tmp/bridge && bash /tmp/bridge/start.sh
```

---

## 🎯 How It Works

1. **Hardware Detection:** Automatically checks dual Tesla T4 GPUs (32 GB total VRAM).
2. **Persistence Cache:** Saves the 15 GB GGUF model in `/kaggle/working`. On session restarts, it reuses the file instantly without re-downloading.
3. **Multi-GPU Parallelism:** Runs Ollama across both GPUs, supporting up to 16,384 context tokens.
4. **Cloudflare Quick Tunnel:** Creates an instant HTTPS endpoint with zero configuration or auth tokens.
5. **Idle Watchdog (Quota Protection):** Automatically shuts down the kernel if idle for 30 minutes so you never burn your free 30-hour weekly quota.
6. **Remote Shutdown:** Stop the remote VM from your Mac anytime with:
   ```bash
   kaggle-connect stop
   ```

---

## 🔗 Connect Local Hermes

Once the server outputs the Cloudflare URL, run:

```bash
kaggle-connect <tunnel_url>
```

Or simply run without arguments to auto-detect from your active Safari tab:

```bash
kaggle-connect
```

Then chat with Hermes:

```bash
hermes -m kaggle
```

---

## 🐳 Docker Deployment (RunPod, Vast.ai, Modal, Local GPU)

```bash
docker compose up -d
```
