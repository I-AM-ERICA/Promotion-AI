"""CPU-only 1080x1350 raster renderer with measured Korean text layout."""
from __future__ import annotations
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import os
import warnings
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
from .product_image import has_transparency
from .templates import PALETTES

WIDTH, HEIGHT = 1080, 1350
Image.MAX_IMAGE_PIXELS = 20_000_000


def normalize_image(source, *, max_edge=2000) -> bytes | None:
    if source is None:
        return None
    data = source.decode()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in ("PNG", "JPEG", "WEBP"):
                    raise ValueError("PNG, JPEG, WEBP만 지원합니다.")
                actual = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[image.format]
                if source.media_type != actual:
                    raise ValueError("이미지 형식과 media_type이 일치하지 않습니다.")
                if image.width * image.height > 20_000_000 or min(image.size) < 4:
                    raise ValueError("이미지 해상도를 확인해 주세요. 최대 2천만 화소입니다.")
                image = ImageOps.exif_transpose(image).convert("RGBA")
                image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                # Preserve alpha, remove EXIF/profile/metadata; never fetch caller URLs.
                clean = Image.new("RGBA", image.size)
                clean.paste(image)
                buffer = BytesIO()
                clean.save(buffer, "PNG")
                return buffer.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError):
        raise ValueError("이미지를 읽을 수 없거나 해상도가 너무 큽니다.") from None


def vision_image(data):
    """Pad extreme ratios to meet HCX-005's 1:5..5:1 input rule."""
    im = Image.open(BytesIO(data)).convert("RGB")
    w, h = im.size
    canvas = Image.new("RGB", (max(w, (h + 4) // 5), max(h, (w + 4) // 5)), "#F5F0E7")
    canvas.paste(im, ((canvas.width-w)//2, (canvas.height-h)//2))
    output = BytesIO()
    canvas.save(output, "PNG")
    return output.getvalue()


class LayoutError(ValueError):
    pass


def find_font(custom="", bold=False):
    candidates = [custom] if custom else []
    candidates += [
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("한글 폰트가 없습니다. POSTER_FONT_PATH / POSTER_BOLD_FONT_PATH를 설정해 주세요.")


class Renderer:
    def __init__(self, font_path="", bold_font_path=""):
        self.regular = find_font(font_path)
        self.bold = find_font(bold_font_path or font_path, True)

    @lru_cache(maxsize=100)
    def font(self, size, bold=False):
        return ImageFont.truetype(self.bold if bold else self.regular, size)

    def wrap(self, text, font, width):
        lines = []
        for para in text.split("\n"):
            line = ""
            for char in para:
                if font.getlength(line + char) > width and line:
                    lines.append(line.rstrip())
                    line = char.lstrip()
                else:
                    line += char
            lines.append(line.rstrip())
        return lines

    def text(self, draw, text, box, color, size=48, minimum=20, bold=False, align="left"):
        if not text:
            return 0
        x, y, w, h = box
        for value in range(size, minimum - 1, -1):
            font = self.font(value, bold)
            lines = self.wrap(text, font, w)
            step = round(value * 1.35)
            if len(lines) * step <= h and all(font.getlength(line) <= w for line in lines):
                for index, line in enumerate(lines):
                    offset = (w - font.getlength(line)) / 2 if align == "center" else 0
                    draw.text((x+offset, y+index*step), line, font=font, fill=color, anchor="lt")
                return len(lines) * step
        raise LayoutError("문구가 포스터 영역에 맞지 않습니다. 글귀를 조금 줄여 주세요.")

    def photo(self, canvas, data, box, panel, ink, product, fit="contain", radius=10):
        x, y, w, h = map(int, box)
        if min(w, h) < 100:
            raise LayoutError("상품 사진을 배치할 공간이 부족합니다. 글귀를 줄여 주세요.")
        frame = Image.new("RGB", (w, h), panel)
        if data:
            source = Image.open(BytesIO(data)).convert("RGBA")
            if has_transparency(source):
                bounds = source.getchannel("A").point(lambda v: 255 if v > 16 else 0).getbbox()
                if bounds:
                    source = source.crop(bounds)
                # Transparent assets float on the layout, with breathing room for a soft shadow.
                scale = min(w*.88/source.width, h*.86/source.height)
                source = source.resize((max(1, round(source.width*scale)), max(1, round(source.height*scale))), Image.Resampling.LANCZOS)
                layer = Image.new("RGBA", (w, h))
                px, py = (w-source.width)//2, (h-source.height)//2
                shadow_mask = Image.new("L", (w, h))
                shadow_mask.paste(source.getchannel("A"), (px+7, py+17))
                shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(18)).point(lambda v: round(v*.23))
                shadow = Image.new("RGBA", (w, h), (24, 20, 17, 0))
                shadow.putalpha(shadow_mask)
                layer.alpha_composite(shadow)
                layer.alpha_composite(source, (px, py))
                canvas.paste(layer, (x, y), layer)
                return
            if fit == "cover":
                source = ImageOps.fit(source, (w, h), method=Image.Resampling.LANCZOS)
                frame.paste(source, (0, 0), source)
            else:
                source = ImageOps.contain(source, (int(w*.94), int(h*.94)), Image.Resampling.LANCZOS)
                frame.paste(source, ((w-source.width)//2, (h-source.height)//2), source)
        else:
            d = ImageDraw.Draw(frame)
            d.ellipse((w*.12, h*.10, w*.88, h*.9), outline=ink, width=2)
            self.text(d, product, (w*.2, h*.25, w*.6, h*.5), ink, 50, 18, True, "center")
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w-1, h-1), radius=radius, fill=255)
        canvas.paste(frame, (x, y), mask)

    def render(self, brief, design, product_image=None, logo=None):
        bg, fg, accent, panel, muted = PALETTES[design.palette]
        canvas = Image.new("RGB", (WIDTH, HEIGHT), bg)
        d = ImageDraw.Draw(canvas)
        # Facts are never copied from the model: exact owner text and computed price.
        detail = "\n".join(x for x in [brief.product, brief.message] if x)
        detail_font = 26
        detail_lines = self.wrap(detail, self.font(detail_font), 936)
        detail_height = len(detail_lines) * 35
        price_height = (108 if design.emphasis == "price" else 82) if brief.price is not None else 0
        period_height = 44 if brief.period else 0
        facts_height = detail_height + price_height + period_height + 28
        facts_y = 1230 - facts_height
        top_end = facts_y - 26
        if top_end < 550:
            # Long copy gets a larger facts area through smaller but still legible type.
            detail_font = 22
            detail_height = len(self.wrap(detail, self.font(detail_font), 936)) * 30
            facts_height = detail_height + price_height + period_height + 28
            facts_y = 1230 - facts_height
            top_end = facts_y - 26
        if top_end < 490:
            raise LayoutError("글귀가 너무 깁니다. 메시지를 줄여 주세요.")
        title = design.headline
        variant = design.template_id
        if variant == "night":
            d.rectangle((27, 27, 1052, 1322), outline=accent, width=2)
        self.text(d, brief.store.name, (72, 58, 760, 42), fg, 27, 20, True)
        if logo:
            im = Image.open(BytesIO(logo)).convert("RGBA")
            im.thumbnail((150, 66), Image.Resampling.LANCZOS)
            canvas.paste(im, (1008-im.width, 52), im)
        else:
            d.ellipse((973, 63, 1005, 95), fill=accent)

        if variant == "split":
            d.line((530, 145, 530, top_end), fill=accent, width=2)
            self.text(d, title, (72, 167, 420, 255), fg, 86, 34, True)
            self.text(d, design.subhead, (76, 438, 410, max(85, top_end-450)), muted, 32, 22)
            self.photo(canvas, product_image, (558, 157, 450, top_end-157), panel, fg, brief.product, design.image_fit, 8)
        else:
            centered = variant in ("soft_frame", "night")
            align = "center" if centered else "left"
            title_y = 144
            title_height = 166 if top_end < 700 else 207
            title_size = 84 if centered else 96
            self.text(d, title, (72, title_y, 936, title_height), fg, title_size, 36, True, align)
            sub_y = title_y + title_height + 5
            sub_height = 82
            self.text(d, design.subhead, (74, sub_y, 932, sub_height), muted, 30, 20, False, align)
            photo_y = sub_y + sub_height + 18
            photo_h = top_end-photo_y
            if photo_h < 130:
                # Compact the headline area for very long factual text.
                raise LayoutError("문구와 상품 사진을 함께 배치하기 어렵습니다. 메시지를 줄여 주세요.")
            box = (72, photo_y, 936, photo_h)
            radius = 8
            if variant == "bold_sale":
                d.ellipse((840, photo_y-26, 1030, photo_y+164), fill=accent)
                box = (90, photo_y+10, 900, photo_h-10)
                radius = 28
            elif variant == "soft_frame":
                d.rounded_rectangle((61, photo_y-11, 1019, top_end+11), radius=60, outline=accent, width=2)
                box = (76, photo_y+4, 928, photo_h-8)
                radius = 48
            elif variant == "market":
                d.rounded_rectangle((89, photo_y+15, 1023, top_end+15), radius=18, fill=accent)
                radius = 18
            elif variant == "night":
                box = (90, photo_y, 900, photo_h)
            else:
                d.line((72, 120, 1008, 120), fill=muted, width=1)
            self.photo(canvas, product_image, box, panel, fg, brief.product, design.image_fit, radius)

        y = facts_y
        if brief.price is not None:
            label = f"{brief.price:,}원"
            price_size = 76 if design.emphasis == "price" else 58
            self.text(d, label, (72, y, 680, price_height), accent, price_size, 34, True)
            if brief.original_price is not None:
                original = f"{brief.original_price:,}원"
                ofont = self.font(25)
                ow = ofont.getlength(original)
                d.text((1008-ow, y+8), original, font=ofont, fill=muted, anchor="lt")
                d.line((1008-ow, y+23, 1008, y+23), fill=muted, width=2)
                # Integer arithmetic rounds DOWN, never exaggerates the discount.
                discount = (brief.original_price-brief.price)*100//brief.original_price
                self.text(d, f"{discount}% 할인", (740, y+43, 268, 43), fg, 28, 20, True, "center")
            y += price_height
        self.text(d, detail, (72, y, 936, detail_height), fg, detail_font, detail_font)
        y += detail_height + 10
        if brief.period:
            self.text(d, brief.period, (72, y, 936, period_height), muted, 25, 20)
        d.line((72, 1247, 1008, 1247), fill=muted, width=1)
        self.text(d, design.cta, (72, 1270, 500, 43), fg, 26, 20, True)
        footer = brief.contact or brief.store.region
        self.text(d, footer, (600, 1270, 408, 45), muted, 22, 16)
        out = BytesIO()
        canvas.save(out, "PNG", optimize=True)
        return out.getvalue()
