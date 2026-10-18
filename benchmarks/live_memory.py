"""Bounded live end-to-end smoke test, not a public benchmark or leaderboard score.

Uses a temporary tenant graph and real model calls. Never seeds user workspaces.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from app import actions
from app.conversation import chat
from app.models import ModelRouter
from app.repository import FalkorStore
from app.service import Service


def run(model_name="openrouter/free", output="reports/final-live-memory.json"):
    tenant="live_check_"+uuid.uuid4().hex
    store=FalkorStore(tenant,"memory_check")
    service=Service(store)
    model=ModelRouter(model_name=model_name)
    report={"kind":"live synthetic end-to-end memory smoke test", "public_benchmark":False,
        "requested_model":model_name,"checks":[],"provider_calls":0,"status":"running"}
    started=time.perf_counter()
    def record(name,condition):
        report["checks"].append({"check":name,"passed":bool(condition)})
        print(("PASS: " if condition else "FAIL: ") + name, flush=True)
        if not condition: raise AssertionError(name)
    def turn(text,thread,role="Assistant"):
        receipt=chat(service,uuid.uuid4().hex,text,thread=thread,agent_role=role,model=model)
        return store.read()["chat_turns"][receipt["turn"]]
    try:
        first=turn("My name is Jack and I own 2 restaurants.","first")
        state=store.read()
        facts=[state["memory_versions"][v] for v in state.get("memory_slots",{}).values()]
        record("Natural message stores Jack and restaurant count with exact user sources",
            {"Jack","2"} <= {f["value"] for f in facts})
        count=next(f for f in facts if f["value"]=="2")
        code=("from app.repository import FalkorStore; import json; "
            f"s=FalkorStore({tenant!r},'memory_check'); "
            "print(json.dumps([m['value'] for m in s.conversation_context('What do you know about me?')[1]]))")
        process=subprocess.run([sys.executable,"-B","-c",code],capture_output=True,text=True,check=True,timeout=30)
        record("Fresh Python process recalls stored facts",{"Jack","2"} <= set(json.loads(process.stdout)))
        recall=turn("What is my name and how many restaurants do I own?","second","Helper")
        record("Helper recalls another conversation's facts with graph citations",
            "jack" in recall["reply"].lower() and ("2" in recall["reply"] or "two" in recall["reply"].lower()) and bool(recall["citations"]))
        turn("Correction: I now own 3 restaurants.","second")
        state=store.read()
        current=state["memory_versions"][state["memory_slots"][count["slot"]]]
        record("Correction supersedes 2 with 3 and preserves history",
            ("3" in current["value"] or "three" in current["value"].lower()) and current["supersedes"] is not None and state["memory_versions"][current["supersedes"]]["value"]=="2")
        latest=turn("How many restaurants do I own now?","third","Planner")
        record("New Planner conversation uses the correction",
            ("3" in latest["reply"] or "three" in latest["reply"].lower()) and current["id"] in latest["citations"])
        plan=actions.plan_new_task(service,uuid.uuid4().hex,"Prepare a weekly budget for my restaurants",model=model)
        h=store.read()["handoffs"][plan["handoff"]]
        record("Planner saves graph evidence in its handoff",current["id"] in h["memory_inputs"].values())
        draft=actions.workflow(Service(store),uuid.uuid4().hex,"helper",
            "Suggest steps for the weekly budget and explicitly state the restaurant count from current shared memory.",handoff=plan["handoff"],model=model)
        state=store.read(); attempt=state["attempts"][draft["attempt"]]
        record("Helper receives the handoff and latest memory without falsely completing work",
            draft["accepted"] and not draft["completed"] and current["id"] in attempt["memory_inputs"].values())
        other=FalkorStore(tenant,"other_project")
        record("Another project cannot see these memories",not other.conversation_context("Who am I?")[1])
        report["status"]="passed"
    except Exception as exc:
        report["status"]="failed"
        report["error_type"]=type(exc).__name__
        if isinstance(exc,AssertionError): report["failed_check"]=str(exc)
    finally:
        state = store.read()
        report["provider_calls"]=sum(r["calls"] for r in state["requests"].values())
        report["memory_evidence"] = list(state.get("memory_versions", {}).values())
        report["turn_evidence"] = list(state.get("chat_turns", {}).values())
        report["served_by"]=model.get_status()
        report["elapsed_seconds"]=round(time.perf_counter()-started,3)
        store.graph.delete()
        report["test_graph_deleted"]=True
        Path(output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",default="openrouter/free")
    parser.add_argument("--out",default="reports/final-live-memory.json")
    args=parser.parse_args()
    report=run(args.model,args.out)
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report["status"]=="passed" else 1)
