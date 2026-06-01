"""DealDesk — sales & marketing control surface (Streamlit page).

Review the prospects, run an outreach batch, and approve/edit/reject each
personalized message before it sends.

Launched automatically alongside the main app: `streamlit run app.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from social_poster.marketing import runner  # noqa: E402
from social_poster.marketing.agent import build_sales_agent  # noqa: E402
from social_poster.marketing.business import load_business_profile  # noqa: E402
from social_poster.marketing.config import marketing_settings  # noqa: E402
from social_poster.marketing.crm import LeadStore, seed_example_leads  # noqa: E402
from social_poster.marketing.governor import governor  # noqa: E402

st.set_page_config(page_title="DealDesk", page_icon="📣", layout="wide")

ss = st.session_state
ss.setdefault("dd_stage", "home")
ss.setdefault("dd_agent", None)
ss.setdefault("dd_config", None)
ss.setdefault("dd_result", None)
ss.setdefault("dd_pending", [])

CHANNEL_ICON = {"email": "✉️", "whatsapp": "💬"}


def dd_reset():
    for k in ("dd_stage", "dd_agent", "dd_config", "dd_result", "dd_pending"):
        ss.pop(k, None)
    ss.dd_stage = "home"


with st.sidebar:
    st.title("📣 DealDesk")
    st.caption("Autonomous outbound sales · human-in-the-loop")
    mode = "🟡 DRY RUN (no real sends)" if marketing_settings.dry_run else "🟢 LIVE outreach"
    st.markdown(f"**Mode:** {mode}")
    st.markdown(f"**Opt-in required:** `{marketing_settings.require_opt_in}`")
    st.markdown(f"**Autonomous daemon:** `{marketing_settings.autonomous}`")
    st.markdown(f"**Sent today:** {governor.sent_today} / {marketing_settings.max_per_day}")
    quiet = governor.in_quiet_hours()
    st.markdown(f"**Quiet hours now:** {'🌙 yes' if quiet else 'no'}")
    if Path("docs/marketing_architecture.png").exists():
        st.image("docs/marketing_architecture.png", use_container_width=True)

st.header("📣 DealDesk — Sales & Marketing")

# --- Business + CRM overview ------------------------------------------------ #
store = LeadStore()
profile = load_business_profile()

c1, c2 = st.columns([1, 1])
with c1:
    st.subheader("Your business")
    st.markdown(f"**{profile.name}** — {profile.one_liner or 'set data/business_profile.yaml'}")
    with st.expander("Profile the agent uses"):
        st.code(profile.as_brief())
with c2:
    st.subheader("Pipeline")
    leads = store.all()
    if not leads:
        if st.button("Seed example leads"):
            seed_example_leads(store)
            st.rerun()
    else:
        due = store.due_leads()
        st.metric("Leads", len(leads))
        st.metric("Eligible & due now", len(due))
        with st.expander("View leads"):
            st.dataframe(
                [{"id": l.id, "name": l.name, "company": l.company,
                  "consent": l.consent, "status": l.status, "touches": l.touches} for l in leads],
                use_container_width=True,
            )

st.divider()

# --- Run a batch ------------------------------------------------------------ #
if ss.dd_stage == "home":
    st.subheader("Run an outreach batch")
    st.write(
        "The agent grounds itself in your business, pulls eligible prospects, and "
        "drafts one personalized message each. You approve before anything sends."
    )
    if st.button("🚀 Draft outreach now", type="primary", disabled=not store.all()):
        with st.spinner("Agent is segmenting leads and drafting personalized messages…"):
            agent = build_sales_agent()
            config = runner.new_thread_config()
            result = runner.start_run(agent, runner.DEFAULT_INSTRUCTION, config)
        ss.dd_agent, ss.dd_config, ss.dd_result = agent, config, result
        ss.dd_pending = runner.pending_sends(result)
        ss.dd_stage = "review" if ss.dd_pending else "done"
        st.rerun()

elif ss.dd_stage == "review":
    st.subheader("Review messages before they send")
    decisions: list[dict] = []
    for send in ss.dd_pending:
        icon = CHANNEL_ICON.get(send.channel, "")
        lead = store.get(send.lead_id)
        who = f"{lead.name} · {lead.company}" if lead else send.lead_id
        with st.container(border=True):
            st.markdown(f"**{icon} {send.channel.title()} → {who}**")
            subject = send.subject
            if send.tool_name == "send_outreach_email":
                subject = st.text_input("Subject", value=send.subject, key=f"subj_{send.index}")
            body = st.text_area("Message", value=send.body, height=160, key=f"body_{send.index}")
            action = st.radio("Decision", ["Approve", "Edit", "Reject"],
                              horizontal=True, key=f"act_{send.index}")
            if action == "Reject":
                reason = st.text_input("Reason", key=f"rej_{send.index}")
                decisions.append(runner.reject(reason or "Rejected by reviewer."))
            elif action == "Edit" or subject != send.subject or body != send.body:
                decisions.append(runner.edit(send, subject, body))
            else:
                decisions.append(runner.approve())

    label = "📨 Send approved messages" if not marketing_settings.dry_run else "📨 Send (dry run → outbox)"
    if st.button(label, type="primary"):
        with st.spinner("Sending approved messages…"):
            result = runner.resume_with_decisions(ss.dd_agent, decisions, ss.dd_config)
        ss.dd_result = result
        more = runner.pending_sends(result)
        if more:
            ss.dd_pending = more
        else:
            ss.dd_stage = "done"
        st.rerun()

elif ss.dd_stage == "done":
    st.success("Batch complete.")
    summary = runner.final_message(ss.dd_result)
    if summary:
        st.markdown(summary)
    if marketing_settings.dry_run:
        st.info("Dry run — staged messages written to `./outbox/marketing`.")
    if st.button("🔄 Run another batch", type="primary"):
        dd_reset()
        st.rerun()

st.divider()
st.caption(
    "⚖️ Outreach is consent-filtered, rate-limited, and quiet-hour aware. You are "
    "responsible for complying with CAN-SPAM, GDPR, TCPA, and WhatsApp Business "
    "policy for your contacts. For 24/7 unattended operation run "
    "`python marketing_cli.py daemon`."
)
