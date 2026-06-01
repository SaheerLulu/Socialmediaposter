"""Tests that exercise the agent wiring, tools, and runner without an LLM call.

Run:  PYTHONPATH=src python -m pytest -q   (or: python tests/test_core.py)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("SOCIAL_POSTER_DRY_RUN", "true")
os.environ.setdefault("SOCIAL_POSTER_IMAGE_PROVIDER", "placeholder")


def test_image_generation_creates_png():
    from social_poster.tools.image_gen import generate_image

    path = generate_image.invoke({"prompt": "a calm mountain lake at sunrise"})
    p = Path(path)
    assert p.exists() and p.suffix == ".png" and p.stat().st_size > 1000


def test_dry_run_posting_tools_return_permalink():
    from social_poster.tools import POSTING_TOOLS

    for platform, tool in POSTING_TOOLS.items():
        out = tool.invoke({"caption": f"hello {platform}", "image_path": None})
        assert "DRY RUN" in out and "example.test" in out


def test_runner_decision_helpers():
    from social_poster import runner

    assert runner.approve() == {"type": "approve"}
    assert runner.reject("nope")["type"] == "reject"
    e = runner.edit("post_to_twitter", "new text", "/tmp/x.png")
    assert e["type"] == "edit"
    assert e["edited_action"]["args"]["caption"] == "new text"


def test_pending_posts_parsing():
    from social_poster import runner

    fake_interrupt = SimpleNamespace(
        value={
            "action_requests": [
                {"name": "post_to_twitter", "args": {"caption": "hi", "image_path": "/tmp/a.png"},
                 "description": "review"},
                {"name": "post_to_linkedin", "args": {"caption": "pro", "image_path": None},
                 "description": "review"},
            ]
        }
    )
    posts = runner.pending_posts({"__interrupt__": [fake_interrupt]})
    assert [p.platform for p in posts] == ["twitter", "linkedin"]
    assert posts[0].caption == "hi"
    assert runner.is_waiting_for_approval({"__interrupt__": [fake_interrupt]})
    assert not runner.is_waiting_for_approval({"messages": []})


def test_build_agent_wires_hitl_and_subagents():
    from social_poster.agent import build_agent

    agent = build_agent(platforms=("twitter", "linkedin"), model="claude-sonnet-4-5-20250929")
    nodes = list(agent.get_graph().nodes.keys())
    assert any("HumanInTheLoop" in n for n in nodes)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
