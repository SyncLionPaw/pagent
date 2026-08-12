#!/usr/bin/env python3
"""聚合 JobBench 判分结果，输出每个 (split, harness) 组合的统计与逐任务明细。

读取 `<dataset>/{split}/*/task*/eval_result/eval_{harness}/deepseek-v4-pro_judge.json`，
按 split 与 harness（deepseek-v4-flash = OpenCode；pagentv4-deepseek-v4-flash =
pagentv4 inplace）汇总，写出 `jobbench_scores.json` 快照供画图。

dataset 目录是第三方 job-bench-eval 的本地 checkout（本仓库 .gitignore 排除），
用 --dataset 指定，默认取仓库同级的 `job-bench-eval/dataset`。

用法:
    uv run python examples/eval/aggregate_scores.py                 # 打印总览
    uv run python examples/eval/aggregate_scores.py --json examples/eval/jobbench_scores.json
    uv run python examples/eval/aggregate_scores.py --detail        # 逐任务明细
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPO_ROOT / "job-bench-eval" / "dataset"

# harness 目录名 -> 展示名
HARNESS = {
    "deepseek-v4-flash": "OpenCode",
    "pagentv4-deepseek-v4-flash": "pagentv4",
}
SPLITS = ["easy", "main"]
JUDGE_FILE = "deepseek-v4-pro_judge.json"


def load_task_score(judge_path: Path) -> dict | None:
    if not judge_path.exists():
        return None
    data = json.loads(judge_path.read_text())
    total = data.get("total_score", 0)
    max_score = data.get("max_score", 0)
    if not max_score:
        return None
    return {
        "total": total,
        "max": max_score,
        "norm": total / max_score,
        "passed": data.get("passed_count", 0),
        "count": data.get("total_count", 0),
    }


def collect(dataset: Path, split: str, model: str) -> list[dict]:
    rows = []
    base = dataset / split
    for task_dir in sorted(base.glob("*/task*")):
        if not task_dir.is_dir():
            continue
        judge_path = task_dir / "eval_result" / f"eval_{model}" / JUDGE_FILE
        score = load_task_score(judge_path)
        if score is None:
            continue
        rows.append({"occ": task_dir.parent.name, "task": task_dir.name, **score})
    return rows


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0}
    norms = [r["norm"] for r in rows]
    total = sum(r["total"] for r in rows)
    maxsum = sum(r["max"] for r in rows)
    return {
        "n": len(rows),
        "macro": statistics.mean(norms),
        "micro": total / maxsum,
        "median": statistics.median(norms),
        "stdev": statistics.pstdev(norms) if len(norms) > 1 else 0.0,
        "max": max(norms),
        "min": min(norms),
        "total": total,
        "maxsum": maxsum,
        "ge08": sum(1 for x in norms if x >= 0.8),
        "mid": sum(1 for x in norms if 0.5 <= x < 0.8),
        "lt05": sum(1 for x in norms if x < 0.5),
        "zero": sum(1 for x in norms if x == 0.0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--json", type=str, default="")
    ap.add_argument("--detail", action="store_true", help="打印逐任务明细")
    args = ap.parse_args()

    if not args.dataset.is_dir():
        raise SystemExit(f"dataset 目录不存在: {args.dataset}（用 --dataset 指定）")

    out = {}
    for split in SPLITS:
        for model, hname in HARNESS.items():
            rows = collect(args.dataset, split, model)
            summ = summarize(rows)
            key = f"{split}/{hname}"
            out[key] = {"summary": summ, "rows": rows}
            n = summ.get("n", 0)
            if n == 0:
                print(f"{key:22s}  (no data)")
                continue
            print(
                f"{key:22s}  n={n:2d}  "
                f"macro={summ['macro'] * 100:5.1f}  "
                f"micro={summ['micro'] * 100:5.1f}  "
                f"median={summ['median']:.3f}  "
                f"max={summ['max']:.2f}  "
                f">=0.8:{summ['ge08']:2d}  <0.5:{summ['lt05']:2d}  0:{summ['zero']}"
            )

    if args.detail:
        for key, blob in out.items():
            rows = sorted(blob["rows"], key=lambda r: -r["norm"])
            print(f"\n=== {key} 明细 ===")
            for i, r in enumerate(rows, 1):
                print(
                    f"{i:2d} {r['norm']:.2f} {r['total']:>3}/{r['max']:<3} "
                    f"{r['passed']}/{r['count']:<2} {r['occ']}/{r['task']}"
                )

    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=2))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
