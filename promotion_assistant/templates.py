"""Reviewed layout and colour choices; models cannot supply CSS or coordinates."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    palette: str


TEMPLATES = [
    Template("editorial", "시그니처", "여백과 큰 상품 사진으로 전하는 차분한 소개", "cream"),
    Template("bold_sale", "위크엔드 딜", "선명한 색과 큰 가격으로 강조하는 행사", "coral"),
    Template("soft_frame", "작은 선물", "부드러운 프레임의 신메뉴·선물 광고", "peach"),
    Template("split", "컬렉션", "문구와 상품을 나란히 배치한 정돈된 광고", "cobalt"),
    Template("night", "프리미엄", "짙은 배경과 절제된 장식의 고급 상품 소개", "ink"),
    Template("market", "동네의 발견", "밝은 색과 리듬감 있는 구도의 매장 소식", "sage"),
]
# background, foreground, accent, panel, muted
PALETTES = {
    "cream": ("#F5F0E7", "#292821", "#7B4A31", "#E9E0D2", "#655F55"),
    "coral": ("#F44835", "#FFF9EF", "#FFE96D", "#D53527", "#FFF3DD"),
    "sage": ("#DDE7D3", "#173D2D", "#E9683C", "#F7F4E8", "#44604D"),
    "cobalt": ("#EAEFF6", "#193A73", "#245BE6", "#D5DFF0", "#4C5F7E"),
    "ink": ("#20292B", "#F5EAD5", "#E5B978", "#344044", "#C0C7C1"),
    "peach": ("#F9E8DD", "#60362B", "#B94B3D", "#FFF8EF", "#835E52"),
}
