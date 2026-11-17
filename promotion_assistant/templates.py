"""Reviewed layout and colour choices; models cannot supply CSS or coordinates."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    palette: str
    family: str


TEMPLATES = [
    Template("editorial", "시그니처", "큰 상품과 명조 제목, 넓은 여백", "cream", "hero"),
    Template("bold_sale", "위크엔드 딜", "큰 가격 위계와 선명한 행사 색상", "coral", "offer"),
    Template("soft_frame", "작은 선물", "상단 아치 속 상품과 하단의 짧은 편지", "peach", "brand"),
    Template("split", "컬렉션", "왼쪽 가격과 문구, 오른쪽 세로 상품 배치", "cobalt", "offer"),
    Template("night", "프리미엄", "비대칭 명조 제목과 짙은 여백", "ink", "brand"),
    Template("market", "동네의 발견", "원형 배경 속 큰 상품과 하단의 경쾌한 제목", "sage", "hero"),
]


def diverse_designs(designs):
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
    return result
# background, foreground, accent, panel, muted
PALETTES = {
    "cream": ("#F5F0E7", "#292821", "#7B4A31", "#E9E0D2", "#655F55"),
    "coral": ("#F44835", "#FFF9EF", "#FFE96D", "#D53527", "#FFF3DD"),
    "sage": ("#DDE7D3", "#173D2D", "#E9683C", "#F7F4E8", "#44604D"),
    "cobalt": ("#EAEFF6", "#193A73", "#245BE6", "#D5DFF0", "#4C5F7E"),
    "ink": ("#20292B", "#F5EAD5", "#E5B978", "#344044", "#C0C7C1"),
    "peach": ("#F9E8DD", "#60362B", "#B94B3D", "#FFF8EF", "#835E52"),
}
