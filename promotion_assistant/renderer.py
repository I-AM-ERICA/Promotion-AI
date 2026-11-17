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
from .typography import wrap_text

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
        self.serif = str(Path(__file__).parent / "fonts/NanumMyeongjo-Regular.ttf")
        self.serif_bold = str(Path(__file__).parent / "fonts/NanumMyeongjo-ExtraBold.ttf")

    @lru_cache(maxsize=100)
    def font(self, size, bold=False, serif=False):
        path = (self.serif_bold if bold else self.serif) if serif else (self.bold if bold else self.regular)
        return ImageFont.truetype(path, size)

    def wrap(self, text, font, width, balanced=False):
        return wrap_text(text, font, width, balanced=balanced)

    def text(self, draw, text, box, color, size=48, minimum=20, bold=False, align="left", *, serif=False, balanced=False, leading=1.35):
        if not text:
            return 0
        x, y, w, h = box
        for value in range(size, minimum - 1, -1):
            font = self.font(value, bold, serif)
            lines = self.wrap(text, font, w, balanced)
            step = round(value * leading)
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

    def price(self, draw, brief, box, fg, accent, muted, *, large=False):
        if brief.price is None:
            return
        x, y, w, h = box
        sale_height = h-47 if brief.original_price is not None else h
        self.text(draw, f"{brief.price:,}원", (x, y, w, sale_height), accent,
                  128 if large else 66, 28, True, leading=1.15)
        if brief.original_price is not None:
            label = f"{brief.original_price:,}원"
            font = self.font(24)
            length = font.getlength(label)
            py = y+sale_height+4
            draw.text((x, py), label, font=font, fill=muted, anchor="lt")
            draw.line((x, py+13, x+length, py+13), fill=muted, width=1)
            discount = (brief.original_price-brief.price)*100//brief.original_price
            self.text(draw, f"{discount}% 할인", (x+length+24, py-2, w-length-24, 38),
                      fg, 25, 18, True)

    def render(self, brief, design, product_image=None, logo=None):
        bg, fg, accent, panel, muted = PALETTES[design.palette]
        canvas = Image.new("RGB", (WIDTH, HEIGHT), bg)
        d = ImageDraw.Draw(canvas)
        variant = design.template_id
        offer = variant in ("bold_sale", "split")
        bottom_price = brief.price is not None and not offer
        detail = "\n".join(x for x in [brief.product, brief.message] if x)
        detail_font = 25
        detail_height = len(self.wrap(detail, self.font(detail_font), 936))*34
        price_height = (176 if design.emphasis == "price" else 128) if bottom_price else 0
        period_height = 40 if brief.period else 0
        facts_y = 1222-detail_height-period_height-price_height-16
        top_end = facts_y-30
        if top_end < 790:
            detail_font = 21
            detail_height = len(self.wrap(detail, self.font(detail_font), 936))*29
            facts_y = 1222-detail_height-period_height-price_height-16
            top_end = facts_y-30
        if top_end < 600:
            raise LayoutError("문구와 상품 사진을 함께 배치하기 어렵습니다. 메시지를 줄여 주세요.")
        required = {"split": 860 if brief.price is not None else 680,
                    "soft_frame": 705, "market": 720}.get(variant, 600)
        if top_end < required:
            raise LayoutError("이 구도에 문구가 모두 들어가지 않습니다. 메시지를 줄여 주세요.")
        serif = design.typography == "serif" or design.typography == "auto" and variant in ("editorial", "night", "soft_frame")
        bold = design.typography == "bold" or design.typography == "auto" and not serif

        def title(box, size=86, align="left"):
            return self.text(d, design.headline, box, fg, size, 30, bold, align,
                             serif=serif, balanced=True, leading=1.18)

        def subtitle(box, align="left"):
            return self.text(d, design.subhead, box, muted, 29, 19, False, align)

        def photo(box, radius=12):
            self.photo(canvas, product_image, box, panel, fg, brief.product, design.image_fit, radius)

        # Store identity and logo occupy a fixed safe area in every composition.
        self.text(d, brief.store.name, (72, 56, 750, 52), fg, 27, 18, True)
        if logo:
            im = Image.open(BytesIO(logo)).convert("RGBA")
            im.thumbnail((150, 65), Image.Resampling.LANCZOS)
            canvas.paste(im, (1008-im.width, 50), im)
        else:
            d.ellipse((981, 65, 1005, 89), fill=accent)

        if variant == "editorial":
            d.line((72, 122, 1008, 122), fill=muted, width=1)
            used = title((72, 164, 936, 210), 92)
            sub_y = 164+used+24
            sub_used = subtitle((76, sub_y, 850, 82))
            photo_y = sub_y+sub_used+24
            photo((65, photo_y, 950, top_end-photo_y))
        elif variant == "bold_sale":
            d.line((72, 125, 1008, 125), fill=fg, width=3)
            title((72, 155, 936, 168), 88)
            subtitle((76, 335, 890, 78))
            if brief.price is not None:
                self.price(d, brief, (72, 430, 936, 200), fg, accent, muted, large=True)
                photo_top = 630
            else:
                photo_top = 430
            # A broad colour field grounds the product; no sticker obscures it.
            d.rounded_rectangle((72, photo_top, 1008, top_end), radius=38, fill=panel)
            photo((78, photo_top+4, 924, top_end-photo_top-8), 32)
        elif variant == "split":
            d.rounded_rectangle((542, 146, 1008, top_end), radius=220, fill=panel)
            title((72, 174, 430, 280), 79)
            subtitle((76, 477, 414, 155))
            if brief.price is not None:
                self.price(d, brief, (72, max(650, top_end-220), 430, 180),
                           fg, accent, muted, large=True)
            photo((548, 160, 454, top_end-175), 180)
        elif variant == "soft_frame":
            photo_end = max(420, top_end-285)
            d.rounded_rectangle((192, 142, 888, photo_end), radius=230, fill=panel)
            photo((170, 145, 740, photo_end-145), 180)
            title((72, photo_end+33, 936, 155), 77, "center")
            subtitle((130, photo_end+202, 820, 78), "center")
        elif variant == "night":
            d.rectangle((29, 29, 1050, 1320), outline=accent, width=1)
            d.line((72, 125, 1008, 125), fill=accent, width=1)
            used = title((72, 181, 560, 300), 86)
            subtitle((76, 510, 340, min(180, top_end-510)))
            # Deliberately lower/right composition leaves a quiet column of copy.
            photo_y = max(367, 181+used+24)
            photo((434, photo_y, 574, top_end-photo_y))
            d.line((76, top_end-16, 274, top_end-16), fill=accent, width=3)
        else:  # market: the product leads, copy follows.
            photo_end = max(440, top_end-280)
            d.ellipse((202, 147, 878, photo_end), fill=panel)
            photo((72, 140, 936, photo_end-140))
            title((72, photo_end+28, 936, 158), 82)
            subtitle((76, photo_end+202, 910, 76))

        y = facts_y
        if bottom_price:
            self.price(d, brief, (72, y, 936, price_height), fg, accent, muted,
                       large=design.emphasis == "price")
            y += price_height
        self.text(d, detail, (72, y, 936, detail_height), fg, detail_font, detail_font)
        y += detail_height+12
        if brief.period:
            self.text(d, brief.period, (72, y, 936, period_height), muted, 23, 18)
        d.line((72, 1247, 1008, 1247), fill=muted, width=1)
        self.text(d, design.cta, (72, 1270, 500, 43), fg, 25, 18, True)
        self.text(d, brief.contact or brief.store.region, (600, 1266, 408, 53), muted, 22, 16)
        output = BytesIO()
        canvas.save(output, "PNG", optimize=True)
        return output.getvalue()
