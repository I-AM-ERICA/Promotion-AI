"""Render six templates with an ORIGINAL illustrative product, not a product photo."""
from pathlib import Path
from PIL import Image, ImageDraw
from promotion_assistant.renderer import Renderer
from promotion_assistant.models import Brief, Design
from promotion_assistant.templates import TEMPLATES


def sample_product():
    image = Image.new("RGBA", (1100, 760))
    draw = ImageDraw.Draw(image)
    draw.ellipse((120, 585, 1015, 685), fill=(79, 44, 21, 25))
    # Simple bread illustration for local smoke tests, not an AI-generated photograph.
    draw.rounded_rectangle((148, 206, 973, 628), radius=210, fill="#9E5728")
    draw.rounded_rectangle((155, 170, 967, 590), radius=204, fill="#CE8541")
    draw.rounded_rectangle((173, 155, 949, 545), radius=186, fill="#E4AA63")
    for x in (310, 490, 670):
        draw.polygon([(x, 193), (x+82, 173), (x+183, 486), (x+101, 505)], fill="#B87539")
        draw.polygon([(x+15, 193), (x+61, 184), (x+161, 476), (x+116, 488)], fill="#F5D39A")
    for x, y in [(248, 320), (410, 420), (660, 297), (810, 380), (550, 248), (340, 500), (730, 479)]:
        draw.rounded_rectangle((x, y, x+12, y+7), radius=2, fill="#FFF5DD")
    return image


def main():
    destination = Path("outputs/gallery")
    destination.mkdir(parents=True, exist_ok=True)
    photo = sample_product()
    photo.save(destination / "sample-product.png")
    data = (destination / "sample-product.png").read_bytes()
    renderer = Renderer()
    brief = Brief(store={"store_id": "sample", "name": "오후의 베이커리", "region": "성수동"},
                  product="버터 소금빵", message="바삭한 첫입, 촉촉한 속.\n오늘의 작은 여유를 담았어요.",
                  price=3500, original_price=4000, period="11.20 – 11.27", contact="매장 방문 · 포장 가능")
    sheet = Image.new("RGB", (1128, 1050), "#F5F4EF")
    label = ImageDraw.Draw(sheet)
    label.text((24, 15), "Promotion-AI · 6 templates / 샘플 일러스트", font=renderer.font(24, True), fill="#293C31")
    for index, template in enumerate(TEMPLATES):
        design = Design(template_id=template.id, palette=template.palette, headline="버터의 풍미,\n소금의 여운",
                        subhead="고소한 향으로 채우는 오늘", emphasis="price")
        png = renderer.render(brief, design, data)
        path = destination / (template.id + ".png")
        path.write_bytes(png)
        preview = Image.open(path)
        preview.thumbnail((348, 435), Image.Resampling.LANCZOS)
        x = 24 + (index % 3)*372
        y = 65 + (index // 3)*492
        sheet.paste(preview, (x, y))
        label.text((x, y+445), template.name, font=renderer.font(22, True), fill="#293C31")
    sheet.save(destination / "gallery.png")
    print(destination.resolve())


if __name__ == "__main__":
    main()
