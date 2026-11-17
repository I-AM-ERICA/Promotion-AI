import base64
from concurrent.futures import ThreadPoolExecutor
import json
from io import BytesIO
import re
import time
import grpc
import httpx
import pytest
from fastapi.testclient import TestClient
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from PIL import Image
from america.ai.v1 import common_pb2, promotion_pb2 as pb, promotion_pb2_grpc as rpc
from promotion_assistant.api import create_app
from promotion_assistant.clova import ClovaDesigner, DemoDesigner, ProviderError
from promotion_assistant.config import Settings
from promotion_assistant.engine import Engine
from promotion_assistant.grpc_service import build_server
from promotion_assistant.models import Brief, Design, Revision
from promotion_assistant.renderer import Renderer
from promotion_assistant.storage import Repository, Conflict, NotFound


@pytest.fixture
def brief():
    return Brief(store={"store_id":"owner-1","name":"오후의 베이커리","region":"성수동"},
                 product="버터 소금빵",message="오늘의 작은 여유",price=3500,original_price=4000,period="11.20 – 11.27")


@pytest.fixture
def engine(tmp_path):
    settings=Settings(internal_key="test-key",demo=True,studio=True,data_dir=tmp_path,public_base_url="http://testserver")
    return Engine(settings,DemoDesigner(),Renderer(),Repository(tmp_path))


def mock_designs(brief):
    return DemoDesigner().designs(brief, time.monotonic()+10)


def clova_client(handler):
    return ClovaDesigner("secret-never-leak",httpx.Client(transport=httpx.MockTransport(handler)))


def success(content, finish="stop"):
    return httpx.Response(200,json={"status":{"code":"20000"},"result":{"finishReason":finish,"message":{"content":json.dumps(content,ensure_ascii=False)}}})


def test_clova_request_is_real_naver_schema_and_bearer(brief):
    def handler(request):
        assert str(request.url)=="https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-007"
        assert request.headers["Authorization"]=="Bearer secret-never-leak"
        data=json.loads(request.content)
        assert data["responseFormat"]["type"]=="json"
        assert data["thinking"]=={"effort":"none"}
        assert "maxTokens" not in data
        assert "base64" not in data["messages"][1]["content"]
        return success({"designs":[d.model_dump() for d in mock_designs(brief)]})
    assert len(clova_client(handler).designs(brief,time.monotonic()+10))==3


@pytest.mark.parametrize("status,code",[(429,"RATE_LIMIT"),(401,"AUTH"),(403,"AUTH"),(500,"UPSTREAM")])
def test_clova_errors_are_sanitized(brief,status,code):
    designer=clova_client(lambda _:httpx.Response(status,text="secret-never-leak internal error"))
    with pytest.raises(ProviderError) as raised:
        designer.designs(brief,time.monotonic()+5)
    assert raised.value.code==code
    assert "secret" not in str(raised.value)


def test_clova_rejects_truncated_and_malformed_outputs(brief):
    for response in [success({},finish="length"),httpx.Response(200,json={}),success({"designs":[]})]:
        designer=clova_client(lambda _, response=response:response)
        with pytest.raises(ProviderError) as raised:
            designer.designs(brief,time.monotonic()+5)
        assert raised.value.code=="OUTPUT"


def test_live_revision_and_style_use_separate_naver_models(brief):
    seen=[]
    current=mock_designs(brief)[0]
    def handler(request):
        seen.append(request.url.path)
        data=json.loads(request.content)
        if request.url.path.endswith("HCX-005"):
            uri=data["messages"][1]["content"][1]["dataUri"]["data"]
            assert base64.b64decode(uri, validate=True)==b"image"
            return httpx.Response(200,json={"status":{"code":"20000"},"result":{"finishReason":"stop","message":{"content":"초록색과 넓은 여백"}}})
        assert "current" in json.loads(data["messages"][1]["content"])
        return success({"design":current.model_dump()|{"palette":"sage"},"needs_fact_edit":False})
    designer=clova_client(handler)
    style=designer.analyze_style(b"image",time.monotonic()+5)
    result=designer.designs(brief,time.monotonic()+5,style=style,current=current,instruction="초록색으로")
    assert result[0].palette=="sage"
    assert [s.rsplit("/",1)[-1] for s in seen]==["HCX-005","HCX-007"]


def test_live_fact_change_returns_actionable_error(brief):
    current=mock_designs(brief)[0]
    designer=clova_client(lambda _:success({"design":current.model_dump(),"needs_fact_edit":True}))
    with pytest.raises(ProviderError,match="입력란"):
        designer.designs(brief,time.monotonic()+5,current=current,instruction="가격을 5000원으로")


def test_engine_three_drafts_revision_restart_ownership(engine,brief):
    result=engine.create(brief)
    assert len(result["drafts"])==3
    assert len({d["design"]["template_id"] for d in result["drafts"]})==3
    old=result["drafts"][0]
    revision=Revision(store_id=brief.store.store_id,instruction="초록색으로",expected_version=1)
    new=engine.revise(old["id"],revision)
    assert new["version"]==2 and new["design"]["palette"]=="sage"
    assert old["image_url"]!=new["image_url"]
    assert "3,500원" in new["caption"]["body"]
    record,facts,*_=engine.repository.get(old["id"],brief.store.store_id)
    assert facts["price"]==3500 and facts["period"]==brief.period
    reopened=Repository(engine.settings.data_dir)
    assert reopened.get(old["id"],brief.store.store_id)[0]["version"]==2
    with pytest.raises(NotFound):
        engine.get(old["id"],"other-owner")
    with pytest.raises(Conflict):
        engine.revise(old["id"],revision)


def test_concurrent_revisions_do_not_overwrite(engine,brief):
    old=engine.create(brief)["drafts"][0]
    revision=Revision(store_id=brief.store.store_id,instruction="초록색으로",expected_version=1)
    def run():
        try:return engine.revise(old["id"],revision)["version"]
        except Conflict:return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:run(),range(2)))
    assert sorted(map(str,results))==["2","conflict"]


def test_cancelled_generation_does_not_publish(engine,brief):
    with pytest.raises(ProviderError) as raised:
        engine.create(brief,cancelled=lambda:True)
    assert raised.value.code=="DEADLINE"
    assert not list(engine.repository.images.glob("*.png"))


def test_api_auth_studio_csrf_and_png_download(engine,brief):
    with TestClient(create_app(engine)) as client:
        assert client.post("/v1/posters/drafts",json=brief.model_dump()).status_code==401
        page=client.get("/")
        token=json.loads(re.search(r'<script id="studio-config" type="application/json">(.*?)</script>',page.text).group(1))["token"]
        assert "test-key" not in page.text
        bad=client.post("/v1/posters/drafts",headers={"X-Studio-Token":token,"Origin":"https://evil.example"},json=brief.model_dump())
        assert bad.status_code==401
        headers={"X-Studio-Token":token}
        result=client.post("/v1/posters/drafts",headers=headers,json=brief.model_dump())
        assert result.status_code==200,result.text
        first=result.json()["drafts"][0]
        response=client.get(first["image_url"]+"?download=true")
        assert response.headers["content-type"]=="image/png"
        assert "attachment" in response.headers["content-disposition"]
        assert Image.open(BytesIO(response.content)).size==(1080,1350)
        changed=client.post("/v1/posters/"+first["id"]+"/revisions",headers=headers,json={
            "store_id":brief.store.store_id,"instruction":"가격 강조","expected_version":1})
        assert changed.status_code==200
        assert client.get("/v1/posters/"+first["id"],params={"store_id":"other"},headers=headers).status_code==404
        assert client.get("/images/"+"a"*32+".png").status_code==404
        assert client.get("/",headers={"Host":"attacker.example"}).status_code==404


def test_api_rejects_unknown_fields_without_echoing_input(engine,brief):
    with TestClient(create_app(engine)) as client:
        r=client.post("/v1/posters/drafts",json=brief.model_dump()|{"unknown":"secret-private-data"},headers={"X-Internal-Key":"test-key"})
        assert r.status_code==422 and "secret-private-data" not in r.text


def test_api_rejects_oversized_body_before_parsing(engine):
    with TestClient(create_app(engine)) as client:
        result=client.post("/v1/posters/drafts",content=b"x"*(22*1024*1024+1))
        assert result.status_code==413


def test_grpc_old_client_new_client_and_health(engine):
    server,port=build_server(engine,"127.0.0.1:0")
    server.start()
    channel=grpc.insecure_channel("127.0.0.1:"+str(port))
    metadata=(("x-internal-key","test-key"),)
    try:
        stub=rpc.PromotionAssistantStub(channel)
        request=pb.PosterRequest(store=common_pb2.StoreContext(store_id="owner-1",name="테스트 가게"),product="소금빵")
        with pytest.raises(grpc.RpcError) as error:
            stub.CreatePoster(request,timeout=3)
        assert error.value.code()==grpc.StatusCode.UNAUTHENTICATED
        # Build an independent client descriptor containing ONLY the original fields.
        file=descriptor_pb2.FileDescriptorProto(name="legacy.proto",package="legacy",syntax="proto3")
        old=file.message_type.add(name="PosterRequest")
        old.field.add(name="store",number=1,type=12) # wire-compatible embedded StoreContext bytes
        old.field.add(name="product",number=2,type=9)
        old.field.add(name="generate_image",number=6,type=8)
        pool=descriptor_pool.DescriptorPool();pool.Add(file)
        Legacy=message_factory.GetMessageClass(pool.FindMessageTypeByName("legacy.PosterRequest"))
        raw=channel.unary_unary("/america.ai.v1.PromotionAssistant/CreatePoster",
                               request_serializer=lambda x:x.SerializeToString(),response_deserializer=pb.PosterResult.FromString)
        response=raw(Legacy(store=request.store.SerializeToString(),product="소금빵",generate_image=True),timeout=10,metadata=metadata)
        assert response.image_url.startswith("http://testserver/images/")
        no_image=stub.CreatePoster(request,timeout=5,metadata=metadata)
        assert no_image.headline and not no_image.image_url
        request.price=0
        result=stub.CreateDrafts(request,timeout=10,metadata=metadata)
        assert len(result.drafts)==3 and "0원" in result.drafts[0].result.body
        revised=stub.RevisePoster(pb.PosterRevisionRequest(store_id="owner-1",draft_id=result.drafts[0].id,
                     instruction="초록색으로",expected_version=1),timeout=10,metadata=metadata)
        assert revised.version==2
        from grpc_health.v1 import health_pb2,health_pb2_grpc
        health_result=health_pb2_grpc.HealthStub(channel).Check(health_pb2.HealthCheckRequest(service="america.ai.v1.PromotionAssistant"),timeout=3)
        assert health_result.status==health_pb2.HealthCheckResponse.SERVING
    finally:
        channel.close()
        server.stop(0).wait()
