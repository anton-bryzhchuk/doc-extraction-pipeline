#!/usr/bin/env python3
"""Generate 30 synthetic invoices (PDFs) + data/ground_truth.json.

All data is invented; no real people or companies. Deterministic (seeded) so
the PDFs always match the committed ground truth.

Usage:
    python scripts/generate_invoices.py [--seed 2026]
"""
from __future__ import annotations

import argparse

from docpipe.invoices import generate_all


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    gt = generate_all(seed=args.seed)
    print(f"Generated {len(gt)} invoices + ground_truth.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
