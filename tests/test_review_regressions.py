import pytest
from app.models import ModelRouter
from app.domain import Rejected
from benchmarks import judge


def test_each_standby_reserves_a_slot(service, monkeypatch):
    monkeypatch.delenv('NVIDIA_API_KEY',raising=False)
    monkeypatch.setenv('GOOGLE_API_KEY','test-only')
    monkeypatch.setenv('OPENROUTER_API_KEY','test-only')
    calls=[]
    class Failed:
        def __init__(self, **kwargs): pass
        def generate(self,*args):
            calls.append(1)
            raise TimeoutError('sensitive provider text')
    monkeypatch.setattr('app.models.GeminiProvider',Failed)
    monkeypatch.setattr('app.models.OpenRouterProvider',Failed)
    service.begin('bounded-fallback','planner','test')
    router=ModelRouter()
    with pytest.raises(Rejected):
        service.generate('bounded-fallback',router,'planner',{})
    assert len(calls)==3
    assert service.store.read()['requests']['bounded-fallback']['calls']==3
    assert 'sensitive' not in str(router.get_status())


def test_local_judge_uses_model_verdict_not_substring(tmp_path, monkeypatch):
    import json
    data=tmp_path/'data.json'; predictions=tmp_path/'predictions.jsonl'
    data.write_text(json.dumps([{'question_id':'q','question':'Which database?','answer':'FalkorDB'}]))
    predictions.write_text(json.dumps({'question_id':'q','hypothesis':'Not FalkorDB; SQLite.'}))
    monkeypatch.setattr(judge,'judge_one',lambda *args: judge.Verdict(is_correct=False,reason='Contradiction'))
    path=judge.judge_predictions(data,predictions,'test-judge',1)
    assert json.loads(__import__('pathlib').Path(path).read_text())['autoeval_label']['label'] is False


def test_local_judge_failure_is_not_heuristic_success(tmp_path, monkeypatch):
    import json
    data=tmp_path/'data.json'; predictions=tmp_path/'predictions.jsonl'
    data.write_text(json.dumps([{'question_id':'q','question':'Which database?','answer':'FalkorDB'}]))
    predictions.write_text(json.dumps({'question_id':'q','hypothesis':'FalkorDB'}))
    def fail(*args): raise TimeoutError('private')
    monkeypatch.setattr(judge,'judge_one',fail)
    path=judge.judge_predictions(data,predictions,'test-judge',1)
    row=json.loads(__import__('pathlib').Path(path).read_text())
    assert row['autoeval_label']['label'] is False and row['judge_error']=='TimeoutError'


def test_comparison_rejects_failed_judging(tmp_path):
    import json
    from benchmarks.compare import compare
    (tmp_path / "manifest.json").write_text("{}")
    (tmp_path / "score.json").write_text(json.dumps({"evaluation_valid": False, "judge_errors": 1}))
    with pytest.raises(ValueError, match="Judge errors"):
        compare([tmp_path, tmp_path])


def test_openrouter_judge_uses_valid_user_role(monkeypatch):
    from benchmarks.judge import judge_one
    monkeypatch.setenv("OPENROUTER_API_KEY","test-key")
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"choices":[{"message":{"content":'{"is_correct": true, "reason":"Matches evidence"}'}}]}
    class Client:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,**kwargs):
            assert [m["role"] for m in kwargs["json"]["messages"]]==["system","user"]
            return Response()
    monkeypatch.setattr("benchmarks.judge.httpx.Client",Client)
    assert judge_one("openrouter/free","Which?","FalkorDB","FalkorDB").is_correct
