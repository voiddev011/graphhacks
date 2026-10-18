import json
import httpx
import pytest
from app.models import NVIDIAProvider,ModelRouter


def test_nvidia_uses_own_endpoint_key_and_structured_request(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY","nvidia-test-key")
    monkeypatch.setenv("OPENROUTER_API_KEY","different-openrouter-key")
    real_client=httpx.Client
    def handler(request):
        assert str(request.url)==NVIDIAProvider.ENDPOINT
        assert request.headers['Authorization']=='Bearer nvidia-test-key'
        body=json.loads(request.content)
        assert body['model']==NVIDIAProvider.DEFAULT_MODEL
        assert body['stream'] is False and body['reasoning_effort']=='none'
        assert 'reasoning' not in body and body['response_format']['type']=='json_schema'
        return httpx.Response(200,json={'model':'actual-nvidia-model','choices':[{'message':{'content':json.dumps(
            {'reply':'Hello','memories':[],'citations':[],'suggested_task':''})}}],'usage':{'total_tokens':12}})
    monkeypatch.setattr('app.models.httpx.Client',lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs))
    model=NVIDIAProvider()
    answer,usage=model.generate('chat',{'current_message':'Hello'})
    assert answer['reply']=='Hello' and usage['total_tokens']==12 and model.served_model=='actual-nvidia-model'


def test_nvidia_key_is_required_independently(monkeypatch):
    monkeypatch.delenv('NVIDIA_API_KEY',raising=False)
    monkeypatch.setenv('OPENROUTER_API_KEY','not-a-nvidia-key')
    with pytest.raises(ValueError,match='NVIDIA_API_KEY'):
        NVIDIAProvider()


def test_nvidia_router_records_actual_model_and_reserves_once(monkeypatch):
    monkeypatch.setenv('NVIDIA_API_KEY','test-only')
    calls=[]
    class Provider:
        DEFAULT_MODEL='default-nvidia-model'
        served_model='served-nvidia-model'
        def __init__(self,**kwargs):pass
        def generate(self,*args):return {'reply':'Hello'},None
    monkeypatch.setattr('app.models.NVIDIAProvider',Provider)
    router=ModelRouter(preferred_provider='nvidia',model_name='requested-nvidia-model')
    assert router._build_chain()[0]=={'provider':'nvidia','model':'requested-nvidia-model'}
    router.generate_with_budget('chat',{},lambda:calls.append(1))
    assert calls==[1] and router.last_provider=='nvidia' and router.last_model=='served-nvidia-model'


def test_fixed_benchmark_nvidia_does_not_use_openrouter(monkeypatch,tmp_path):
    from benchmarks.locomo import FixedModel,Budget
    calls=[]
    class Provider:
        def __init__(self,name,timeout):calls.append((name,timeout))
        def generate(self,*args):return {'reply':'ok'},None
    monkeypatch.setattr('benchmarks.locomo.NVIDIAProvider',Provider)
    manifest={'provider_calls':0,'attempts':[]}
    budget=Budget(tmp_path/'manifest.json',manifest,1,1)
    FixedModel('nim:nvidia/test-model',budget,'qa').generate('chat',{})
    assert calls==[('nvidia/test-model',60)] and manifest['provider_calls']==1


def test_nvidia_judge_uses_direct_endpoint_and_fixed_budget(monkeypatch,tmp_path):
    from benchmarks.locomo import judge_batch,Budget
    monkeypatch.setenv('NVIDIA_API_KEY','judge-nvidia-key')
    real_client=httpx.Client
    def handler(request):
        assert str(request.url)==NVIDIAProvider.ENDPOINT
        assert request.headers['Authorization']=='Bearer judge-nvidia-key'
        payload=json.loads(request.content)
        assert payload['model']=='nvidia/test-model' and payload['stream'] is False
        assert payload['response_format']['type']=='json_schema'
        return httpx.Response(200,json={'model':'reported-model','choices':[{'message':{'content':json.dumps(
            {'verdicts':[{'id':'graph:q1','correct':False,'reason':'Incorrect'}]})}}]})
    monkeypatch.setattr('benchmarks.locomo.httpx.Client',lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs))
    budget=Budget(tmp_path/'manifest.json',{'provider_calls':0,'attempts':[]},1,1)
    verdicts,actual=judge_batch([{'method':'graph','id':'q1','question':'Q','reference':'R','answer':'A'}],
        'nim:nvidia/test-model',budget)
    assert verdicts['graph:q1']['correct'] is False and actual=='reported-model'
    assert budget.manifest['provider_calls']==1


def test_provider_error_preserves_quota_reason_but_redacts_key(monkeypatch):
    monkeypatch.setenv('NVIDIA_API_KEY','secret-nvidia-key')
    real_client=httpx.Client
    def handler(request):
        return httpx.Response(429,json={'error':{'message':'daily quota exceeded for secret-nvidia-key'}})
    monkeypatch.setattr('app.models.httpx.Client',lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs))
    with pytest.raises(ValueError) as error:
        NVIDIAProvider().generate('chat',{})
    assert 'secret-nvidia-key' not in str(error.value)
    assert '429' in str(error.value) and 'daily quota' in str(error.value)
