import base64
from io import BytesIO

import numpy as np
import pytest
from PIL import Image, ImageDraw

from promotion_assistant.clova import DemoDesigner
from promotion_assistant.config import Settings
from promotion_assistant.creative_layouts import edge_photo
from promotion_assistant.engine import Engine
from promotion_assistant.models import Brief, Design, Revision
from promotion_assistant.product_image import ProductProcessor, png
from promotion_assistant.renderer import Renderer, normalize_image
from promotion_assistant.storage import Repository, NotFound


def test_scene_and_cutout_switch_reuses_assets_and_checks_owner(tmp_path):
    class Segmenter:
        calls = 0

        def predict(self, source):
            self.calls += 1
            mask = Image.new("L", source.size)
            ImageDraw.Draw(mask).ellipse((25, 25, 175, 175), fill=255)
            return [mask]

    class Designer(DemoDesigner):
        def designs(self, brief, deadline, **kwargs):
            if kwargs.get("current"):
                return super().designs(brief, deadline, **kwargs)
            return [Design(template_id=t, palette="cream", headline="오늘의 즐거움", image_fit="cover")
                    for t in ("edge_closeup", "service_board", "photo_mood")]

    class RecordingRenderer(Renderer):
        def __init__(self):
            super().__init__()
            self.photos = []

        def render(self, brief, design, data=None, logo=None):
            self.photos.append(data)
            return super().render(brief, design, data, logo)

    session, renderer = Segmenter(), RecordingRenderer()
    source = png(Image.new("RGB", (200, 200), (230, 120, 40)))
    brief = Brief(store={"store_id": "owner", "name": "가게"}, product="당구",
                  background_mode="remove",
                  product_image={"base64": base64.b64encode(source).decode(), "media_type": "image/png"})
    repository = Repository(tmp_path)
    engine = Engine(Settings(internal_key="test", demo=True, data_dir=tmp_path), Designer(),
                    renderer, repository, ProductProcessor(session))
    drafts = engine.create(brief)["drafts"]
    cutout = renderer.photos[0]
    original = normalize_image(brief.product_image)
    assert renderer.photos == [cutout, cutout, original] and cutout != original
    assert [d["image_processing"]["source"] for d in drafts] == ["processed", "processed", "original"]
    target = drafts[0]["id"]
    engine.revise(target, Revision(store_id="owner", instruction="포토 무드 템플릿으로 바꿔줘", expected_version=1))
    changed = engine.revise(target, Revision(store_id="owner", instruction="웨이브 스플릿 템플릿으로 바꿔줘", expected_version=2))
    assert renderer.photos[-2:] == [original, cutout]
    assert changed["image_processing"]["source"] == "processed" and session.calls == 1
    assert repository.get(target, "owner", original=True)[2] == original
    with pytest.raises(NotFound):
        repository.get(target, "other-owner", original=True)


def test_edge_closeup_crops_only_on_request_and_keeps_text_column_clear():
    source = Image.new("RGBA", (200, 200))
    draw = ImageDraw.Draw(source)
    draw.rectangle((10, 10, 189, 189), fill=(100, 100, 100, 255))
    colors = [(240, 20, 20), (20, 220, 20), (20, 20, 240), (220, 20, 220)]
    for (x, y), color in zip([(10, 10), (170, 10), (10, 170), (170, 170)], colors):
        draw.rectangle((x, y, x+19, y+19), fill=color+(255,))
    renderer = Renderer()
    rendered = {}
    for fit in ("contain", "cover"):
        canvas = Image.new("RGB", (1080, 1350), "white")
        edge_photo(renderer, canvas, png(source), 1100, "white", "black", "상품", fit)
        pixels = np.asarray(canvas).astype(int)
        rendered[fit] = [(np.max(np.abs(pixels-color), axis=2) < 10).sum() for color in colors]
        assert np.all(pixels[:, :420] == 255)
    assert all(count > 10 for count in rendered["contain"])
    assert rendered["cover"][0] > 10 and rendered["cover"][1] == 0
