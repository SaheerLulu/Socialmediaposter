"""Command-line runner for PostPilot.

Usage:
    python cli.py "Launch post for our new eco-friendly water bottle"
    python cli.py "..." --platforms twitter,linkedin --auto-approve

By default it runs in DRY_RUN (no credentials needed) and asks for approval
interactively before each post.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from social_poster import runner  # noqa: E402
from social_poster.agent import build_agent  # noqa: E402
from social_poster.config import settings  # noqa: E402
from social_poster.schemas import ALL_PLATFORMS  # noqa: E402


def _print_pending(posts) -> None:
    print("\n" + "=" * 70)
    print("FINAL DRAFTS — awaiting your approval")
    print("=" * 70)
    for p in posts:
        print(f"\n● {p.platform.upper()}  (tool: {p.tool_name})")
        print("-" * 70)
        print(p.caption)
        if p.image_path:
            print(f"\n  image: {p.image_path}")
    print("\n" + "=" * 70)


def _prompt_decisions(posts, auto_approve: bool) -> list[dict]:
    if auto_approve:
        print("\n[--auto-approve] approving all posts.")
        return [runner.approve() for _ in posts]

    decisions = []
    for p in posts:
        while True:
            choice = input(f"\nPublish to {p.platform}? [a]pprove / [r]eject / [e]dit: ").strip().lower()
            if choice in ("a", "approve", ""):
                decisions.append(runner.approve())
                break
            if choice in ("r", "reject"):
                why = input("  reason (optional): ").strip() or "Rejected by reviewer."
                decisions.append(runner.reject(why))
                break
            if choice in ("e", "edit"):
                new_caption = input("  new caption:\n  ").strip() or p.caption
                decisions.append(runner.edit(p.tool_name, new_caption, p.image_path))
                break
            print("  please enter a, r, or e")
    return decisions


def main() -> int:
    ap = argparse.ArgumentParser(description="PostPilot — agentic social media poster")
    ap.add_argument("brief", help="The creative brief / initial prompt")
    ap.add_argument(
        "--platforms",
        default=",".join(ALL_PLATFORMS),
        help="Comma-separated subset of: twitter,instagram,linkedin",
    )
    ap.add_argument("--auto-approve", action="store_true", help="Approve every post automatically")
    ap.add_argument("--model", default=None, help="Override the chat model")
    args = ap.parse_args()

    platforms = tuple(p.strip() for p in args.platforms.split(",") if p.strip())
    invalid = [p for p in platforms if p not in ALL_PLATFORMS]
    if invalid:
        ap.error(f"unknown platforms: {invalid}; choose from {list(ALL_PLATFORMS)}")

    print(f"PostPilot · model={args.model or settings.model} · dry_run={settings.dry_run}")
    print(f"platforms: {', '.join(platforms)}")
    print(f"\nbrief: {args.brief}\n")
    print("Running the agentic flow (plan → image → draft → approve → publish)...")

    agent = build_agent(platforms=platforms, model=args.model)
    config = runner.new_thread_config()

    result = runner.start_campaign(agent, args.brief, config)

    # Resume loop: the agent may pause for approval one or more times.
    while runner.is_waiting_for_approval(result):
        posts = runner.pending_posts(result)
        _print_pending(posts)
        decisions = _prompt_decisions(posts, args.auto_approve)
        result = runner.resume_with_decisions(agent, decisions, config)

    print("\n" + "=" * 70)
    print("CAMPAIGN COMPLETE")
    print("=" * 70)
    summary = runner.final_message(result)
    if summary:
        print(summary)
    if settings.dry_run:
        print("\n(DRY RUN — staged posts written to ./outbox)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
