from io import BytesIO
import json
from typing import get_args
import pytest
from PIL import Image, ImageDraw
from promotion_assistant.font_catalog import FONT_CHOICES, ROOT, TypographyId
from promotion_assistant.models import Brief, Design
from promotion_assistant.renderer import Renderer
from promotion_assistant.templates import TEMPLATES, diverse_designs
from promotion_assistant.visual_profile import visual_profile, is_product_set
from promotion_assistant.design_edits import explicit_edits
from examples.product_fixtures import fixture_bytes

CASES = [("bottle","데일리 세럼 30ml",25500), ("shoe","데일리 스니커즈",89000),
         ("box","무선 스피커",999999999), ("meal","모둠 도시락",0),
         ("set","생활용품 선물세트",35000), ("jewelry","실버 링",None)]


@pytest.fixture(scope="module")
def renderer():return Renderer()


@pytest.mark.parametrize("template",TEMPLATES,ids=lambda t:t.id)
@pytest.mark.parametrize("kind,product,price",CASES)
def test_different_product_shapes_keep_whole_subject_and_render(renderer,template,kind,product,price):
    brief=Brief(store={"store_id":"test","name":"우리 가게"},product=product,price=price,
                message="매장에서 직접 만나보세요.")
    design=Design(template_id=template.id,palette=template.palette,headline="일상의 새로운 취향",subhead="가게에서 전하는 소식")
    rendered=Image.open(BytesIO(renderer.render(brief,design,fixture_bytes(kind))))
    assert rendered.size==(1080,1350) and rendered.format=="PNG"


@pytest.mark.parametrize("template",TEMPLATES,ids=lambda t:t.id)
def test_dense_facts_use_compact_layout_without_omission(renderer,template):
    product="상품"*50
    message="다양한 상품 구성과 안내 사항을 매장에서 확인해 주세요. "*14
    brief=Brief(store={"store_id":"dense","name":"우리 가게"},product=product,message=message[:500],
                price=999999999,period="행사 기간 안내 "*6,contact="방문 전 문의해 주세요. "*7)
    design=Design(template_id=template.id,palette=template.palette,headline="가게에서 만나는 특별한 상품 소식을 지금 전합니다",subhead="상품에 대한 자세한 내용은 안내된 정보를 확인하고 매장에서 만나보세요.")
    # Inspect actual drawn text, so a successful but truncated PNG is not enough.
    class RecordingRenderer(Renderer):
        def __init__(self):super().__init__();self.drawn=[]
        def text(self,draw,text,*args,**kwargs):
            result=super().text(draw,text,*args,**kwargs);self.drawn.append(text);return result
    recorder=RecordingRenderer()
    result=recorder.render(brief,design,fixture_bytes("bottle"))
    all_text=" ".join(recorder.drawn)
    assert product in all_text and " ".join(brief.message.split()) in all_text
    assert brief.period in all_text and brief.contact in all_text and "999,999,999원" in all_text
    assert Image.open(BytesIO(result)).size==(1080,1350)


@pytest.mark.parametrize("font",FONT_CHOICES,ids=lambda f:f.id)
def test_bundled_fonts_render_and_can_be_selected(renderer,font):
    assert font.id in get_args(TypographyId)
    if font.path:
        path=ROOT/font.path
        assert path.is_file() and (path.parent/"OFL.txt").is_file()
    assert explicit_edits(f"제목 서체를 {font.id}로 바꿔줘")=={"typography":font.id}
    assert Image.open(BytesIO(renderer.font_preview(font.id))).size==(800,130)
    brief=Brief(store={"store_id":"font","name":"우리 가게"},product="선물",price=3500)
    design=Design(template_id="magazine",palette="cream",headline="일상에 담는 취향 ABC",typography=font.id)
    assert Image.open(BytesIO(renderer.render(brief,design,fixture_bytes("box")))).size==(1080,1350)


def test_shape_uses_subject_bounds_and_wide_products_avoid_narrow_columns():
    brief=Brief(store={"store_id":"shape","name":"가게"},product="신발")
    context=visual_profile(fixture_bytes("meal"),brief)
    assert context["shape"]=="wide" and context["background"]=="cutout"
    assert visual_profile(fixture_bytes("bottle"),brief)["shape"]=="tall"
    designs=[Design(template_id=id,palette="cream",headline="상품") for id in ("editorial","split","magazine")]
    result=diverse_designs(designs,context)
    assert [d.template_id for d in result]==["editorial","diagonal","soft_frame"]
    assert is_product_set("선물세트") and not is_product_set("텀블러")


@pytest.mark.parametrize("size,angle",[((180,900),0),((1200,300),0),((1200,300),-12)])
def test_cutout_placement_retains_all_four_extremities(renderer,size,angle):
    import numpy as np
    im=Image.new("RGBA",size)
    draw=ImageDraw.Draw(im)
    w,h=size
    colors=[(240,20,20),(20,220,20),(20,20,240),(220,20,220)]
    draw.rectangle((10,10,w-11,h-11),fill=(100,100,100,255))
    for (x,y),color in zip([(10,10),(w-65,10),(10,h-65),(w-65,h-65)],colors):
        draw.rectangle((x,y,x+54,y+54),fill=color+(255,))
    buffer=BytesIO();im.save(buffer,"PNG")
    canvas=Image.new("RGB",(500,650),"white")
    renderer.photo(canvas,buffer.getvalue(),(40,50,420,550),"white","black","product",angle=angle)
    pixels=np.asarray(canvas).astype(int)
    assert all((np.max(np.abs(pixels-color),axis=2)<10).sum()>4 for color in colors)
