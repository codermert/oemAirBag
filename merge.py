"""
Tum marka JSON dosyalarini tek bir all_parts.json dosyasinda birlestirir.
GitHub Actions combine adiminda kullanilir.
"""

import json
import os
import sys
import glob

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = "output"
MERGED_FILE = os.path.join(OUTPUT_DIR, "all_parts.json")


def main():
    all_parts = []
    brand_stats = {}

    for path in sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.json"))):
        filename = os.path.basename(path)
        if filename in ("all_parts.json",):
            continue
        if os.path.isdir(path):
            continue

        with open(path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"  [!] {filename} okunamadi, atlaniyor.", flush=True)
                continue

        if isinstance(data, list):
            all_parts.extend(data)
            brand_name = filename.replace('.json', '').title()
            brand_stats[brand_name] = len(data)
            print(f"  {filename:25s} -> {len(data)} parca", flush=True)

    with open(MERGED_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_parts, f, indent=2, ensure_ascii=False)

    print(f"\nToplam: {len(all_parts)} parca -> {MERGED_FILE}", flush=True)

    summary = {
        'total_parts': len(all_parts),
        'brands': brand_stats,
        'updated_at': __import__('datetime').datetime.utcnow().isoformat() + 'Z'
    }
    with open(os.path.join(OUTPUT_DIR, "summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
