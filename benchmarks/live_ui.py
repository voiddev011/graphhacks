"""One real-model Streamlit AppTest turn in a temporary profile (no browser screenshot)."""
import json
import re
import uuid
from pathlib import Path
from dotenv import load_dotenv
from streamlit.testing.v1 import AppTest
from app.repository import FalkorStore

def run(provider_label="OpenRouter Free Meta-Router", output="reports/final-live-ui-v2.json"):
    load_dotenv()
    tenant="ui_live_"+uuid.uuid4().hex
    store=FalkorStore(tenant,"chat_ui_check")
    report={"kind":"live Streamlit AppTest smoke", "visual_browser_test":False,"checks":[]}
    def check(name,condition):
        report["checks"].append({"check":name,"passed":bool(condition)})
        if not condition: raise AssertionError(name)
    try:
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"),default_timeout=180)
        app.session_state["interface_version"]="live-v4"
        app.session_state["scope"]={"tenant":tenant,"project":"chat_ui_check"}
        app.run()
        check("Empty real profile loads without sample tasks",not app.exception and not store.read()["tasks"])
        provider=next(w for w in app.selectbox if w.label=="Active Provider")
        provider.set_value(provider_label).run()
        app.chat_input[0].set_value("My name is Quinn and I own 2 restaurants.").run()
        check("Ordinary chat obtains a real saved response",not app.exception and bool(store.read().get("chat_turns")))
        state=store.read()
        values={state["memory_versions"][v]["value"] for v in state.get("memory_slots",{}).values()}
        check("UI chat stores sourced personal facts",any(v.casefold()=="quinn" for v in values) and any(re.fullmatch(r"2(?: restaurants?)?",v.casefold()) for v in values))
        for b in app.button:
            if b.label=="New conversation": b.click().run(); break
        check("New conversation retains graph memory",len(store.read().get("memory_slots",{}))>=2 and not app.exception)
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"),default_timeout=60)
        app.session_state["interface_version"]="live-v4"
        app.session_state["scope"]={"tenant":tenant,"project":"chat_ui_check"}
        app.run()
        app.radio(key="page").set_value("Memory").run()
        check("Reloaded Memory page renders sources and connected graph",not app.exception and any("Quinn" in e.label for e in app.expander))
        report["status"]="passed"
    except Exception as exc:
        report["status"]="failed"; report["error_type"]=type(exc).__name__
        if isinstance(exc,AssertionError):report["failed_check"]=str(exc)
    finally:
        state=store.read()
        report["provider_calls"]=sum(r["calls"] for r in state["requests"].values())
        report["memory_evidence"]=list(state.get("memory_versions",{}).values())
        report["turn_evidence"]=list(state.get("chat_turns",{}).values())
        store.graph.delete(); report["test_graph_deleted"]=True
        Path(output).write_text(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    report=run();print(json.dumps(report,indent=2));raise SystemExit(0 if report["status"]=="passed" else 1)
