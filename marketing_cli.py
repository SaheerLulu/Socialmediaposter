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
from social_poster.marketing.crm import make_store, seed_example_leads  # noqa: E402
from social_poster.marketing.scheduler import serve_forever  # noqa: E402


def cmd_leads(_args) -> int:
    store = make_store()
    leads = store.all()
    if not leads:
        print("No leads. Run: python marketing_cli.py seed  (or import)")
        return 0
    for l in leads:
        ch = "/".join(c for c in (("email" if l.email else ""), ("whatsapp" if l.whatsapp else "")) if c)
        print(f"  {l.id}  {l.name:<16} {l.company:<16} consent={l.consent:<8} "
              f"status={l.status:<10} touches={l.touches} [{ch}]")
    print(f"\n{len(leads)} lead(s) · backend={marketing_settings.db_backend}.")
    return 0


def cmd_seed(_args) -> int:
    store = make_store()
    seed_example_leads(store)
    print(f"Seeded. {len(store.all())} lead(s) · backend={marketing_settings.db_backend}.")
    return 0


def cmd_db(_args) -> int:
    from social_poster.marketing.db import init_db

    url = init_db()
    # mask credentials in the printed URL
    import re as _re

    safe = _re.sub(r"//[^@/]+@", "//***@", url)
    print(f"CRM database initialized · {safe}")
    return 0


def cmd_import(args) -> int:
    from social_poster.marketing.ingest import import_csv, import_json

    store = make_store()
    fn = import_json if str(args.file).lower().endswith(".json") else import_csv
    summary = fn(args.file, store, source=args.source or "", default_consent=args.consent)
    print(f"Import complete: {summary}")
    if summary.get("skipped"):
        print("Note: rows skipped (missing email/whatsapp) are not added.")
    return 0


def cmd_prospect(args) -> int:
    from social_poster.marketing.prospect import prospect_companies, read_url_list

    urls = list(args.urls)
    if args.file:
        urls += read_url_list(args.file)
    if not urls:
        print("Provide one or more company URLs, or --file urls.txt")
        return 1
    store = make_store()
    print(f"Crawling {len(urls)} company site(s) for published business contacts "
          f"(role-based, robots-aware)…")
    summary = prospect_companies(
        urls, store, consent=args.consent,
        include_personal=args.include_personal, preview=args.preview,
    )
    import json as _json

    print(_json.dumps(summary, indent=2))
    if args.preview:
        print("\n(preview only — nothing imported; drop --preview to save)")
    else:
        print(f"\nImported {summary['imported']} company lead(s) under "
              f"'{args.consent}'. Review before any outreach; opt-out is included.")
    return 0


def cmd_enrich(args) -> int:
    from social_poster.marketing.enrich import build_profile_from_site

    print(f"Crawling {args.url} (your own site) to build the business profile…")
    result = build_profile_from_site(args.url)
    import json as _json

    print(_json.dumps(result, indent=2))
    if args.save:
        import yaml  # type: ignore
        from social_poster.marketing.config import marketing_settings as ms

        ms.business_profile_path.write_text(yaml.safe_dump(result["profile"], sort_keys=False))
        print(f"\nSaved profile -> {ms.business_profile_path}")
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

    sub.add_parser("db", help="create the CRM database tables").set_defaults(func=cmd_db)
    sub.add_parser("leads", help="list CRM leads").set_defaults(func=cmd_leads)
    sub.add_parser("seed", help="load example opted-in leads").set_defaults(func=cmd_seed)

    p_imp = sub.add_parser("import", help="import contacts you own (CSV/JSON)")
    p_imp.add_argument("file")
    p_imp.add_argument("--source", default="", help="where these contacts came from")
    p_imp.add_argument("--consent", default=None,
                       help="default basis if a row has none: opt_in|legitimate_interest|none")
    p_imp.set_defaults(func=cmd_import)

    p_enr = sub.add_parser("enrich", help="crawl YOUR OWN website to build the business profile")
    p_enr.add_argument("url")
    p_enr.add_argument("--save", action="store_true", help="write data/business_profile.yaml")
    p_enr.set_defaults(func=cmd_enrich)

    p_pro = sub.add_parser("prospect",
                           help="extract published business contacts from company websites (B2B)")
    p_pro.add_argument("urls", nargs="*", help="company website URLs")
    p_pro.add_argument("--file", help="file of newline-separated company URLs")
    p_pro.add_argument("--consent", default="legitimate_interest",
                       help="lawful basis to record (default: legitimate_interest)")
    p_pro.add_argument("--include-personal", action="store_true",
                       help="also accept named-individual emails (default: role inboxes only)")
    p_pro.add_argument("--preview", action="store_true", help="show findings without importing")
    p_pro.set_defaults(func=cmd_prospect)

    p_run = sub.add_parser("run", help="run one outreach batch")
    p_run.add_argument("--auto-approve", action="store_true")
    p_run.set_defaults(func=cmd_run)

    sub.add_parser("daemon", help="run the 24/7 scheduler").set_defaults(func=cmd_daemon)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
