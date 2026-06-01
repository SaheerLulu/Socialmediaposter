"""PostPilot — Streamlit UI.

The human-in-the-loop control surface: enter a brief, watch the agent plan and
draft, then review the FINAL posts (caption + hero image) and approve, edit, or
reject each one. On approval the agentic flow publishes automatically.

Run:  streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from social_poster import runner  # noqa: E402
from social_poster.agent import build_agent  # noqa: E402
from social_poster.config import settings  # noqa: E402
from social_poster.schemas import ALL_PLATFORMS  # noqa: E402

st.set_page_config(page_title="PostPilot", page_icon="🚀", layout="wide")

PLATFORM_ICON = {"twitter": "🐦", "instagram": "📸", "linkedin": "💼"}

# --------------------------------------------------------------------------- #
# Session state
# --------------------------------------------------------------------------- #
ss = st.session_state
ss.setdefault("stage", "input")  # input -> review -> done
ss.setdefault("agent", None)
ss.setdefault("config", None)
ss.setdefault("result", None)
ss.setdefault("pending", [])


def reset() -> None:
    for key in ("stage", "agent", "config", "result", "pending"):
        ss.pop(key, None)
    ss.stage = "input"


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("🚀 PostPilot")
    st.caption("Agentic social media poster · LangChain deep agents")
    st.divider()
    st.subheader("Settings")
    mode = "🟡 DRY RUN (no real posting)" if settings.dry_run else "🟢 LIVE posting"
    st.markdown(f"**Mode:** {mode}")
    st.markdown(f"**Model:** `{settings.model}`")
    st.markdown(f"**Image backend:** `{settings.resolved_image_provider()}`")
    st.divider()
    if Path("docs/architecture.png").exists():
        st.image("docs/architecture.png", caption="Architecture", use_container_width=True)
    st.divider()
    if st.button("🔄 New campaign", use_container_width=True):
        reset()
        st.rerun()


# --------------------------------------------------------------------------- #
# Stage 1 — brief input
# --------------------------------------------------------------------------- #
if ss.stage == "input":
    st.header("Describe your campaign")
    st.write(
        "Give PostPilot a single creative brief. It plans the campaign, generates "
        "a hero image, and drafts platform-native copy with specialist sub-agents. "
        "You approve the final posts before anything goes live."
    )

    brief = st.text_area(
        "Creative brief / initial prompt",
        placeholder="e.g. Announce the launch of our solar-powered backpack, "
        "playful and adventurous tone, aimed at outdoor enthusiasts.",
        height=130,
    )
    chosen = st.multiselect(
        "Target platforms",
        options=list(ALL_PLATFORMS),
        default=list(ALL_PLATFORMS),
        format_func=lambda p: f"{PLATFORM_ICON.get(p,'')} {p.title()}",
    )

    if st.button("✨ Generate posts", type="primary", disabled=not (brief and chosen)):
        with st.spinner("Agent is planning, generating the image, and drafting copy…"):
            agent = build_agent(platforms=tuple(chosen))
            config = runner.new_thread_config()
            result = runner.start_campaign(agent, brief, config)
        ss.agent, ss.config, ss.result = agent, config, result
        ss.pending = runner.pending_posts(result)
        ss.stage = "review" if ss.pending else "done"
        st.rerun()


# --------------------------------------------------------------------------- #
# Stage 2 — review & approve the FINAL posts
# --------------------------------------------------------------------------- #
elif ss.stage == "review":
    st.header("Review the final posts")
    st.write("Approve, edit, or reject each post. Only approved posts are published.")

    decisions: list[dict] = []
    cols = st.columns(len(ss.pending)) if ss.pending else []
    for col, post in zip(cols, ss.pending):
        with col:
            icon = PLATFORM_ICON.get(post.platform, "")
            st.subheader(f"{icon} {post.platform.title()}")
            if post.image_path and Path(post.image_path).exists():
                st.image(post.image_path, use_container_width=True)
            caption = st.text_area(
                "Caption",
                value=post.caption,
                height=220,
                key=f"cap_{post.index}",
            )
            st.caption(f"{len(caption)} characters")
            action = st.radio(
                "Decision",
                options=["Approve", "Edit", "Reject"],
                horizontal=True,
                key=f"act_{post.index}",
            )
            reason = ""
            if action == "Reject":
                reason = st.text_input("Reason", key=f"rej_{post.index}")

            if action == "Approve":
                # If the caption was changed, send it as an edit; otherwise approve.
                if caption != post.caption:
                    decisions.append(runner.edit(post.tool_name, caption, post.image_path))
                else:
                    decisions.append(runner.approve())
            elif action == "Edit":
                decisions.append(runner.edit(post.tool_name, caption, post.image_path))
            else:
                decisions.append(runner.reject(reason or "Rejected by reviewer."))

    st.divider()
    label = "🚀 Publish approved posts" if not settings.dry_run else "🚀 Publish (dry run → ./outbox)"
    if st.button(label, type="primary"):
        with st.spinner("Publishing approved posts…"):
            result = runner.resume_with_decisions(ss.agent, decisions, ss.config)
        ss.result = result
        more = runner.pending_posts(result)
        if more:
            ss.pending = more
            st.rerun()
        else:
            ss.stage = "done"
            st.rerun()


# --------------------------------------------------------------------------- #
# Stage 3 — done
# --------------------------------------------------------------------------- #
elif ss.stage == "done":
    st.header("✅ Campaign complete")
    summary = runner.final_message(ss.result)
    if summary:
        st.markdown(summary)
    if settings.dry_run:
        st.info("Dry run — staged posts were written to `./outbox`.")
        outbox = sorted(Path("outbox").glob("*.json"))
        if outbox:
            with st.expander(f"View staged post(s)"):
                for f in outbox[-3:]:
                    st.code(f.read_text(), language="json")
    if st.button("🔄 Start another campaign", type="primary"):
        reset()
        st.rerun()
