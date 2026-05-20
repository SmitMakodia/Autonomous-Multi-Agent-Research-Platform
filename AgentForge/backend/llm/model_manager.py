import subprocess
import time
import os
import urllib.request
import urllib.error
from config import BASE_DIR

LLAMA_SERVER_EXE = os.path.join(BASE_DIR, "llama.cpp", "build", "bin", "Release", "llama-server.exe")
LLM_MODEL_PATH = os.path.join(BASE_DIR, "models", "Qwen3.5-4B-Q4_K_M.gguf")

class ModelManager:
    def __init__(self):
        self.llm_process = None

    def start_llm(self):
        print("[ModelManager] Starting Qwen LLM server...")
        # Always kill any orphan instances first
        os.system("taskkill /F /IM llama-server.exe /T >nul 2>&1")
        
        cmd = [
            LLAMA_SERVER_EXE,
            "-m", LLM_MODEL_PATH,
            "-ngl", "99",
            "-fa", "on",
            "--ctx-size", "10000",
            "--host", "0.0.0.0",
            "--port", "8000",
            "-np", "1"
        ]
        self.llm_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        for _ in range(45):
            try:
                req = urllib.request.Request("http://127.0.0.1:8000/health")
                with urllib.request.urlopen(req) as response:
                    if response.getcode() == 200:
                        print("[ModelManager] Qwen LLM server is ready.")
                        return
            except Exception:
                time.sleep(1)
        print("[ModelManager] Warning: LLM server might not be ready.")

    def stop_llm(self):
        print("[ModelManager] Stopping Qwen LLM server to free VRAM...")
        if self.llm_process:
            if self.llm_process.poll() is None:
                self.llm_process.terminate()
                try:
                    self.llm_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.llm_process.kill()
            self.llm_process = None
        os.system("taskkill /F /IM llama-server.exe /T >nul 2>&1")

model_manager = ModelManager()