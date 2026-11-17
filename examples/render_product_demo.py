"""Real local U2Net + optional CLOVA smoke test using one CC0 coffee photo.

python -m examples.render_product_demo
python -m examples.render_product_demo --env-file /path/to/.env
Only the second form calls CLOVA (one generation and one revision).
"""
import argparse
import base64
from pathlib import Path
import json
from dataclasses import replace
from PIL import Image, ImageDraw
from dotenv import load_dotenv
from promotion_assistant.clova import ClovaDesigner, DemoDesigner
from promotion_assistant.config import Settings
from promotion_assistant.engine import Engine
from promotion_assistant.models import Brief, Revision
from promotion_assistant.product_image import ProductProcessor
from promotion_assistant.renderer import Renderer
from promotion_assistant.storage import Repository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file")
    args = parser.parse_args()
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    output = Path("outputs/product-demo")
    output.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).parent / "assets/coffee.jpg"
    photo = source.read_bytes()
    brief = Brief(store={"store_id": "example-coffee", "name": "오후의 커피"},
                  product="에스프레소", message="깊은 향, 여유로운 한 모금.", price=3500,
                  original_price=4000, period="11.20 – 11.27", contact="매장 방문 · 포장 가능",
                  product_image={"base64": base64.b64encode(photo).decode(), "media_type": "image/jpeg"},
                  background_mode="remove")
    processor = ProductProcessor()
    processor.warmup()
    # This cutout preview is reused for manual inspection; engine independently exercises the pipeline.
    cutout = processor.process(photo, "remove")
    (output / "cutout.png").write_bytes(cutout.data)
    settings = Settings.from_env(demo=not bool(args.env_file), studio=True)
    settings = replace(settings, data_dir=output / "data")
    renderer = Renderer()
    designer = ClovaDesigner(settings.api_key) if args.env_file else DemoDesigner()
    engine = Engine(settings, designer, renderer, Repository(settings.data_dir), processor)
    try:
        result = engine.create(brief)
        panels = []
        for index, draft in enumerate(result["drafts"]):
            record, *_ = engine.repository.get(draft["id"], brief.store.store_id)
            png = engine.repository.images / record["image_name"]
            image = Image.open(png).copy()
            image.save(output / f"draft-{index+1}.png")
            image.thumbnail((360, 450))
            panels.append(image)
        sheet = Image.new("RGB", (1152, 580), "#F1EFE9")
        draw = ImageDraw.Draw(sheet)
        draw.text((24, 20), "같은 상품 사진 · 서로 다른 구도", font=renderer.font(28, True), fill="#26342B")
        for i, (panel, label) in enumerate(zip(panels, ("상품 중심", "가격 중심", "여백·서체 중심"))):
            sheet.paste(panel, (24+372*i, 78))
            draw.text((24+372*i, 541), label, font=renderer.font(22, True), fill="#26342B")
        sheet.save(output / "comparison.png")
        first = result["drafts"][0]
        revised = engine.revise(first["id"], Revision(store_id=brief.store.store_id,
                               instruction="제목을 '한 모금의 여유'로 바꾸고 설명을 짧게 다듬어 주세요." if args.env_file else "제목을 명조체로 바꾸고 배경을 초록색으로 바꿔줘", expected_version=1))
        summary = {"mode": result["mode"], "drafts": [d["design"] for d in result["drafts"]],
                   "processing": first["image_processing"], "revision": revised["design"], "version": revised["version"]}
        (output / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"mode": summary["mode"], "draft_count": 3, "background": summary["processing"]["background"], "revision_version": revised["version"]}))
        print(output.resolve())
    finally:
        designer.close()


if __name__ == "__main__":
    main()
