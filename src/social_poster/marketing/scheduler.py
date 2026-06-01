"""The 24/7 sales & marketing daemon.

Runs outreach batches on an interval, forever, honoring quiet hours, daily
caps, and follow-up cadence. Two modes:

  * supervised  (default): each batch's drafts wait for human approval. The
                 daemon logs that approvals are pending and moves on; approve
                 them in the Streamlit UI or via the CLI.
  * autonomous  (MARKETING_AUTONOMOUS=true): the daemon auto-approves and sends
                 within the configured guardrails. Use only once you trust the
                 copy and your consent/compliance posture.

Run:  python -m social_poster.marketing.scheduler   (or: python marketing_cli.py daemon)
"""

from __future__ import annotations

import time
from datetime import datetime

from . import runner
from .agent import build_sales_agent
from .config import marketing_settings
from .crm import LeadStore, seed_example_leads
from .governor import governor


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_once(agent=None, *, auto_approve: bool | None = None) -> dict:
    """Execute a single outreach batch. Returns a small summary dict."""
    auto_approve = marketing_settings.autonomous if auto_approve is None else auto_approve

    can, why = governor.can_send()
    if not can:
        _log(f"skipping batch: {why}")
        return {"skipped": why, "sent": 0}

    agent = agent or build_sales_agent()
    config = runner.new_thread_config()
    result = runner.start_run(agent, runner.DEFAULT_INSTRUCTION, config)

    sent = 0
    pending_total = 0
    while runner.is_waiting_for_approval(result):
        pending = runner.pending_sends(result)
        pending_total += len(pending)
        if not auto_approve:
            _log(f"{len(pending)} message(s) drafted and AWAITING APPROVAL "
                 f"(supervised mode). Approve them in the UI/CLI.")
            return {"pending_approval": pending_total, "sent": 0}
        decisions = [runner.approve() for _ in pending]
        result = runner.resume_with_decisions(agent, decisions, config)
        sent += len(pending)

    _log(f"batch complete: {sent} message(s) sent, {governor.sent_today} today.")
    return {"sent": sent}


def serve_forever() -> None:
    """The 24/7 loop. Sleeps `run_interval_seconds` between batches."""
    store = LeadStore()
    seed_example_leads(store)
    _log(
        f"DealDesk daemon starting · dry_run={marketing_settings.dry_run} · "
        f"autonomous={marketing_settings.autonomous} · "
        f"interval={marketing_settings.run_interval_seconds}s · "
        f"quiet={marketing_settings.quiet_start_hour}-{marketing_settings.quiet_end_hour}h"
    )
    agent = build_sales_agent()
    try:
        while True:
            try:
                run_once(agent)
            except Exception as exc:  # keep the daemon alive across failures
                _log(f"batch error (continuing): {exc}")
            time.sleep(marketing_settings.run_interval_seconds)
    except KeyboardInterrupt:
        _log("daemon stopped.")


if __name__ == "__main__":
    serve_forever()
