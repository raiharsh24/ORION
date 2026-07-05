import time
import asyncio
import aiohttp
import subprocess
import os
import sys
import glob

def calculate_percentile(data, percentile):
    if not data:
        return 0
    sorted_data = sorted(data)
    index = (len(sorted_data) - 1) * (percentile / 100.0)
    floor = int(index)
    ceil = floor + 1
    if ceil < len(sorted_data):
        return sorted_data[floor] + (sorted_data[ceil] - sorted_data[floor]) * (index - floor)
    return sorted_data[floor]

async def run_concurrency_test(url, concurrency_levels):
    print("\n--- Starting Concurrency & Latency Stress Tests ---")
    results = {}
    
    for level in concurrency_levels:
        print(f"Testing {level} concurrent requests...")
        latencies = []
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i in range(level):
                payload = {"prompt": f"Stress test query {i}", "confirmed": False}
                tasks.append(send_request(session, url, payload))
            
            start_time = time.time()
            responses = await asyncio.gather(*tasks)
            duration = (time.time() - start_time) * 1000
            
            for res in responses:
                if res is not None:
                    latencies.append(res)
            
            if latencies:
                p50 = calculate_percentile(latencies, 50)
                p95 = calculate_percentile(latencies, 95)
                p99 = calculate_percentile(latencies, 99)
                results[level] = {
                    "p50": p50,
                    "p95": p95,
                    "p99": p99,
                    "duration_ms": duration,
                    "success_rate": (len(latencies) / level) * 100
                }
                print(f"  Level {level} -> P50: {p50:.2f}ms, P95: {p95:.2f}ms, P99: {p99:.2f}ms, Success Rate: {results[level]['success_rate']:.2f}%")
            else:
                print(f"  Level {level} -> All requests failed!")
                
    return results

async def send_request(session, url, payload):
    start = time.time()
    try:
        async with session.post(url, json=payload, timeout=10.0) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("success"):
                    return (time.time() - start) * 1000
    except Exception:
        pass
    return None

async def run_chaos_injection(url):
    print("\n--- Injecting Chaos & Security Anomalies ---")
    
    # 1. Malformed JSON payload
    print("Testing malformed JSON payload...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, data="{'prompt': 'unclosed quote", headers={"Content-Type": "application/json"}) as resp:
                print(f"  Malformed JSON -> Status: {resp.status} (Expected: 400 or 422)")
        except Exception as e:
            print(f"  Malformed JSON failed cleanly with error: {e}")

    # 2. Oversized payload (Flood request)
    print("Testing oversized payload (1MB string)...")
    large_str = "A" * (1024 * 1024)
    async with aiohttp.ClientSession() as session:
        try:
            payload = {"prompt": large_str, "confirmed": False}
            async with session.post(url, json=payload) as resp:
                print(f"  Oversized payload -> Status: {resp.status} (Expected: 200 mock response or payload restriction)")
        except Exception as e:
            print(f"  Oversized payload failed cleanly with error: {e}")

    # 3. HTTP Request Flood (Rate limiter trigger)
    print("Simulating high-frequency flood requests (100 rapid sequential requests)...")
    flood_count = 100
    blocked_count = 0
    async with aiohttp.ClientSession() as session:
        for i in range(flood_count):
            try:
                payload = {"prompt": f"Flood request {i}"}
                async with session.post(url, json=payload) as resp:
                    if resp.status == 429:
                        blocked_count += 1
            except Exception:
                pass
    print(f"  Flood Test -> Total sent: {flood_count}, Blocked (429): {blocked_count}")

def run_code_health_scan():
    print("\n--- Scanning Codebase Health ---")
    todos = []
    fixmes = []
    
    # Scan for TODO/FIXME markers
    search_path = "/home/warlock/ORION/services/friday-api/**/*.py"
    files = glob.glob(search_path, recursive=True)
    
    for f in files:
        if "node_modules" in f or ".venv" in f or "simulate_user" in f or "chaos_stress" in f:
            continue
        try:
            with open(f, "r", errors="ignore") as fh:
                for line_no, line in enumerate(fh, 1):
                    if "TODO" in line:
                        todos.append((f, line_no, line.strip()))
                    if "FIXME" in line:
                        fixmes.append((f, line_no, line.strip()))
        except Exception:
            pass
            
    print(f"  Discovered TODO count: {len(todos)}")
    print(f"  Discovered FIXME count: {len(fixmes)}")
    for file_path, ln, text in todos[:5]:
        print(f"    TODO in {os.path.basename(file_path)}:L{ln} -> {text[:60]}")
    for file_path, ln, text in fixmes[:5]:
        print(f"    FIXME in {os.path.basename(file_path)}:L{ln} -> {text[:60]}")

def get_system_load():
    try:
        # Threads
        threads = len(os.listdir("/proc/self/task"))
        # Memory
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()
        total = 1
        free = 1
        for line in meminfo.split("\n"):
            if "MemTotal" in line:
                total = int(line.split()[1])
            if "MemFree" in line:
                free = int(line.split()[1])
        mem_pct = ((total - free) / total) * 100
        # CPU
        with open("/proc/loadavg", "r") as f:
            load = float(f.read().split()[0])
        return load, mem_pct, threads
    except Exception:
        return 0.0, 0.0, 0

def start_backend():
    print("Booting production target backend...")
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    log_file = open("chaos_uvicorn.log", "w")
    proc = subprocess.Popen(
        [".venv/bin/uvicorn", "app.main:app", "--port", "8999", "--host", "127.0.0.1"],
        cwd="/home/warlock/ORION/services/friday-api",
        env=env,
        stdout=log_file,
        stderr=log_file
    )
    time.sleep(3.0) # Wait for kernel boot
    return proc, log_file

def main():
    proc, log_file = start_backend()
    
    cpu_init, mem_init, threads_init = get_system_load()
    print(f"Initial Resource Usage: CPU Load: {cpu_init:.2f}, Memory: {mem_init:.1f}%, Threads: {threads_init}")
    
    url = "http://localhost:8999/api/ask"
    
    # Run tests
    loop = asyncio.get_event_loop()
    concurrency_results = loop.run_until_complete(run_concurrency_test(url, [10, 25, 50, 100]))
    loop.run_until_complete(run_chaos_injection(url))
    
    run_code_health_scan()
    
    cpu_final, mem_final, threads_final = get_system_load()
    print(f"Final Resource Usage: CPU Load: {cpu_final:.2f}, Memory: {mem_final:.1f}%, Threads: {threads_final}")
    
    print("Terminating stress backend...")
    proc.terminate()
    proc.wait()
    log_file.close()
    try:
        os.remove("chaos_uvicorn.log")
    except Exception:
        pass
    print("Chaos/Stress test validation complete.")

if __name__ == "__main__":
    main()
