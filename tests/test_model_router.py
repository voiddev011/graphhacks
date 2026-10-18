import pytest
from app.models import ModelRouter, Plan, Help, clean_json_output

def test_clean_json_output():
    raw_md = '```json\n{"task_id": "t1", "objective": "test"}\n```'
    parsed = clean_json_output(raw_md)
    assert parsed == {"task_id": "t1", "objective": "test"}

    raw_text = 'Sure, here is the output:\n{"task_id": "t2", "objective": "test 2"}\nHope this helps!'
    parsed2 = clean_json_output(raw_text)
    assert parsed2 == {"task_id": "t2", "objective": "test 2"}

def test_router_chain_construction():
    router = ModelRouter(preferred_provider="openrouter", model_name="nvidia/nemotron-3.5-super-vl:free")
    chain = router._build_chain()
    assert chain[0]["provider"] == "openrouter"
    assert chain[0]["model"] == "nvidia/nemotron-3.5-super-vl:free"
    # Ensure fallbacks exist
    assert any(c["provider"] == "gemini" for c in chain)

def test_router_seamless_fallback(monkeypatch):
    router = ModelRouter()
    
    # Simulate first candidate failing, second candidate succeeding
    call_counts = {"attempts": 0}

    class MockFailingProvider:
        def generate(self, role, context):
            call_counts["attempts"] += 1
            raise ValueError("Rate limit 429 quota exhausted")

    class MockWorkingProvider:
        def generate(self, role, context):
            call_counts["attempts"] += 1
            return {"task_id": "task_1", "objective": "Resume work seamlessly"}, None

    def mock_build_chain():
        return [
            {"provider": "gemini", "model": "failing-model"},
            {"provider": "openrouter", "model": "standby-model"}
        ]

    monkeypatch.setattr(router, "_build_chain", mock_build_chain)

    def mock_provider_factory(candidate):
        if candidate["model"] == "failing-model":
            return MockFailingProvider()
        return MockWorkingProvider()

    # Test generation: should succeed without error
    # Patch GeminiProvider and OpenRouterProvider
    monkeypatch.setattr("app.models.GeminiProvider", lambda model_name: MockFailingProvider())
    monkeypatch.setattr("app.models.OpenRouterProvider", lambda model_name: MockWorkingProvider())
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy")
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy")

    result = router.generate("planner", {"eligible": ["task_1"]})
    assert result["task_id"] == "task_1"
    assert result["objective"] == "Resume work seamlessly"
    assert len(router.fallback_history) == 1
    assert router.fallback_history[0]["error"] == "ValueError"
    assert router.last_provider == "openrouter"


def test_selected_openrouter_prefers_free_standbys_before_google():
    chain=ModelRouter(model_name="nvidia/nemotron-3.5-super-vl:free",preferred_provider="openrouter")._build_chain()
    assert [c["provider"] for c in chain[:3]]==["openrouter"]*3
    assert all(c["model"]=="openrouter/free" or c["model"].endswith(":free") for c in chain[:3])
