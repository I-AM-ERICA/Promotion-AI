import base64
from io import BytesIO
import json
import time
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from promotion_assistant.api import create_app
from promotion_assistant.clova import ClovaDesigner, DemoDesigner, ProviderError
from promotion_assistant.config import Settings
from promotion_assistant.engine import Engine
from promotion_assistant.models import Brief
from promotion_assistant.renderer import Renderer
from promotion_assistant.storage import Repository


@pytest.mark.parametrize("format,mime,size",[("PNG","image/png",(120,200)),
    ("JPEG","image/jpeg",(600,20)),("WEBP","image/webp",(20,600))])
def test_reference_upload_flows_from_vision_to_three_pngs(tmp_path,format,mime,size):
    image=BytesIO();Image.new("RGB",size,"green").save(image,format)
    brief=Brief(store={"store_id":"style-test","name":"가게"},product="에스프레소",price=3500,
                style_reference={"base64":base64.b64encode(image.getvalue()).decode(),"media_type":mime})
    calls=[]
    def respond(request):
        model=request.url.path.rsplit("/",1)[-1];calls.append(model)
        body=json.loads(request.content)
        if model=="HCX-005":
            content=body["messages"][1]["content"]
            uri=next(item["dataUri"]["data"] for item in content if item["type"]=="image_url")
            prefix,encoded=uri.split(",",1)
            assert prefix=="data:image/png;base64"
            decoded=Image.open(BytesIO(base64.b64decode(encoded,validate=True)))
            assert decoded.format=="PNG" and decoded.mode=="RGB"
            assert max(decoded.size)<=2240 and min(decoded.size)>=4
            assert max(decoded.size)<=5*min(decoded.size)
            result="초록색, 넓은 여백, 명조 제목"
        else:
            assert json.loads(body["messages"][1]["content"])["style_description"]=="초록색, 넓은 여백, 명조 제목"
            result=json.dumps({"designs":[d.model_dump() for d in DemoDesigner().designs(brief,time.monotonic()+5)]})
        return httpx.Response(200,json={"status":{"code":"20000"},"result":{"finishReason":"stop","message":{"content":result}}})
    with httpx.Client(transport=httpx.MockTransport(respond)) as upstream:
        engine=Engine(Settings(internal_key="test-key",api_key="test-api-key",data_dir=tmp_path),
                      ClovaDesigner("test-api-key",upstream),Renderer(),Repository(tmp_path))
        with TestClient(create_app(engine)) as client:
            response=client.post("/v1/posters/drafts",json=brief.model_dump(),headers={"X-Internal-Key":"test-key"})
            assert response.status_code==200,response.text
            drafts=response.json()["drafts"]
            assert len(drafts)==3 and calls==["HCX-005","HCX-007"]
            assert all(d["mode"]=="clova" for d in drafts)


def test_bad_request_logs_only_safe_code(caplog):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(400,
            json={"status":{"code":"40001","message":"secret-key image-base64 private"}}))) as client:
        with pytest.raises(ProviderError) as raised:
            ClovaDesigner("secret-key",client).analyze_style(b"image",time.monotonic()+5)
    assert raised.value.code=="REQUEST" and "40001" in caplog.text
    assert "secret-key" not in caplog.text and "image-base64" not in caplog.text
    assert "secret-key" not in str(raised.value)
