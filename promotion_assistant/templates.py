"""Reviewed layout and colour choices; models cannot supply CSS or coordinates."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    palette: str
    family: str
    font_id: str = "auto"


TEMPLATES = [
    Template("editorial", "시그니처", "큰 상품과 명조 제목, 넓은 여백", "cream", "hero"),
    Template("bold_sale", "위크엔드 딜", "큰 가격 위계와 선명한 행사 색상", "coral", "offer"),
    Template("soft_frame", "작은 선물", "상단 아치 속 상품과 하단의 짧은 편지", "peach", "brand"),
    Template("split", "컬렉션", "왼쪽 가격과 문구, 오른쪽 세로 상품 배치", "cobalt", "offer"),
    Template("night", "프리미엄", "비대칭 명조 제목과 짙은 여백", "ink", "brand"),
    Template("market", "동네의 발견", "원형 배경 속 큰 상품과 하단의 경쾌한 제목", "sage", "hero"),
    Template("type_stack", "타이포 팝", "큰 반복 글자 앞의 상품, 음료·패키지에 어울림", "burgundy", "hero", "black_han_sans"),
    Template("magazine", "매거진", "왼쪽 세리프 제목과 오른쪽 큰 상품, 뷰티·패션·공방", "cream", "brand", "gowun_batang"),
    Template("spotlight", "스튜디오 글로우", "은은한 조명과 받침대 위의 상품, 병·화장품·생활용품", "forest", "hero", "serif"),
    Template("diagonal", "다이내믹", "두 가지 색면과 대각선 상품, 신발·잡화·전자제품", "cobalt", "offer", "dohyeon"),
]


def default_font(template_id):
    template = next(t for t in TEMPLATES if t.id == template_id)
    if template.font_id != "auto":
        return template.font_id
    return "serif" if template_id in ("editorial", "night", "soft_frame") else "bold"


def diverse_designs(designs, visual_context=None):
    """Cover three composition families, even when the LLM chooses similar layouts."""
    by_id = {t.id: t for t in TEMPLATES}
    chosen, used = [], set()
    for family, default in [("hero", "editorial"), ("offer", "bold_sale"), ("brand", "night")]:
        index = next((i for i, d in enumerate(designs) if i not in used and by_id[d.template_id].family == family), None)
        if index is not None:
            chosen.append((index, designs[index])); used.add(index)
        else:
            chosen.append((None, default))
    remaining = iter(i for i in range(len(designs)) if i not in used)
    result = []
    for index, value in chosen:
        if index is None:
            template = by_id[value]
            value = designs[next(remaining)].model_copy(update={"template_id": template.id, "palette": template.palette, "typography": "auto"})
        result.append(value)
    if visual_context and visual_context.get("shape") == "wide":
        # Narrow side columns make wide products too small. Keep the chosen colour and copy.
        replacements = {"split": "diagonal", "night": "soft_frame", "magazine": "soft_frame"}
        result = [d.model_copy(update={"template_id": replacements[d.template_id]}) if d.template_id in replacements else d for d in result]
    return result
# background, foreground, accent, panel, muted
PALETTES = {
    "cream": ("#F5F0E7", "#292821", "#7B4A31", "#E9E0D2", "#655F55"),
    "coral": ("#F44835", "#FFF9EF", "#FFE96D", "#D53527", "#FFF3DD"),
    "sage": ("#DDE7D3", "#173D2D", "#E9683C", "#F7F4E8", "#44604D"),
    "cobalt": ("#EAEFF6", "#193A73", "#245BE6", "#D5DFF0", "#4C5F7E"),
    "ink": ("#20292B", "#F5EAD5", "#E5B978", "#344044", "#C0C7C1"),
    "peach": ("#F9E8DD", "#60362B", "#B94B3D", "#FFF8EF", "#835E52"),
    "burgundy": ("#F8F0DD", "#7F2026", "#932A30", "#EDDDBE", "#79534C"),
    "forest": ("#153C35", "#F4EFDC", "#DFC48A", "#41695A", "#CFD9C5"),
}
