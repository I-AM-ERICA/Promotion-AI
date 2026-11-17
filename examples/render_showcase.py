"""Reproducible original illustrations and bundled fonts; no network/API calls."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw
from promotion_assistant.font_catalog import FONT_CHOICES
from promotion_assistant.models import Brief, Design
from promotion_assistant.renderer import Renderer
from promotion_assistant.templates import TEMPLATES
from .product_fixtures import fixture_bytes


def main():
    output=Path("outputs/showcase")
    output.mkdir(parents=True,exist_ok=True)
    renderer=Renderer()
    cases=[("type_stack","box","선물 상자","마음을 담은 선물",25000),
           ("magazine","jewelry","실버 링","일상에 빛나는 취향",39000),
           ("spotlight","bottle","데일리 세럼","나를 위한 작은 여유",25500),
           ("diagonal","shoe","데일리 스니커즈","오늘의 가벼운 발걸음",89000),
           ("floating_type","bottle","데일리 세럼","하루를 채우는 취향",25500),
           ("big_focus","jewelry","실버 링","시선을 사로잡는 순간",39000)]
    sheet=Image.new("RGB",(1128,1060),"#F5F4EF")
    draw=ImageDraw.Draw(sheet)
    draw.text((24,16),"새로운 구도 6가지 · 자체 제작 상품 일러스트",font=renderer.font(26,True),fill="#293C31")
    for i,(template_id,kind,product,headline,price) in enumerate(cases):
        template=next(t for t in TEMPLATES if t.id==template_id)
        brief=Brief(store={"store_id":"showcase","name":"우리 동네 상점"},product=product,
                    price=price,message="매장에서 직접 만나보세요.")
        design=Design(template_id=template_id,palette=template.palette,headline=headline,
                      subhead="당신의 하루에 더하는 취향")
        png=renderer.render(brief,design,fixture_bytes(kind))
        (output/(template_id+".png")).write_bytes(png)
        preview=Image.open(BytesIO(png));preview.thumbnail((348,435))
        x,y=24+(i%3)*372,70+(i//3)*495
        sheet.paste(preview,(x,y))
        draw.text((x,y+450),template.name,font=renderer.font(24,True),fill="#293C31")
    sheet.save(output/"products.png")
    fonts=[f for f in FONT_CHOICES if f.id not in ("auto","bold")]
    sheet=Image.new("RGB",(1000,1050),"#F6F4ED")
    draw=ImageDraw.Draw(sheet)
    draw.text((30,20),"상업용 무료 글꼴 8개 계열",font=renderer.font(28,True),fill="#243B30")
    for i,font in enumerate(fonts):
        y=80+i*120
        draw.text((30,y+20),font.name,font=renderer.font(22,True),fill="#243B30")
        sample=Image.open(BytesIO(renderer.font_preview(font.id)))
        sample.thumbnail((760,124))
        sheet.paste(sample,(225,y))
    sheet.save(output/"fonts.png")
    print(output.resolve())


if __name__=="__main__":
    main()
