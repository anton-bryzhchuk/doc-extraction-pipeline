"""CLI: ``python -m docpipe <command>``."""
from __future__ import annotations

import argparse
import sys

from .config import DOCS_DIR
from .eval import evaluate, render_markdown, write_reports
from .invoices import generate_all
from .logging_utils import setup_logging

# For each failure profile: what the validation layer is expected to do.
_DEMO_EXPECTATIONS = {
    "noisy": "misread/missing fields -> routed to needs_review",
    "hallucinating": "invented wrong total -> arithmetic check fails -> needs_review",
    "malformed": "invalid JSON -> fails after retries -> status failed",
}


def cmd_generate(args: argparse.Namespace) -> int:
    gt = generate_all(seed=args.seed)
    print(f"Generated {len(gt)} invoices + ground_truth.json")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    report = evaluate(profile=args.profile, seed=args.seed)
    json_path, md_path = write_reports(report)
    print(render_markdown(report))
    print(f"Wrote {json_path} and {md_path}")
    # Non-zero exit if a wrong value slipped through auto-approval.
    return 0 if report["wrongly_auto_approved"] == 0 else 1


def cmd_demo_failures(args: argparse.Namespace) -> int:
    rows = []
    all_handled = True
    for profile, why in _DEMO_EXPECTATIONS.items():
        report = evaluate(profile=profile, seed=args.seed)
        slipped = report["wrongly_auto_approved"]
        if profile == "malformed":
            activity_ok = report["failed"] > 0
        else:
            activity_ok = report["needs_review"] > 0
        handled = (slipped == 0) and activity_ok
        all_handled = all_handled and handled
        rows.append({"profile": profile, "why": why, "report": report, "handled": handled})
        status = "HANDLED" if handled else "LEAK/UNHANDLED"
        print(
            f"[{status}] profile={profile:14s} "
            f"review={report['needs_review']} failed={report['failed']} "
            f"auto={report['auto_approved']} wrongly_auto_approved={slipped}"
        )

    _write_demo_doc(rows, all_handled)
    print()
    print("All bad extractions handled ✅" if all_handled else "Some leaked ❌")
    return 0 if all_handled else 1


def _write_demo_doc(rows: list[dict], all_handled: bool) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Demo: the validation layer catches bad extractions",
        "",
        "Each mock profile injects a realistic extraction failure. This table shows",
        "how the deterministic validation + routing layer handled it. The key column",
        "is **wrongly auto-approved** -- a wrong value that slipped through (must be 0).",
        "",
        f"**Result:** {'all handled ✅' if all_handled else 'some leaked ❌'}",
        "",
        "| Profile | Injected failure | Auto-approved | Needs review | Failed | Wrongly auto-approved |",
        "|---------|------------------|---------------|--------------|--------|-----------------------|",
    ]
    for row in rows:
        r = row["report"]
        lines.append(
            f"| `{row['profile']}` | {row['why']} | {r['auto_approved']} | "
            f"{r['needs_review']} | {r['failed']} | **{r['wrongly_auto_approved']}** |"
        )
    lines.append("")
    (DOCS_DIR / "demo-failures.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("docpipe.api:create_app", factory=True, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="docpipe", description="Document extraction pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    pg = sub.add_parser("generate", help="generate synthetic invoices + ground truth")
    pg.add_argument("--seed", type=int, default=2026)
    pg.set_defaults(func=cmd_generate)

    pe = sub.add_parser("evaluate", help="run the pipeline over all invoices and write reports")
    pe.add_argument("--profile", default="good")
    pe.add_argument("--seed", type=int, default=2026)
    pe.set_defaults(func=cmd_evaluate)

    pd = sub.add_parser("demo-failures", help="prove validation catches bad extractions")
    pd.add_argument("--seed", type=int, default=2026)
    pd.set_defaults(func=cmd_demo_failures)

    ps = sub.add_parser("serve", help="run the FastAPI app")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--port", type=int, default=8000)
    ps.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
