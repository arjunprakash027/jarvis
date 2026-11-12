#!/usr/bin/env bash
set -euo pipefail

# Query macOS RAM and SSD consumption and output taskbar/tooltip widget text.
MODE="${1:-all}"

python3 - "$MODE" << 'EOF'
import sys
import subprocess
import re
import json

mode = sys.argv[1] if len(sys.argv) > 1 else "all"

# 1. Query RAM
try:
    mem_total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip())
except Exception as e:
    sys.exit(f"Failed to query sysctl hw.memsize: {e}")

try:
    vm = subprocess.check_output(["vm_stat"]).decode("utf-8")
except Exception as e:
    sys.exit(f"Failed to query vm_stat: {e}")

page_size_match = re.search(r"page size of (\d+) bytes", vm)
page_size = int(page_size_match.group(1)) if page_size_match else 16384

def get_pages(key: str) -> int:
    m = re.search(rf"{key}:\s+(\d+)", vm)
    return int(m.group(1)) if m else 0

pages_active = get_pages("Pages active")
pages_wired = get_pages("Pages wired down")
pages_compressed = get_pages("Pages occupied by compressor")
pages_free = get_pages("Pages free")
pages_spec = get_pages("Pages speculative")
pages_inactive = get_pages("Pages inactive")

used_bytes = (pages_active + pages_wired + pages_compressed) * page_size
free_bytes = (pages_free + pages_spec) * page_size

used_gb = used_bytes / (1024 ** 3)
total_gb = mem_total / (1024 ** 3)
free_gb = free_bytes / (1024 ** 3)
active_gb = (pages_active * page_size) / (1024 ** 3)
wired_gb = (pages_wired * page_size) / (1024 ** 3)
compressed_gb = (pages_compressed * page_size) / (1024 ** 3)

ram_pct = int(round((used_bytes / mem_total) * 100))

# 2. Query SSD
try:
    df_lines = subprocess.check_output(["df", "-h", "/"]).decode("utf-8").strip().splitlines()
    df_parts = df_lines[1].split()
    ssd_filesystem = df_parts[0]
    ssd_size = df_parts[1]
    ssd_used = df_parts[2]
    ssd_avail = df_parts[3]
    ssd_capacity = df_parts[4]
except Exception as e:
    sys.exit(f"Failed to query df -h /: {e}")

taskbar_text = f"RAM: {used_gb:.1f}G/{total_gb:.1f}G ({ram_pct}%) | SSD: {ssd_used}/{ssd_size} ({ssd_capacity})"

tooltip_text = f"""RAM Breakdown:
  Total: {total_gb:.1f} GB
  Used:  {used_gb:.1f} GB ({ram_pct}%)
  Free:  {free_gb:.1f} GB
  - Active:     {active_gb:.1f} GB
  - Wired:      {wired_gb:.1f} GB
  - Compressed: {compressed_gb:.1f} GB
SSD Breakdown ({ssd_filesystem} on /):
  Total: {ssd_size}
  Used:  {ssd_used} ({ssd_capacity})
  Free:  {ssd_avail}"""

if mode == "--taskbar":
    print(taskbar_text)
elif mode == "--tooltip":
    print(tooltip_text)
elif mode == "--json":
    data = {
        "ram": {
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
            "used_percent": ram_pct,
            "active_gb": round(active_gb, 2),
            "wired_gb": round(wired_gb, 2),
            "compressed_gb": round(compressed_gb, 2)
        },
        "ssd": {
            "filesystem": ssd_filesystem,
            "mount": "/",
            "size": ssd_size,
            "used": ssd_used,
            "available": ssd_avail,
            "capacity": ssd_capacity
        },
        "taskbar": taskbar_text
    }
    print(json.dumps(data, indent=2))
elif mode in ("-h", "--help"):
    print("Usage: widget.sh [--taskbar | --tooltip | --json | --help]")
else:
    print(taskbar_text)
    print("---")
    print(tooltip_text)
EOF
