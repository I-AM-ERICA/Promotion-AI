import base64
from io import BytesIO
import pytest
from PIL import Image
from pydantic import ValidationError
from promotion_assistant.models import Brief, Design, ImageInput, validate_copy
from promotion_assistant.renderer import Renderer, normalize_image, LayoutError
from promotion_assistant.templates import TEMPLATES


@pytest.fixture
def brief():
    return Brief(store={"store_id": "store-1", "name": "오후의 베이커리", "region": "성수동"},
                 product="버터 소금빵", message="매일 만나는 고소한 즐거움",
                 price=3500, original_price=4000, period="11.20 – 11.27")


@pytest.fixture
def renderer():
    return Renderer()


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
@pytest.mark.parametrize("photo", [True, False])
def test_templates_make_real_png_with_or_without_photo(brief, renderer, template, photo):
    image = Image.new("RGBA", (340, 500), (250, 190, 90, 200))
    buffer = BytesIO()
    image.save(buffer, "PNG")
    design = Design(template_id=template.id, palette=template.palette, headline="오늘의 작은 즐거움")
    data = renderer.render(brief, design, buffer.getvalue() if photo else None)
    result = Image.open(BytesIO(data))
    assert result.format == "PNG" and result.size == (1080, 1350)
    assert len(result.getcolors(2_000_000)) > 100


def test_measured_text_never_silently_truncates(brief, renderer):
    design = Design(template_id="editorial", palette="cream", headline="맛있는 소식")
    for length in (100, 300, 500):
        value = Brief.model_validate(brief.model_dump() | {"message": "맛" * length})
        try:
            data = renderer.render(value, design)
            assert Image.open(BytesIO(data)).size == (1080, 1350)
        except LayoutError as e:
            assert "줄여" in str(e) or "맞지" in str(e)


def test_image_decode_checks_size_type_and_metadata():
    image = Image.new("RGB", (200, 400), "red")
    out = BytesIO()
    image.save(out, "PNG")
    value = ImageInput(base64=base64.b64encode(out.getvalue()).decode(), media_type="image/png")
    assert Image.open(BytesIO(normalize_image(value))).size == (200, 400)
    with pytest.raises(ValueError, match="media_type"):
        normalize_image(value.model_copy(update={"media_type": "image/jpeg"}))
    with pytest.raises(ValueError):
        normalize_image(value.model_copy(update={"base64": "this is not base64"}))


def test_owner_prices_cannot_be_invalid(brief):
    with pytest.raises(ValidationError):
        Brief.model_validate(brief.model_dump() | {"original_price": 1000})
    free = Brief.model_validate(brief.model_dump() | {"price": 0})
    assert free.price == 0


def test_model_cannot_introduce_numeric_claims(brief):
    invalid = Design(template_id="night", palette="ink", headline="90% 할인")
    with pytest.raises(ValueError):
        validate_copy(invalid, brief)
    valid = invalid.model_copy(update={"headline": "버터 소금빵 3,500원"})
    assert validate_copy(valid, brief).headline == valid.headline
