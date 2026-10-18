"""Local browser interface. Business rules and Gemini calls live in app/, not widgets."""
from __future__ import annotations

import json
import os

import streamlit as st
from dotenv import load_dotenv

from app import actions
from app.domain import ALLOWED, canonical, current_inputs, digest, ready, satisfied, valid_bundle
from app.service import new_id

load_dotenv()
st.set_page_config(page_title="Continuity", page_icon="↗", layout="wide")
st.markdown("""<style>
.block-container {max-width:1200px;padding-top:2rem}
div[data-testid="stMetric"] {background:#f0f7f5;padding:1rem;border-radius:12px}
div[data-testid="stMetric"] label, div[data-testid="stMetric"] div {color:#153f35}
</style>""", unsafe_allow_html=True)


def flash(message, level="success"):
    st.session_state["notice"] = {"message": message, "level": level}
    st.rerun()


def request_id(action, inputs):
    key = digest([tenant, project, action, inputs])
    pending = st.session_state.setdefault("pending_requests", {})
    if key not in pending:
        pending[key] = new_id()
    return key, pending[key]


def execute(action, inputs, fn, original_request_id=None):
    key, rid = request_id(action, inputs)
    if original_request_id is not None:
        rid = original_request_id
        st.session_state["pending_requests"][key] = rid
    st.caption("Request ID: " + rid)
    try:
        with st.spinner("Checking memory and saving the result…"):
            receipt = fn(rid)
        st.session_state["last_receipt"] = {"scope": [tenant, project], "receipt": receipt}
        if receipt.get("handoff"):
            st.session_state["recent_handoff"] = receipt["handoff"]
        st.session_state["pending_requests"].pop(key, None)
        if receipt.get("accepted") is False:
            flash("Saved as a stale attempt. " + receipt.get("reason", "Inspect current inputs and replan."), "warning")
        flash("Saved. Project state has been refreshed.")
    except Exception as exc:
        st.error(actions.error_message(exc))
        st.caption("Retry with the same inputs to retain this request ID. Changed inputs start a new request.")


def draft_view(content):
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        st.write(content)
        return
    st.write(data.get("summary", ""))
    for index, step in enumerate(data.get("steps", []), 1):
        st.write(f"{index}. {step}")


st.sidebar.title("↗ Continuity")
st.sidebar.caption("Pick up where you left off.")
if st.session_state.get("interface_version") != "live-v2":
    st.session_state.clear()
    st.session_state["interface_version"] = "live-v2"
st.session_state.setdefault("scope", {"tenant": "userA", "project": "my_project"})
scope = st.session_state["scope"]
with st.sidebar.form("scope_form"):
    tenant_input = st.text_input("User", value=scope["tenant"])
    project_input = st.text_input("Project", value=scope["project"])
    if st.form_submit_button("Open project"):
        st.session_state["scope"] = {"tenant": tenant_input.strip(), "project": project_input.strip()}
        st.rerun()
tenant, project = scope["tenant"], scope["project"]
st.sidebar.caption("Stored locally. User/project names separate your records; they are not passwords.")
page = st.sidebar.radio("Explore", ["Workspace", "Memory", "Benchmark"], label_visibility="collapsed", key="page")
st.sidebar.caption("Live Gemini ? " + os.getenv("GOOGLE_MODEL", "model not configured"))

try:
    service = actions.connect(tenant, project)
    state = service.store.read()
except Exception as exc:
    st.title("Continuity")
    st.error(actions.error_message(exc))
    st.code(".\\docker.ps1 compose up -d --wait", language="powershell")
    st.stop()

if st.sidebar.button("Refresh memory", key="refresh"):
    st.rerun()
if st.sidebar.button("Start new request after a failed attempt", key="clear_pending"):
    st.session_state["pending_requests"] = {}
    flash("New actions will use new request IDs. Existing saved requests remain in the database.")

st.title("Continuity")
st.caption(f"{project}  /  {tenant}  ·  Persistent project memory")
if st.session_state.get("notice"):
    notice = st.session_state.pop("notice")
    if isinstance(notice, str):
        st.success(notice)
    else:
        getattr(st, notice["level"])(notice["message"])

if page == "Workspace":
    st.header("Your next step")
    st.write("Planner chooses ready work. Helper reads the saved plan and suggests steps. You do the work and report the outcome.")
    if not state["tasks"]:
        st.info("This project is empty. Describe your own task below to create a live plan.")
    available = ready(state)
    review_tasks = [t for t in state["tasks"].values() if t.get("result") and state["results"][t["result"]]["review_state"] == "requires_review"]
    a, b, c, d = st.columns(4)
    a.metric("Ready to start", len(available))
    b.metric("In progress", sum(t["status"] == "in_progress" for t in state["tasks"].values()))
    c.metric("Needs review", len(review_tasks))
    d.metric("Valid completed", sum(satisfied(state, tid) for tid in state["tasks"]))
    left, right = st.columns([1, 1.15], gap="large")
    with left:
        st.subheader("1 · Make a plan")
        if state["tasks"] and not available:
            st.info("No unclaimed task is ready. Continue an existing handoff, resolve a review, release unfinished work, or start a new task below.")
        plan_mode = st.radio("Plan", ["Start a new task", "Plan saved tasks"], key="plan_mode", horizontal=True)
        with st.form("planner"):
            prompt = st.text_area("What would you like to work on?", value="", placeholder="Describe your real task or goal", key="plan_prompt")
            with st.expander("Optional dependencies for a new task"):
                required_decisions = st.multiselect("Use these saved technical decisions", [k for k in state["decisions"] if k != "response_style"], key="plan_requires")
                prior_tasks = st.multiselect("Wait for these tasks first", list(state["tasks"]), key="plan_dependencies")
                approved_procedures = st.multiselect("Follow these approved procedures", list(state["procedures"]), key="plan_procedures")
            if st.form_submit_button("Create plan", disabled=plan_mode == "Plan saved tasks" and not available, type="primary"):
                if not prompt.strip():
                    st.error("Describe what you want to work on first.")
                elif plan_mode == "Start a new task":
                    inputs = [prompt, required_decisions, prior_tasks, approved_procedures]
                    execute("new_plan", inputs, lambda rid: actions.plan_new_task(service, rid, prompt, required_decisions, prior_tasks, approved_procedures))
                else:
                    execute("plan", prompt, lambda rid: actions.workflow(service, rid, "planner", prompt))
        st.subheader("Tasks")
        for tid, task in state["tasks"].items():
            result = state["results"].get(task.get("result"))
            needs_review = result and result["review_state"] == "requires_review"
            label = "Needs review" if needs_review else "Ready" if tid in available else task["status"].replace("_", " ").title()
            with st.container(border=True):
                st.write(f"**{task['title']}**")
                st.caption(label + " · " + tid)
                reasons = [state["tasks"][p]["title"] for p in task["prerequisites"] if not satisfied(state, p)]
                if reasons:
                    st.caption("Waiting for: " + ", ".join(reasons))
                if task["requires"]:
                    st.caption("Uses: " + ", ".join(task["requires"]))
        with st.expander("Add your own task"):
            with st.form("new_task"):
                task_id = st.text_input("Short task ID", placeholder="write_intro", key="task_id")
                title = st.text_input("Task title", key="task_title")
                requirements = st.multiselect("Technical decisions this task depends on", ["interface_framework", "database_engine"], key="task_requirements")
                dependencies = st.multiselect("Tasks that must finish first", list(state["tasks"]), key="task_dependencies")
                procs = st.multiselect("Approved procedures to follow", list(state["procedures"]), key="task_procedures")
                if st.form_submit_button("Save task"):
                    p = {"id": task_id.strip(), "title": title, "requires": requirements, "prerequisites": dependencies, "procedures": procs}
                    execute("task", p, lambda rid: actions.mutate(service, rid, "task", p))
    with right:
        st.subheader("2 · Continue a saved plan")
        handoffs = list(reversed(state["handoffs"]))
        if not handoffs:
            st.caption("Your saved plans will appear here.")
        else:
            def handoff_label(hid):
                h = state["handoffs"][hid]
                return state["tasks"][h["bundle"]["task"]]["title"] + " · " + h["status"] + " · " + hid[-6:]
            recent = st.session_state.get("recent_handoff")
            selected = st.selectbox("Saved plan", handoffs, index=handoffs.index(recent) if recent in handoffs else 0, format_func=handoff_label, key="handoff_choice")
            h = state["handoffs"][selected]
            task = state["tasks"][h["bundle"]["task"]]
            st.write(h["objective"])
            good = valid_bundle(state, h["bundle"], h.get("execution_version") if h["status"] == "claimed" else None)
            owns = h["claim"] is not None and h["claim"] == task["claim"]
            usable = (h["status"] == "saved" and task["status"] == "pending" and good) or (h["status"] == "claimed" and owns and good)
            if not usable:
                st.info("This plan is finished or its task/inputs changed. Read its history, or make a new plan when the task is ready.")
            with st.expander("Inputs remembered for this plan"):
                for key, did in h["bundle"]["decisions"].items():
                    decision = state["versions"][did]
                    st.write(f"**{key}:** {decision['value']}")
                    st.caption("User source: " + decision["source"]["passage"])
                for name, pid in h["bundle"]["procedures"].items():
                    procedure = state["procedure_versions"][pid]
                    st.write("**Procedure: " + name + "**")
                    for step in procedure["steps"]:
                        st.write("• " + step)
                st.caption("Plan ID: " + selected)
            if h.get("draft"):
                attempt = state["attempts"][h["draft"]]
                st.markdown("**Saved Helper draft**")
                draft_view(attempt["content"])
                st.caption("Assistant draft · " + ("inputs changed" if not good or attempt["stale"] else "inputs current"))
            elif st.button("Get Helper steps" if h["status"] == "saved" else "Retry original Helper request", disabled=not usable, key="help", type="primary"):
                if h["status"] == "claimed":
                    try:
                        saved = actions.helper_request(service, selected)
                        execute("helper_resume", saved, lambda _: actions.resume_helper(service, saved), original_request_id=saved["request_id"])
                    except Exception as exc:
                        st.error(actions.error_message(exc))
                else:
                    execute("help", selected, lambda rid: actions.workflow(service, rid, "helper", "Suggest practical steps using this saved plan.", handoff=selected))
            if h["status"] == "claimed" and owns:
                with st.expander("3 · Report work you actually finished"):
                    with st.form("completion"):
                        outcome = st.text_area("What did you do, and how did you check it?", key="outcome")
                        confirmed = st.checkbox("I performed this work. Record my report as user-reported evidence.", key="completion_confirm")
                        if st.form_submit_button("Record completed work"):
                            if not confirmed or not outcome.strip():
                                st.error("Report the actual outcome and confirm that you performed the work.")
                            else:
                                p = {"handoff": selected, "claim": h["claim"], "execution_version": h["execution_version"], "outcome": outcome}
                                execute("complete", p, lambda rid: actions.mutate(service, rid, "complete", p))
                with st.expander("Return unfinished work to the queue"):
                    if st.checkbox("Release this claim so the task can be planned again", key="release_confirm"):
                        if st.button("Release task", key="release"):
                            p = {"task": task["id"], "claim": h["claim"], "confirmed": True}
                            execute("release", p, lambda rid: actions.mutate(service, rid, "release", p))
        if review_tasks:
            st.subheader("Review affected work")
            reviewed = st.selectbox("Task requiring review", [t["id"] for t in review_tasks], key="review_task")
            t = state["tasks"][reviewed]
            result = state["results"][t["result"]]
            st.write("Earlier outcome: " + result["outcome"])
            st.caption("Original inputs: " + ", ".join(state["versions"][did]["value"] for did in result["based_on"].values()))
            st.caption("Current inputs: " + ", ".join(state["versions"][did]["value"] for did in current_inputs(state, t).values()))
            with st.form("review_form"):
                resolution = st.selectbox("Your resolution", ["confirm", "reopen", "replace"], format_func=lambda x: {"confirm": "Existing work is compatible", "reopen": "Do this task again", "replace": "Create replacement work"}[x], key="resolution")
                replacement = st.text_input("Replacement task ID (for replacement only)", value=reviewed + "_v2", key="replacement")
                dependents = sorted(x["id"] for x in state["tasks"].values() if reviewed in x["prerequisites"])
                st.caption("Replacement would rewire these dependent tasks: " + (", ".join(dependents) or "none"))
                confirm = st.checkbox("I confirm this resolution against the displayed decisions and dependency changes.", key="review_confirm")
                submit = st.form_submit_button("Save review")
            preview_key = f"review_preview:{tenant}:{project}:{reviewed}"
            if submit:
                preview = st.session_state.get(preview_key)
                if not confirm:
                    st.error("Confirm your resolution before saving the review.")
                elif preview is None:
                    st.error("Refresh and inspect this review before confirming.")
                else:
                    p = {"task": reviewed, "action": resolution, "confirmed": True, "replacement": replacement, "rewire": preview["rewire"], "task_version": preview["version"], "decisions": preview["decisions"]}
                    execute("review", p, lambda rid: actions.mutate(service, rid, "review", p))
            else:
                st.session_state[preview_key] = {"version": t["version"], "decisions": current_inputs(state, t), "rewire": dependents}

elif page == "Memory":
    st.header("What this project remembers")
    st.write("Decisions keep their sources and older versions. Procedures are approved instructions; attempts record drafts and reported outcomes.")
    key = st.selectbox("Decision", list(ALLOWED), key="decision_key")
    with st.form("decision_form"):
        value = st.selectbox("Value", sorted(ALLOWED[key]), key="decision_value_" + key)
        if st.form_submit_button("Save decision"):
            p = {"key": key, "value": value}
            execute("decision", p, lambda rid: actions.mutate(service, rid, "decision", p))
    for key, did in state["decisions"].items():
        d = state["versions"][did]
        with st.container(border=True):
            st.write(f"**{key}** → {d['value']}")
            st.caption("User assertion: " + d["source"]["passage"])
            old = d.get("supersedes")
            while old:
                previous = state["versions"][old]
                st.caption("Earlier: " + previous["value"] + " · " + previous["source"]["passage"])
                old = previous.get("supersedes")
    st.subheader("Approved procedures")
    for name, proc in state["procedures"].items():
        with st.expander(name):
            for index, step in enumerate(proc["steps"], 1):
                st.write(f"{index}. {step}")
            st.caption("User approval: " + proc["source"]["passage"])
    with st.expander("Approve a procedure"):
        with st.form("procedure_form"):
            name = st.text_input("Procedure name", key="procedure_name")
            lines = st.text_area("One step per line", key="procedure_steps")
            approved = st.checkbox("I approve these steps for tasks that declare this procedure.", key="procedure_approve")
            if st.form_submit_button("Save approved procedure"):
                if not approved:
                    st.error("Confirm approval before saving the procedure.")
                else:
                    p = {"name": name.strip(), "steps": [x.strip() for x in lines.splitlines() if x.strip()], "approved": True}
                    execute("procedure", p, lambda rid: actions.mutate(service, rid, "procedure", p))
    st.subheader("Recent attempts")
    for attempt in reversed(list(state["attempts"].values())[-10:]):
        with st.expander(state["tasks"][attempt["task"]]["title"] + " · " + attempt["source"]["provenance"]):
            draft_view(attempt["content"])
            st.caption("Recorded stale: " + str(attempt["stale"]))
    with st.expander("Evidence and saved requests"):
        st.json({"requests": state["requests"], "reviews": state["reviews"]})

elif page == "Benchmark":
    st.header("Evaluate your memory system")
    st.write("Use your chosen public benchmark dataset. No sample conversations are loaded into your workspace.")
    st.markdown("The runner imports timestamped histories, generates live answers, and exports predictions for the benchmark evaluator. Use BENCHMARKS.md for the complete commands and comparison rules.")
    st.caption("No public benchmark score or leaderboard placement has been claimed.")
    st.link_button("Original LongMemEval dataset and evaluator", "https://github.com/xiaowu0162/LongMemEval")
    st.link_button("LongMemEval-V2 leaderboard protocol", "https://github.com/xiaowu0162/LongMemEval-V2#submitting-to-leaderboard")
