from promotion_assistant.models import Design
from promotion_assistant.renderer import Renderer
from promotion_assistant.templates import diverse_designs, TEMPLATES


def test_prices_are_atomic_and_words_wrap_at_spaces():
    renderer = Renderer()
    font = renderer.font(30)
    lines = renderer.wrap("버터 소금빵 3,500 원 오늘 만나보세요", font, 240)
    assert any("3,500\u00a0원" in line for line in lines)
    assert all(font.getlength(line) <= 240 for line in lines)
    assert not any(line.startswith("원") for line in lines)
    assert "소금빵" in " ".join(lines)


def test_title_balance_preserves_explicit_newlines_and_text():
    renderer = Renderer()
    font = renderer.font(70, serif=True)
    text = "좋은 하루를 위한 작은 여유"
    lines = renderer.wrap(text, font, 500, balanced=True)
    assert " ".join(lines) == text
    assert all(font.getlength(line) <= 500 for line in lines)
    assert renderer.wrap("좋은 하루\n작은 여유", font, 1000, balanced=True) == ["좋은 하루", "작은 여유"]


def test_selection_covers_distinct_families_without_changing_copy():
    designs = [Design(template_id=t, palette="cream", headline=title) for t, title in
               [("editorial", "첫 번째 문구"), ("market", "두 번째 문구"), ("soft_frame", "세 번째 문구")]]
    result = diverse_designs(designs)
    families = {t.id: t.family for t in TEMPLATES}
    assert [families[d.template_id] for d in result] == ["hero", "offer", "brand"]
    assert {d.headline for d in result} == {d.headline for d in designs}
    assert [d.template_id for d in designs] == ["editorial", "market", "soft_frame"]
