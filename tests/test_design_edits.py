import time
import pytest
from promotion_assistant.clova import ClovaDesigner
from promotion_assistant.design_edits import explicit_edits
from promotion_assistant.models import Brief, Design


@pytest.mark.parametrize("instruction,expected", [
    ("배경을 초록색으로 바꿔줘", {"palette": "sage"}),
    ("제목을 명조체로 바꾸고 배경을 초록색으로 바꿔줘", {"typography": "serif", "palette": "sage"}),
    ("가격 강조", {"emphasis": "price"}),
    ("가격을 더 강조해줘", {"emphasis": "price"}),
    ("night 템플릿으로 바꿔줘", {"template_id": "night", "palette": "ink", "typography": "auto", "image_fit": "contain"}),
    ("엣지 클로즈업 템플릿으로 바꿔줘", {"template_id": "edge_closeup", "palette": "burgundy", "typography": "auto", "image_fit": "cover"}),
    ("초록색으로 바꾸지 마", None),
    ("초록색으로 바꿔줘, 가격을 5000원으로", None),
    ("초록색으로 바꾸고 제목은 꽃으로 해줘", None),
])
def test_explicit_controls_do_not_misread_complex_instructions(instruction, expected):
    assert explicit_edits(instruction)==expected


def test_colour_and_font_changes_are_applied_without_upstream_call():
    class NoRequests:
        def post(self,*args,**kwargs):raise AssertionError("explicit design control called upstream")
    designer=ClovaDesigner("unused",NoRequests())
    brief=Brief(store={"store_id":"1","name":"가게"},product="상품")
    current=Design(template_id="editorial",palette="cream",headline="오늘의 여유")
    result=designer.designs(brief,time.monotonic()+5,current=current,instruction="제목을 명조체로 바꾸고 배경을 초록색으로 바꿔줘")[0]
    assert result.palette=="sage" and result.typography=="serif"
    assert result.headline==current.headline
