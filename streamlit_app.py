"""Continuity: AI-first Project Assistant with Live Multi-Model Router & FalkorDB Memory."""
from __future__ import annotations

import json
import os
import re
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app import actions
from app.domain import ALLOWED, canonical, current_inputs, digest, ready, satisfied, valid_bundle
from app.models import ModelRouter
from app.service import new_id

load_dotenv()
st.set_page_config(page_title="Continuity · AI Agent Memory", page_icon="⚡", layout="wide")

# Modern, elegant styling
st.markdown("""<style>
.block-container {max-width:1250px;padding-top:1.5rem}
div[data-testid="stMetric"] {background:#f4fbf8;border:1px solid #d1fae5;padding:1rem;border-radius:12px}
div[data-testid="stMetric"] label, div[data-testid="stMetric"] div {color:#064e3b}
.router-badge {display:inline-block;padding:4px 10px;border-radius:20px;font-size:0.82rem;font-weight:600;background:#e0f2fe;color:#0369a1;border:1px solid #bae6fd;margin-bottom:8px}
.chip-btn {display:inline-block;padding:6px 12px;margin:4px 4px 8px 0;background:#f1f5f9;border-radius:16px;border:1px solid #cbd5e1;font-size:0.82rem;color:#334155;cursor:pointer}
.chip-btn:hover {background:#e2e8f0}
.chat-card {background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;padding:12px;margin:8px 0}
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


def execute(action, inputs, fn, original_request_id=None, rerun=True):
    key, rid = request_id(action, inputs)
    if original_request_id is not None:
        rid = original_request_id
        st.session_state["pending_requests"][key] = rid
    st.caption("Request ID: " + rid)
    try:
        with st.spinner("Checking memory and reasoning with model router…"):
            receipt = fn(rid)
        st.session_state["last_receipt"] = {"scope": [tenant, project], "receipt": receipt}
        if receipt.get("handoff"):
            st.session_state["recent_handoff"] = receipt["handoff"]
        st.session_state["pending_requests"].pop(key, None)
        if receipt.get("accepted") is False:
            flash("Saved as a stale attempt. " + receipt.get("reason", "Inspect current inputs and replan."), "warning")
        if rerun:
            flash("Saved. Project state and memory have been refreshed.")
        return receipt
    except Exception as exc:
        st.error(actions.error_message(exc))
        st.caption("Retry with the same inputs to retain this request ID. Changed inputs start a new request.")
        return None


def draft_view(content):
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        st.write(content)
        return
    st.write(data.get("summary", ""))
    for index, step in enumerate(data.get("steps", []), 1):
        st.write(f"{index}. {step}")


# Sidebar Scope and Navigation
st.sidebar.title("⚡ Continuity")
st.sidebar.caption("Agent Memory & Multi-Model Coordination")

if st.session_state.get("interface_version") != "live-v4":
    st.session_state.clear()
    st.session_state["interface_version"] = "live-v4"
st.session_state.setdefault("scope", {"tenant": "userA", "project": "my_project"})
scope = st.session_state["scope"]

with st.sidebar.form("scope_form"):
    tenant_input = st.text_input("User", value=scope["tenant"])
    project_input = st.text_input("Project", value=scope["project"])
    if st.form_submit_button("Open project"):
        st.session_state["scope"] = {"tenant": tenant_input.strip(), "project": project_input.strip()}
        st.session_state.pop("chat_thread", None)
        st.session_state.pop("pending_chat", None)
        st.rerun()

tenant, project = scope["tenant"], scope["project"]
st.sidebar.caption("Local profile selector; this is not a login system.")

# Model Router Selector in Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Model Router")
model_options = {
    "Auto-Router (Gemini + OpenRouter Fallbacks)": ("auto", None),
    "NVIDIA Nemotron 3.5 Super VL (OpenRouter Free)": ("openrouter", "nvidia/nemotron-3.5-super-vl:free"),
    "Google Gemini 3.8 Flash (Preferred)": ("gemini", "gemini-3.8-flash"),
    "OpenRouter Free Meta-Router": ("openrouter", "openrouter/free"),
}
selected_model_label = st.sidebar.selectbox("Active Provider", list(model_options.keys()), index=0)
pref_provider, pref_model = model_options[selected_model_label]
active_router = actions.get_model(model_name=pref_model, preferred_provider=None if pref_provider == "auto" else pref_provider)
st.sidebar.caption("Your AI provider receives your message and the relevant saved memories. Failed calls use a bounded fallback budget.")

st.sidebar.caption("🛡️ Standby fallback chain: Gemini ➔ NVIDIA Nemotron ➔ Nemotron Lightning ➔ OpenRouter Free.")

page = st.sidebar.radio("Explore", ["Workspace", "Memory", "Benchmark"], label_visibility="collapsed", key="page")

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
st.caption(f"{project} / {tenant} · FalkorDB Graph Memory · Multi-Model Router Active")

if st.session_state.get("notice"):
    notice = st.session_state.pop("notice")
    if isinstance(notice, str):
        st.success(notice)
    else:
        getattr(st, notice["level"])(notice["message"])

available = ready(state)
review_tasks = [t for t in state["tasks"].values() if t.get("result") and state["results"][t["result"]]["review_state"] == "requires_review"]

# ----------------- WORKSPACE PAGE -----------------
if page == "Workspace":
    # Metrics Bar
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ready to start", len(available))
    m2.metric("In progress", sum(t["status"] == "in_progress" for t in state["tasks"].values()))
    m3.metric("Needs review", len(review_tasks))
    m4.metric("Valid completed", sum(satisfied(state, tid) for tid in state["tasks"]))

    tab_chat, tab_board = st.tabs(["💬 AI Assistant Chat", "📋 Structured Task Board"])

    # Persistent conversational UI: every successful turn comes from FalkorDB.
    with tab_chat:
        from app.conversation import chat, ordered_turns
        st.caption("Talk normally. Useful facts, events and routines are saved with their source. All three agents share this project's memory.")
        threads = list(dict.fromkeys(t["thread"] for t in ordered_turns(state)))
        if st.button("New conversation", key="new_conversation"):
            st.session_state["chat_thread"] = "session_" + new_id()[:12]
            st.session_state.pop("pending_chat", None)
        selected_thread = st.session_state.get("chat_thread", threads[-1] if threads else "main")
        if selected_thread not in threads:
            threads.append(selected_thread)
        st.session_state.setdefault("chat_thread", selected_thread)
        thread = st.selectbox("Conversation", threads, index=None, key="chat_thread")
        agent_role = st.selectbox("Talk to", ["Assistant", "Planner", "Helper"], key="chat_agent")
        turns = ordered_turns(state, thread)
        if not turns:
            st.info("Start a conversation below. A new conversation keeps the saved memories from this project.")
        for turn in turns[-40:]:
            with st.chat_message("user"):
                st.write(state["messages"][turn["message"]]["text"])
            with st.chat_message("assistant"):
                st.markdown(turn["reply"])
                st.caption(turn["agent_role"] + " - " + turn["provider"])
                if turn["saved"]:
                    st.caption("Saved " + str(len(turn["saved"])) + " sourced memories.")
                evidence_ids = list(dict.fromkeys(turn["saved"] + turn["citations"]))
                if evidence_ids:
                    with st.expander("Memory and sources used for this answer"):
                        for vid in evidence_ids:
                            fact = state.get("memory_versions", {}).get(vid)
                            if fact:
                                current = state.get("memory_slots", {}).get(fact["slot"]) == vid
                                st.write(f"**{fact['subject']} / {fact['relation']} / {fact['value']}**")
                                st.caption(fact["kind"] + (" - current" if current else " - historical, updated later"))
                                st.write("You said: " + fact["source"]["passage"])
                if turn["suggested_task"] and not turn.get("handoff"):
                    st.write("Suggested task: " + turn["suggested_task"])
                    if st.button("Create this plan", key="chat_plan_" + turn["id"]):
                        from app.service import operation
                        rid = operation(turn["id"], "plan_from_chat")
                        receipt = execute("new_plan", turn["id"], lambda _: actions.plan_new_task(service, rid, turn["suggested_task"], model=active_router), original_request_id=rid, rerun=False)
                        if receipt:
                            service.command("chat_link", {"turn": turn["id"], "handoff": receipt["handoff"]}, operation(turn["id"], "link_plan"))
                            st.rerun()
                if turn.get("handoff"):
                    hid = turn["handoff"]
                    h = state["handoffs"][hid]
                    st.write("Saved plan: " + h["objective"])
                    task = state["tasks"][h["bundle"]["task"]]
                    usable = (h["status"] == "saved" and task["status"] == "pending" and valid_bundle(state, h["bundle"]))
                    if usable and st.button("Get Step-by-Step Helper Guide", key="chat_help_" + turn["id"]):
                        execute("help", hid, lambda rid: actions.workflow(service, rid, "helper", "Give practical steps using the latest shared memories.", handoff=hid, model=active_router))
                    if h.get("draft"):
                        draft_view(state["attempts"][h["draft"]]["content"])
                        st.caption("Suggested steps only. Use the task board to report work you actually performed.")
                    if h["status"] == "claimed" and not h.get("draft"):
                        st.info("Helper was interrupted. Resume the original request in the task board.")

        pending = st.session_state.get("pending_chat")
        retry = False
        if pending and pending["scope"] == [tenant, project, thread]:
            st.warning("Your last message has not received a saved answer: " + pending["text"])
            retry = st.button("Retry this message", key="retry_chat")
        text = st.chat_input("Message Continuity normally...")
        if text or retry:
            if retry:
                text, agent_role = pending["text"], pending["agent_role"]
            st.session_state["pending_chat"] = {"scope": [tenant, project, thread], "text": text, "agent_role": agent_role}
            receipt = execute("chat", [thread, agent_role, text], lambda rid: chat(service, rid, text, thread, agent_role, active_router), rerun=False)
            if receipt:
                st.session_state.pop("pending_chat", None)
                st.rerun()

    # ----------------- TAB 2: CLASSIC STRUCTURED TASK BOARD (TEST COMPATIBLE) -----------------
    with tab_board:
        st.write("Full structured board for manual task management and review workflows.")
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
                        execute("new_plan", inputs, lambda rid: actions.plan_new_task(service, rid, prompt, required_decisions, prior_tasks, approved_procedures, model=active_router))
                    else:
                        execute("plan", prompt, lambda rid: actions.workflow(service, rid, "planner", prompt, model=active_router))

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
                    for vid in h.get("memory_inputs", {}).values():
                        fact = state["memory_versions"][vid]
                        st.write(f"**{fact['subject']} / {fact['relation']}:** {fact['value']}")
                        st.caption("User source: " + fact["source"]["passage"])
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
                    if attempt.get("memory_inputs"):
                        with st.expander("Shared memory read by Helper"):
                            for vid in attempt["memory_inputs"].values():
                                fact = state["memory_versions"][vid]
                                st.write(f"{fact['subject']} / {fact['relation']}: {fact['value']}")
                                st.caption("User source: " + fact["source"]["passage"])
                    st.caption("Assistant draft · " + ("inputs changed" if not good or attempt["stale"] else "inputs current"))
                elif st.button("Get Helper steps" if h["status"] == "saved" else "Retry original Helper request", disabled=not usable, key="help", type="primary"):
                    if h["status"] == "claimed":
                        try:
                            saved = actions.helper_request(service, selected)
                            execute("helper_resume", saved, lambda _: actions.resume_helper(service, saved, model=active_router), original_request_id=saved["request_id"])
                        except Exception as exc:
                            st.error(actions.error_message(exc))
                    else:
                        execute("help", selected, lambda rid: actions.workflow(service, rid, "helper", "Suggest practical steps using this saved plan.", handoff=selected, model=active_router))
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


# ----------------- MEMORY PAGE -----------------
elif page == "Memory":
    st.header("What this project remembers (FalkorDB Graph)")
    st.write("Decisions keep their sources and older versions. Procedures are approved instructions; attempts record drafts and reported outcomes.")

    st.subheader("What Continuity remembers")
    current_facts = [state["memory_versions"][v] for v in state.get("memory_slots", {}).values()]
    if not current_facts:
        st.caption("No conversational memories yet. Tell the assistant something about yourself or your project.")
    else:
        graph_lines = ["digraph Memory { rankdir=LR;"]
        for fact in current_facts:
            graph_lines.append(json.dumps(fact["subject"]) + " -> " + json.dumps(fact["value"]) + " [label=" + json.dumps(fact["relation"].replace("_", " ")) + "];")
            with st.expander(fact["subject"] + " / " + fact["relation"] + " / " + fact["value"]):
                st.write("Type: " + fact["kind"])
                st.write("You said: " + fact["source"]["passage"])
                st.caption("Saved: " + fact["recorded_at"])
                previous = fact.get("supersedes")
                while previous:
                    old = state["memory_versions"][previous]
                    st.write("Earlier value: " + old["value"])
                    st.caption("Earlier source: " + old["source"]["passage"])
                    previous = old.get("supersedes")
        graph_lines.append("}")
        st.graphviz_chart("\n".join(graph_lines))
    st.markdown("---")
    tab_decisions, tab_graph = st.tabs(["🏛️ Decisions & Procedures", "🔍 Live FalkorDB Cypher Explorer"])

    with tab_decisions:
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

    with tab_graph:
        st.subheader("FalkorDB Graph Live Traversal")
        st.caption("Direct graph queries against the active FalkorDB instance.")
        cypher_templates = [
            "MATCH (t:Task) RETURN t.id AS TaskID, t.key AS Key",
            "MATCH (t:Task)-[:DEPENDS_ON]->(d:Task) RETURN t.id AS Task, d.id AS DependsOn",
            "MATCH (t:Task)-[:REQUIRES_DECISION]->(s:DecisionSlot)-[:CURRENT]->(v:DecisionVersion) RETURN t.id AS Task, s.key AS DecisionKey, v.data AS Version",
            "MATCH (r:Result)-[:BASED_ON]->(v:DecisionVersion) RETURN r.id AS Result, v.data AS BasedOnDecision",
            "MATCH (n:Record) RETURN labels(n)[1] AS RecordType, count(n) AS TotalNodes",
        ]
        chosen_cypher = st.selectbox("Choose a Cypher query template or edit below:", cypher_templates)
        custom_query = st.text_area("Cypher Query", value=chosen_cypher, height=80)
        if st.button("Execute Cypher Query", type="primary"):
            try:
                res = service.store.graph.ro_query(custom_query)
                header = [col[1] for col in res.header] if res.header else []
                df = pd.DataFrame(res.result_set, columns=header if header else None)
                st.success(f"Query returned {len(res.result_set)} records in {getattr(res, 'run_time_ms', 0):.2f}ms")
                st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.error(f"Cypher execution error: {e}")


# ----------------- BENCHMARK PAGE -----------------
elif page == "Benchmark":
    st.header("Memory & Model Router Evaluation")
    st.write("Comparative evaluation of memory retrieval across Google Gemini and OpenRouter free models.")

    b1, b2 = st.columns(2)
    with b1:
        st.subheader("Deterministic Contract Checks")
        st.caption("14 synthetic checks verifying FalkorDB atomic transactions, replay deduplication, and review invalidation.")
        if st.button("Run 14 Contract Checks Now", type="primary"):
            from benchmarks.contracts import run_checks
            with st.spinner("Running contract checks against FalkorDB..."):
                rep = run_checks()
            st.success(f"Pass Rate: {rep['pass_rate'] * 100:.1f}% ({rep['passed']}/{rep['planned_checks']} checks passed in {rep['elapsed_seconds']:.3f}s)")
            st.json(rep)

    with b2:
        st.subheader("LongMemEval QA Benchmark")
        st.caption("Live comparison between Google Gemini and OpenRouter NVIDIA Nemotron on timestamped conversation memory.")
        st.info("Earlier 3/3 results used three synthetic test questions and an unverified judge. They are not public benchmark scores.")
        st.write("Use the verified commands in docs/TESTING_GUIDE.md to create fresh results. No scores are hardcoded here.")

    st.markdown("---")
    st.subheader("Leaderboard and Dataset Protocol")
    st.markdown("The runner imports timestamped histories, generates live answers, and exports predictions for the benchmark evaluator. Use `docs/BENCHMARKS.md` for complete commands.")
    st.link_button("Official LongMemEval Dataset Repository", "https://github.com/xiaowu0162/LongMemEval")
