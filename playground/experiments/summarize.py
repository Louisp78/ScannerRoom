"""Gather every run of an experiment set into one table, for compare.html and README.

Usage: summarize.py <set-dir>     e.g. out/experiments/tab-south-0s-20s
Writes <set-dir>/index.json (runs and their metrics, read by compare.html) and
prints a Markdown table, one row per run, sorted by name.
"""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
runs = []
for m in sorted(root.glob("*/metrics.json")):
    meta = json.loads((m.parent / "frames.json").read_text())
    runs.append({"name": m.parent.name, "variant": meta["variant"], "seed": meta.get("seed", 0),
                 **json.loads(m.read_text())})
(root / "index.json").write_text(json.dumps(runs, indent=1) + "\n")


def pct(x):
    return "n/a" if x != x else f"{x * 100:.1f} %"  # NaN: too few overlapping confident pixels


print("| Run | Confident | Kept | Depth err. k+2 | Depth err. k+8 | Jitter | Thickness | Points |")
print("| --- | --- | --- | --- | --- | --- | --- | --- |")
for r in runs:
    print(f"| `{r['name']}` | {pct(r['confident'])} | {pct(r['kept'])} | {pct(r['depthError2'])} | "
          f"{pct(r['depthError8'])} | {r['jitter']:.2f} | {r['thickness']:.2f} | {r['points']:,} |")
