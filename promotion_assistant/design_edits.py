"""Apply unambiguous design controls without leaving enum selection to the LLM."""
import re
from .templates import TEMPLATES

PALETTE_LABELS = {"cream": "크림색", "coral": "빨간색", "sage": "초록색",
                  "cobalt": "파란색", "ink": "어두운 색", "peach": "분홍색"}


def explicit_edits(instruction):
    suffix = r"(?:\s*(?:바꿔\s*줘|바꿔\s*주세요|변경해\s*줘|변경해\s*주세요|해\s*줘|해\s*주세요))?"
    colors = {"초록색": "sage", "초록": "sage", "파란색": "cobalt", "파랑": "cobalt",
              "분홍색": "peach", "분홍": "peach", "빨간색": "coral", "빨강": "coral",
              "크림색": "cream", "어두운 색": "ink"}
    fonts = {"명조체": "serif", "명조": "serif", "고딕체": "sans", "고딕": "sans", "굵은 고딕": "bold"}
    templates = {name: t for t in TEMPLATES for name in (t.id, t.name)}
    changes = {}
    clauses = re.split(r"\s*(?:,|그리고|바꾸고|변경하고)\s*", instruction.strip().rstrip(".!"))
    for clause in clauses:
        color = re.fullmatch(r"(?:배경[을은]?\s*)?("+"|".join(colors)+r")(?:으로|로)"+suffix, clause)
        font = re.fullmatch(r"(?:제목[을은]?\s*)?("+"|".join(fonts)+r")(?:으로|로)"+suffix, clause)
        template = re.fullmatch(r"("+"|".join(map(re.escape, templates))+r")\s*템플릿으로"+suffix, clause)
        if color:
            changes["palette"] = colors[color[1]]
        elif font:
            changes["typography"] = fonts[font[1]]
        elif template:
            selected = templates[template[1]]
            changes.update(template_id=selected.id, palette=selected.palette, typography="auto")
        elif re.fullmatch(r"가격[을은]?\s*(?:더\s*)?강조"+suffix, clause):
            changes["emphasis"] = "price"
        elif clause in ("사진 전체 보기", "사진 전체가 보이게 해줘", "사진 전체"):
            changes["image_fit"] = "contain"
        elif clause in ("사진 꽉 채워줘", "사진 꽉 채우기"):
            changes["image_fit"] = "cover"
        else:
            # Complex instructions, negations and fact edits go through the full designer.
            return None
    return changes or None
