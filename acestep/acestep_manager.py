import subprocess
import time
import requests
import os
import signal
import psutil

ACESTEP_DIR = r"D:\CODE\Python\Projects\AceStep"
ACESTEP_URL = "http://127.0.0.1:7860"


def is_acestep_running():
    try:
        requests.get(ACESTEP_URL, timeout=2)
        return True
    except requests.RequestException:
        return False


def kill_existing_acestep():
    print("🧹 Checking for existing AceStep processes...")

    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info["cmdline"]
            if cmdline and any("acestep" in str(c).lower() for c in cmdline):
                print(f"⚠️ Killing existing AceStep process (PID: {proc.pid})")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue


def start_acestep():
    print("🚀 Starting AceStep server...")

    if is_acestep_running():
        print("⚡ AceStep already running, Killing it.")
        kill_existing_acestep()
        return None  # IMPORTANT: we didn't start it

    try:
        proc = subprocess.Popen(
            ["uv", "run", "acestep"],
            cwd=ACESTEP_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except FileNotFoundError:
        raise RuntimeError("❌ 'uv' not found. Make sure it is installed and in PATH.")

    # Wait for server
    for _ in range(120):
        if is_acestep_running():
            print("✅ AceStep server ready")
            time.sleep(8)  # warmup
            return proc
        time.sleep(1)

    proc.kill()
    raise RuntimeError("❌ AceStep failed to start")


def stop_acestep(proc):
    if proc is None:
        print("⚡ Skipping stop (server was already running)")
        return

    print("🛑 Stopping AceStep...")

    try:
        proc.terminate()
        proc.wait(timeout=10)
        print("✅ Stopped gracefully")
    except subprocess.TimeoutExpired:
        print("💀 Force killing...")
        proc.kill()