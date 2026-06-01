"""Render the architecture diagram (docs/architecture.png) with matplotlib.

Run:  python scripts/generate_diagrams.py
No external tools (graphviz etc.) required.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

DOCS = Path(__file__).resolve().parents[1] / "docs"
DOCS.mkdir(exist_ok=True)

INK = "#0f172a"
INDIGO = "#6366f1"
PINK = "#ec4899"
TEAL = "#14b8a6"
AMBER = "#f59e0b"
SLATE = "#475569"
PAPER = "#f8fafc"


def _box(ax, xy, w, h, text, face, fg="white", fs=11, bold=True):
    x, y = xy
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=0, facecolor=face, zorder=2,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2, y + h / 2, text,
        ha="center", va="center", color=fg,
        fontsize=fs, fontweight="bold" if bold else "normal", zorder=3, wrap=True,
    )
    return (x + w / 2, y + h / 2, w, h)


def _arrow(ax, p1, p2, color=SLATE, style="-|>", lw=2.0, ls="-"):
    ax.add_patch(
        FancyArrowPatch(
            p1, p2, arrowstyle=style, mutation_scale=16,
            linewidth=lw, color=color, linestyle=ls,
            shrinkA=6, shrinkB=6, zorder=1,
        )
    )


def main() -> None:
    fig, ax = plt.subplots(figsize=(13, 8.5))
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(0.4, 8.55, "PostPilot", fontsize=26, fontweight="bold", color=INK)
    ax.text(
        0.4, 8.15,
        "Agentic social media poster · LangChain deep agents · human-in-the-loop",
        fontsize=12, color=SLATE,
    )

    # User / brief
    user = _box(ax, (0.4, 6.7), 2.4, 0.9, "User\nCreative brief", INK)
    # UI layer
    ui = _box(ax, (0.4, 5.0), 2.4, 1.0, "Streamlit UI\n+ CLI", SLATE)

    # Orchestrator deep agent
    orch = _box(ax, (4.0, 6.2), 4.8, 1.4,
                "Orchestrator Deep Agent\n(LangGraph state machine)\nplanning · virtual filesystem", INDIGO)

    # Sub-agents
    sa_y = 4.2
    sa1 = _box(ax, (3.5, sa_y), 1.7, 0.95, "twitter\nwriter", TEAL, fs=10)
    sa2 = _box(ax, (5.45, sa_y), 1.7, 0.95, "instagram\nwriter", TEAL, fs=10)
    sa3 = _box(ax, (7.4, sa_y), 1.7, 0.95, "linkedin\nwriter", TEAL, fs=10)

    # Image tool
    img = _box(ax, (9.9, 6.2), 2.7, 1.0, "generate_image\n(OpenAI · Gemini ·\nplaceholder)", AMBER, fs=10)

    # Human approval gate
    gate = _box(ax, (4.0, 2.5), 4.8, 1.0,
                "[ STOP ]  Human Approval Gate\nLangGraph interrupt — approve / edit / reject", PINK, fs=11)

    # Posting tools
    pt_y = 0.7
    pt1 = _box(ax, (3.3, pt_y), 1.9, 0.95, "post_to\nTwitter/X", INK, fs=10)
    pt2 = _box(ax, (5.45, pt_y), 1.9, 0.95, "post_to\nInstagram", INK, fs=10)
    pt3 = _box(ax, (7.6, pt_y), 1.9, 0.95, "post_to\nLinkedIn", INK, fs=10)

    # External APIs
    ext = _box(ax, (10.2, 0.7), 2.4, 2.8,
               "Social APIs\n\nTwitter v2\nInstagram Graph\nLinkedIn UGC", SLATE, fs=10)

    # Arrows
    _arrow(ax, (user[0], 6.7), (ui[0], 6.0))
    _arrow(ax, (ui[0] + 0.9, 5.6), (4.0, 6.7))
    _arrow(ax, (orch[0], 6.2), (sa1[0], sa_y + 0.95), color=TEAL)
    _arrow(ax, (orch[0], 6.2), (sa2[0], sa_y + 0.95), color=TEAL)
    _arrow(ax, (orch[0], 6.2), (sa3[0], sa_y + 0.95), color=TEAL)
    _arrow(ax, (8.8, 6.9), (9.9, 6.7), color=AMBER)

    # drafts flow back up then down to gate
    _arrow(ax, (orch[0], 6.2), (gate[0], 3.5), color=PINK, lw=2.4)
    _arrow(ax, (gate[0], 2.5), (pt1[0], pt_y + 0.95), color=INK)
    _arrow(ax, (gate[0], 2.5), (pt2[0], pt_y + 0.95), color=INK)
    _arrow(ax, (gate[0], 2.5), (pt3[0], pt_y + 0.95), color=INK)
    _arrow(ax, (pt3[0] + 0.95, pt_y + 0.5), (10.2, 1.8), color=SLATE)

    # approval round-trip annotation
    _arrow(ax, (gate[0] - 2.4, 3.0), (ui[0] + 0.4, 5.0), color=PINK, ls="--", lw=1.6, style="<|-|>")
    ax.text(1.7, 4.0, "final posts\nshown for\napproval", fontsize=9, color=PINK, ha="center")

    # Legend
    handles = [
        mpatches.Patch(color=INDIGO, label="Orchestrator (deep agent)"),
        mpatches.Patch(color=TEAL, label="Content sub-agents"),
        mpatches.Patch(color=AMBER, label="Image generation tool"),
        mpatches.Patch(color=PINK, label="Human-in-the-loop gate"),
        mpatches.Patch(color=INK, label="Posting tools / APIs"),
    ]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, -0.02),
              ncol=3, frameon=False, fontsize=9)

    out = DOCS / "architecture.png"
    plt.tight_layout()
    plt.savefig(out, dpi=150, facecolor=PAPER, bbox_inches="tight")
    print(f"wrote {out}")
    plt.close(fig)


def marketing() -> None:
    """DealDesk sales & marketing module diagram -> docs/marketing_architecture.png."""
    fig, ax = plt.subplots(figsize=(13, 8.5))
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(0.4, 8.55, "DealDesk", fontsize=26, fontweight="bold", color=INK)
    ax.text(0.4, 8.15,
            "24/7 autonomous outbound sales · consent-aware · human-in-the-loop",
            fontsize=12, color=SLATE)

    sched = _box(ax, (0.4, 6.6), 2.6, 1.1,
                 "Scheduler daemon\n24/7 · quiet hours\nrate caps · cadence", AMBER, fs=10)
    biz = _box(ax, (0.4, 4.9), 2.6, 1.0, "Business profile\n(who we are,\nwhat we sell)", SLATE, fs=10)
    crm = _box(ax, (0.4, 3.0), 2.6, 1.2,
               "CRM / Lead store\nconsent · suppression\ntouches · follow-ups", SLATE, fs=10)

    agent = _box(ax, (4.0, 6.0), 4.8, 1.5,
                 "DealDesk Deep Agent\nsegment → personalize → send\nplanning · sub-agents", INDIGO)
    writer = _box(ax, (5.0, 4.2), 2.8, 0.95, "copywriter\nsub-agent", TEAL, fs=10)

    govern = _box(ax, (4.0, 2.4), 4.8, 1.0,
                  "Eligibility + throttle guard\nconsent · caps · quiet hours", PINK, fs=10)
    gate = _box(ax, (4.0, 0.7), 4.8, 1.0,
                "[ STOP ]  Human Approval Gate\napprove / edit / reject each message", PINK, fs=11)

    email = _box(ax, (9.9, 5.2), 2.7, 1.0, "Email channel\n(SMTP)", INK, fs=10)
    wa = _box(ax, (9.9, 3.6), 2.7, 1.0, "WhatsApp channel\n(Meta / Twilio)", INK, fs=10)
    ext = _box(ax, (9.9, 1.0), 2.7, 1.6, "Prospects\n\n(opted-in\ncontacts)", SLATE, fs=10)

    _arrow(ax, (sched[0], 6.6), (4.0, 6.7), color=AMBER, lw=2.2)
    _arrow(ax, (biz[0] + 1.3, 5.4), (4.0, 6.4), color=SLATE)
    _arrow(ax, (crm[0] + 1.3, 4.2), (4.0, 6.1), color=SLATE)
    _arrow(ax, (agent[0], 6.0), (writer[0], 5.15), color=TEAL)
    _arrow(ax, (agent[0], 6.0), (govern[0], 3.4), color=PINK, lw=2.2)
    _arrow(ax, (govern[0], 2.4), (gate[0], 1.7), color=PINK, lw=2.2)
    _arrow(ax, (gate[0] + 2.4, 1.2), (9.9, 4.0), color=INK)
    _arrow(ax, (gate[0] + 2.4, 1.4), (9.9, 5.6), color=INK)
    _arrow(ax, (email[0], 5.2), (ext[0], 2.6), color=SLATE, ls="--", lw=1.4)
    _arrow(ax, (wa[0], 3.6), (ext[0] + 0.2, 2.6), color=SLATE, ls="--", lw=1.4)

    handles = [
        mpatches.Patch(color=AMBER, label="24/7 scheduler"),
        mpatches.Patch(color=INDIGO, label="Sales agent"),
        mpatches.Patch(color=TEAL, label="Copywriter sub-agent"),
        mpatches.Patch(color=PINK, label="Compliance + approval"),
        mpatches.Patch(color=INK, label="Channels / prospects"),
    ]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, -0.02),
              ncol=3, frameon=False, fontsize=9)

    out = DOCS / "marketing_architecture.png"
    plt.tight_layout()
    plt.savefig(out, dpi=150, facecolor=PAPER, bbox_inches="tight")
    print(f"wrote {out}")
    plt.close(fig)


if __name__ == "__main__":
    main()
    marketing()
