from pathlib import Path

from streamlit.testing.v1 import AppTest

from app import actions
from app.domain import ready
from tests.fixtures import seed


def button(app, label):
    return next(b for b in app.button if b.label == label)


def loaded(service, monkeypatch, model=None):
    from tests.fakes import DemoModel
    monkeypatch.setattr(actions, "connect", lambda *_: service)
    monkeypatch.setattr(actions, "Gemini", model or DemoModel)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=30)
    app.run()
    app.radio(key="plan_mode").set_value("Plan saved tasks").run()
    app.text_area(key="plan_prompt").set_value("Continue my saved work.")
    assert not app.exception
    return app


def test_ui_plan_help_completion_correction_and_review(service, monkeypatch):
    seed(service)
    app = loaded(service, monkeypatch)
    button(app, "Create plan").click().run()
    assert not app.exception
    assert len(service.store.read()["handoffs"]) == 1
    button(app, "Get Helper steps").click().run()
    assert not app.exception
    assert service.store.read()["tasks"]["interface"]["status"] == "in_progress"
    app.text_area(key="outcome").set_value("I performed and checked the synthetic interface work.")
    app.checkbox(key="completion_confirm").check()
    button(app, "Record completed work").click().run()
    assert not app.exception
    assert service.store.read()["tasks"]["interface"]["status"] == "completed"
    app.radio(key="page").set_value("Memory").run()
    app.selectbox(key="decision_value_interface_framework").set_value("Streamlit")
    button(app, "Save decision").click().run()
    assert not app.exception
    result = service.store.read()["tasks"]["interface"]["result"]
    assert service.store.read()["results"][result]["review_state"] == "requires_review"
    app.radio(key="page").set_value("Workspace").run()
    app.checkbox(key="review_confirm").check()
    button(app, "Save review").click().run()
    assert not app.exception
    assert service.store.read()["results"][result]["review_state"] == "valid"


def test_ui_reruns_and_failed_confirmation_do_not_duplicate_work(service, monkeypatch):
    seed(service)
    app = loaded(service, monkeypatch)
    button(app, "Create plan").click().run()
    button(app, "Get Helper steps").click().run()
    before = service.store.read()
    app.run()
    assert service.store.read() == before
    app.text_area(key="outcome").set_value("I have a draft.")
    button(app, "Record completed work").click().run()
    assert not app.exception
    assert app.error
    assert service.store.read()["tasks"]["interface"]["result"] is None
    # Dependent dropdown values update when the field changes outside the form.
    app.radio(key="page").set_value("Memory").run()
    app.selectbox(key="decision_key").set_value("response_style").run()
    app.selectbox(key="decision_value_response_style").set_value("short")
    button(app, "Save decision").click().run()
    assert not app.exception
    s = service.store.read()
    assert s["versions"][s["decisions"]["response_style"]]["value"] == "short"


def test_synthetic_evaluation_uses_zero_model_calls(service):
    from benchmarks.contracts import run_checks
    report = run_checks(service.store)
    assert report["passed"] == report["planned_checks"] == 14, report
    assert report["model_calls"] == 0 and not report["external_benchmark"]


def test_empty_workspace_has_no_samples_and_plans_user_input(service, monkeypatch):
    app = loaded(service, monkeypatch)
    assert not app.toggle
    assert not service.store.read()["tasks"]
    assert not service.store.read()["messages"]
    labels = [b.label for b in app.button]
    assert "Load example tasks" not in labels and "Create fresh practice project" not in labels
    app.radio(key="plan_mode").set_value("Start a new task").run()
    app.text_area(key="plan_prompt").set_value("Review the report I wrote today.")
    button(app, "Create plan").click().run()
    assert not app.exception
    state = service.store.read()
    assert len(state["tasks"]) == len(state["handoffs"]) == 1
    assert next(iter(state["tasks"].values()))["title"] == "Review the report I wrote today."
    assert any(m["text"] == "Review the report I wrote today." for m in state["messages"].values())
    snapshot = service.store.read()
    app.radio(key="page").set_value("Benchmark").run()
    assert not app.exception
    assert service.store.read() == snapshot


def test_ui_helper_retry_resumes_original_claim_and_request(service, monkeypatch):
    from tests.fakes import DemoModel
    class Interrupted(DemoModel):
        failures = 1
        def generate(self, role, context):
            if role == "helper" and Interrupted.failures:
                Interrupted.failures -= 1
                raise TimeoutError("Simulated interrupted provider call")
            return super().generate(role, context)
    seed(service)
    app = loaded(service, monkeypatch, model=Interrupted)
    button(app, "Create plan").click().run()
    button(app, "Get Helper steps").click().run()
    assert app.error and not app.exception
    state = service.store.read()
    old_claim = state["tasks"]["interface"]["claim"]
    helper_id = next(rid for rid, r in state["requests"].items() if r["input"]["role"] == "helper")
    button(app, "Refresh memory").click().run()
    button(app, "Retry original Helper request").click().run()
    assert not app.exception
    state = service.store.read()
    assert state["tasks"]["interface"]["claim"] == old_claim
    assert state["tasks"]["interface"]["version"] == 2
    assert state["requests"][helper_id]["calls"] == 2
    assert len(state["requests"]) == 2
    assert len(state["attempts"]) == 1
