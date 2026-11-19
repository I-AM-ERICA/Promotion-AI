from io import BytesIO
import sqlite3
import pytest
from PIL import Image, ImageDraw
from promotion_assistant.product_image import ProductProcessor, png
from promotion_assistant.storage import Repository
from promotion_assistant.models import Brief


class Segmenter:
    def __init__(self):
        self.calls=0
    def predict(self,source):
        self.calls+=1
        mask=Image.new("L",source.size,0)
        ImageDraw.Draw(mask).ellipse((25,25,175,175),fill=255)
        return [mask]


def test_segmentation_preserves_rgb_and_runs_once():
    source=Image.new("RGBA",(200,200),(230,120,40,255))
    session=Segmenter()
    result=ProductProcessor(session).process(png(source))
    image=Image.open(BytesIO(result.data))
    assert image.convert("RGB").tobytes()==source.convert("RGB").tobytes()
    assert image.getpixel((0,0))[3]==0
    assert image.getpixel((100,100))[3]==255
    assert result.status=="removed" and session.calls==1


def test_keep_and_transparency_do_not_invoke_model():
    class MustNotRun:
        def predict(self,_):raise AssertionError("model should not run")
    processor=ProductProcessor(MustNotRun())
    opaque=png(Image.new("RGBA",(200,200),"red"))
    alpha=png(Image.new("RGBA",(200,200),(1,2,3,0)))
    assert processor.process(opaque,"keep").data==opaque
    assert processor.process(alpha).status=="transparent"


def test_bad_mask_fallback_is_visible():
    class Bad:
        def predict(self,source):return [Image.new("L",source.size,0)]
    processor=ProductProcessor(Bad())
    source=png(Image.new("RGB",(200,200),"red"))
    assert processor.process(source).warning
    with pytest.raises(ValueError,match="원본 배경 유지"):
        processor.process(source,"remove")


def test_tiny_transparent_border_still_runs_segmentation():
    image=Image.new("RGBA",(200,200),(25,150,50,255))
    ImageDraw.Draw(image).line((0,0,0,199),fill=(0,0,0,0),width=1)
    session=Segmenter()
    result=ProductProcessor(session).process(png(image),"remove")
    assert result.status=="removed" and session.calls==1


def test_existing_database_migrates_without_losing_original(tmp_path):
    root=tmp_path
    db=sqlite3.connect(root/"posters.sqlite3")
    db.execute("CREATE TABLE projects(id TEXT PRIMARY KEY,store_id TEXT NOT NULL,brief TEXT NOT NULL,photo BLOB,logo BLOB,style TEXT NOT NULL)")
    db.commit();db.close()
    repository=Repository(root)
    brief=Brief(store={"store_id":"1","name":"shop"},product="product")
    repository.create(brief,b"original",None,"",[({"id":"id","version":1},b"png")],cutout=b"cutout")
    assert repository.get("id","1")[2]==b"cutout"
    with repository.connect() as db:
        row=db.execute("SELECT photo,cutout FROM projects").fetchone()
        assert row["photo"]==b"original" and row["cutout"]==b"cutout"


def test_three_drafts_and_revision_reuse_one_cutout(tmp_path):
    import base64
    from promotion_assistant.clova import DemoDesigner
    from promotion_assistant.config import Settings
    from promotion_assistant.engine import Engine
    from promotion_assistant.models import Revision
    from promotion_assistant.renderer import Renderer
    session=Segmenter()
    source=png(Image.new("RGB",(200,200),(230,120,40)))
    brief=Brief(store={"store_id":"1","name":"가게"},product="상품",price=3500,
                product_image={"base64":base64.b64encode(source).decode(),"media_type":"image/png"})
    engine=Engine(Settings(internal_key="test",demo=True,data_dir=tmp_path),DemoDesigner(),
                  Renderer(),Repository(tmp_path),ProductProcessor(session))
    drafts=engine.create(brief)["drafts"]
    assert len(drafts)==3 and session.calls==1
    assert all(d["image_processing"]["background"]=="removed" for d in drafts)
    changed=engine.revise(drafts[0]["id"],Revision(store_id="1",instruction="명조체로",expected_version=1))
    assert changed["design"]["typography"]=="serif" and session.calls==1
    assert changed["image_processing"]==drafts[0]["image_processing"]
