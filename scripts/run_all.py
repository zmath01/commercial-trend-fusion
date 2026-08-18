#!/usr/bin/env python3
"""run_all.py — end-to-end pipeline orchestrator.

Usage:
  python scripts/run_all.py                 # full pipeline on real corpus
  python scripts/run_all.py --steps fetch   # only fetch (resumes)
  python scripts/run_all.py --sample        # run on the small committed sample

Steps: fetch -> sample -> lexicon -> annotate -> graph -> backtest -> predict -> site
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

STEPS = ["fetch", "sample", "lexicon", "annotate", "graph", "backtest", "predict", "site"]


def run(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=str, default=",".join(STEPS),
                    help=f"comma list of steps: {','.join(STEPS)}")
    ap.add_argument("--sample", action="store_true",
                    help="use the committed sample corpus (CI / quick demo)")
    args = ap.parse_args()

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    for s in steps:
        if s not in STEPS:
            raise SystemExit(f"unknown step: {s}")
    if not steps:
        raise SystemExit("no steps given")

    base = ["python3"]
    extra = ["--sample"] if args.sample else []
    for s in steps:
        if s == "fetch":
            run([*base, "scripts/fetch_arxiv.py"])
        elif s == "sample":
            run([*base, "scripts/corpus.py"])
        elif s == "lexicon":
            run([*base, "scripts/build_lexicon.py", *extra])
        elif s == "annotate":
            run([*base, "scripts/annotate.py", *extra])
        elif s == "graph":
            run([*base, "scripts/build_graph.py", *extra])
        elif s == "backtest":
            run([*base, "scripts/backtest.py", *extra])
        elif s == "predict":
            run([*base, "scripts/predict.py", *extra])
        elif s == "site":
            run([*base, "scripts/build_site.py"])
    print("\nAll steps complete.")


if __name__ == "__main__":
    main()
