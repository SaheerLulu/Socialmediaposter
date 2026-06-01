"""Command-line entry point for the DealDesk sales & marketing module.

Commands:
    python marketing_cli.py leads                 # list CRM leads
    python marketing_cli.py seed                   # load example leads
    python marketing_cli.py run [--auto-approve]   # one supervised/auto batch
    python marketing_cli.py daemon                 # run 24/7 scheduler

Runs in DRY_RUN by default (no real emails/messages sent).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from social_poster.marketing import runner  # noqa: E402
from social_poster.marketing.agent import build_sales_agent  # noqa: E402
from social_poster.marketing.config import marketing_settings  # noqa: E402
from social_poster.marketing.crm import LeadStore, seed_example_leads  # noqa: E402
from social_poster.marketing.scheduler import serve_forever  # noqa: E402


def cmd_leads(_args) -> int:
    store = LeadStore()
    leads = store.all()
    if not leads:
        print("No leads. Run: python marketing_cli.py seed")
        return 0
    for l in leads:
        ch = "/".join(c for c in (("email" if l.email else ""), ("whatsapp" if l.whatsapp else "")) if c)
        print(f"  {l.id}  {l.name:<16} {l.company:<16} consent={l.consent:<8} "
              f"status={l.status:<10} touches={l.touches} [{ch}]")
    print(f"\n{len(leads)} lead(s).")
    return 0


def cmd_seed(_args) -> int:
    store = LeadStore()
    seed_example_leads(store)
    print(f"Seeded. {len(store.all())} lead(s) in {store.path}.")
    return 0


def _review_pending(pending, auto_approve: bool) -> list[dict]:
    if auto_approve:
        print(f"[--auto-approve] approving {len(pending)} message(s).")
        return [runner.approve() for _ in pending]
    decisions = []
    for s in pending:
        print("\n" + "-" * 70)
        print(f"To lead {s.lead_id} via {s.channel}")
        if s.subject:
            print(f"Subject: {s.subject}")
        print(s.body)
        print("-" * 70)
        choice = input("[a]pprove / [r]eject / [e]dit: ").strip().lower()
        if choice in ("r", "reject"):
            decisions.append(runner.reject(input("  reason: ").strip() or "Rejected."))
        elif choice in ("e", "edit"):
            subj = input(f"  subject [{s.subject}]: ").strip() or s.subject
            body = input("  body: ").strip() or s.body
            decisions.append(runner.edit(s, subj, body))
        else:
            decisions.append(runner.approve())
    return decisions


def cmd_run(args) -> int:
    print(f"DealDesk · dry_run={marketing_settings.dry_run} · "
          f"require_opt_in={marketing_settings.require_opt_in}")
    agent = build_sales_agent()
    config = runner.new_thread_config()
    result = runner.start_run(agent, runner.DEFAULT_INSTRUCTION, config)
    while runner.is_waiting_for_approval(result):
        pending = runner.pending_sends(result)
        decisions = _review_pending(pending, args.auto_approve)
        result = runner.resume_with_decisions(agent, decisions, config)
    print("\n" + runner.final_message(result))
    if marketing_settings.dry_run:
        print("\n(DRY RUN — staged messages in ./outbox/marketing)")
    return 0


def cmd_daemon(_args) -> int:
    serve_forever()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="DealDesk — sales & marketing agent")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("leads").set_defaults(func=cmd_leads)
    sub.add_parser("seed").set_defaults(func=cmd_seed)
    p_run = sub.add_parser("run")
    p_run.add_argument("--auto-approve", action="store_true")
    p_run.set_defaults(func=cmd_run)
    sub.add_parser("daemon").set_defaults(func=cmd_daemon)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
