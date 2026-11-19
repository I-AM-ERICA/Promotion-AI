"""Composition-led layouts with asymmetric photos and measured factual text."""
from io import BytesIO
import math
from PIL import Image, ImageDraw, ImageOps, ImageColor
from .templates import PALETTES
from .product_image import has_transparency

CREATIVE_IDS = {"orbit_script", "service_board", "photo_mood", "cast_shadow", "wave_split", "edge_closeup"}


def contrast_ink(color):
    rgb = ImageColor.getrgb(color)
    linear = [v/3294.6 if v <= 10 else ((v/255+.055)/1.055)**2.4 for v in rgb]
    luminance = sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
    return "#FFFFFF" if luminance < .179 else "#000000"


def arc_label(renderer, canvas, text, center, radii, color, *, lower=False):
    """Fit whole Unicode labels on an ellipse; omit decoration if it cannot fit."""
    text=" ".join(text.split())
    if not text:
        return
    rx,ry=radii
    for size in range(30,17,-1):
        font=renderer.font(size,True)
        advances=[font.getlength(char)+2 for char in text]
        if sum(advances) <= rx*2.0:
            break
    else:
        return
    span=min(140,math.degrees(sum(advances)/rx))
    start=(90+span/2) if lower else (270-span/2)
    direction=-1 if lower else 1
    cursor=0
    for char,advance in zip(text,advances):
        theta=math.radians(start+direction*span*(cursor+advance/2)/sum(advances))
        cursor+=advance
        if char.isspace():
            continue
        glyph=Image.new("RGBA",(max(64,round(advance+20)),64))
        ImageDraw.Draw(glyph).text((glyph.width/2,32),char,font=font,fill=color,anchor="mm")
        tangent=math.degrees(math.atan2(direction*ry*math.cos(theta),-direction*rx*math.sin(theta)))
        glyph=glyph.rotate(-tangent,Image.Resampling.BICUBIC,expand=True)
        x=center[0]+rx*math.cos(theta)-glyph.width/2
        y=center[1]+ry*math.sin(theta)-glyph.height/2
        canvas.paste(glyph,(round(x),round(y)),glyph)


def wave(canvas, y, color):
    points=[(x,round(y+43*math.sin(x/170))) for x in range(0,1081,6)]
    ImageDraw.Draw(canvas).polygon(points+[(1080,1350),(0,1350)],fill=color)


def scene_background(canvas, data, fit):
    if data:
        source=Image.open(BytesIO(data)).convert("RGBA")
        source=(ImageOps.fit(source,canvas.size,method=Image.Resampling.LANCZOS)
                if fit=="cover" else ImageOps.contain(source,canvas.size,Image.Resampling.LANCZOS))
        canvas.paste(source,((1080-source.width)//2,(1350-source.height)//2),source)
    # Keep the middle of the photograph visible; darken only copy areas.
    overlay=Image.new("RGBA",canvas.size)
    draw=ImageDraw.Draw(overlay)
    for y in range(1350):
        top=205 if y<380 else max(0,205-round((y-380)*1.7))
        bottom=max(0,min(220,round((y-790)*.9)))
        draw.line((0,y,1080,y),fill=(10,19,17,max(top,bottom)))
    canvas.paste(overlay,(0,0),overlay)


def edge_photo(renderer, canvas, data, bottom, panel, ink, product, fit):
    """Intentional right-edge close-up: crops the art area, never the information column."""
    if not data:
        renderer.photo(canvas,None,(440,250,640,bottom-250),panel,ink,product)
        return
    if fit == "contain":
        renderer.photo(canvas,data,(430,180,650,bottom-180),panel,ink,product,fit,8)
        return
    source=Image.open(BytesIO(data)).convert("RGBA")
    if has_transparency(source):
        bounds=source.getchannel("A").point(lambda a:255 if a>16 else 0).getbbox()
        if bounds:
            source=source.crop(bounds)
    scale=min(850/source.width,1120/source.height)
    source=source.resize((max(1,round(source.width*scale)),max(1,round(source.height*scale))),Image.Resampling.LANCZOS)
    art=Image.new("RGBA",(1080,round(bottom-170)))
    x=max(430,round(1080-source.width*.84))
    y=round((art.height-source.height)/2)
    art.alpha_composite(source,(x,y))
    canvas.paste(art,(0,170),art)


def render_creative(r, brief, design, data=None, logo=None):
    from .renderer import LayoutError
    bg,fg,accent,panel,muted=PALETTES[design.palette]
    canvas=Image.new("RGB",(1080,1350),bg)
    variant=design.template_id
    family=r.headline_family(design)
    detail="\n".join(x for x in (brief.product,brief.message) if x)
    detail_h=len(r.wrap(detail,r.font(24),936))*33
    period_h=len(r.wrap(brief.period,r.font(22),936))*30 if brief.period else 0
    contact=brief.contact or brief.store.region
    contact_h=len(r.wrap(contact,r.font(20),936))*27 if contact else 0
    side_price=variant in ("service_board","edge_closeup")
    price_h=145 if brief.price is not None and not side_price else 0
    facts_h=price_h+detail_h+period_h+contact_h+66
    facts_y=1302-facts_h
    if facts_y < (860 if side_price else 800):
        raise LayoutError("정보 영역이 부족합니다. 메시지를 줄여 주세요.")
    top_end=facts_y-28
    facts_fg,facts_muted,facts_accent=fg,muted,accent
    if variant=="photo_mood":
        scene_background(canvas,data,design.image_fit)
        fg=muted=facts_fg=facts_muted=facts_accent="#FFFFFF"
    if variant=="wave_split":
        wave(canvas,top_end*.64,fg)
        facts_fg=facts_muted=facts_accent=contrast_ink(fg)
    d=ImageDraw.Draw(canvas)

    def text(value,box,size=80,minimum=24,align="left",color=None,font=None):
        chosen=font or family
        return r.text(d,value,box,color or fg,size,minimum,chosen=="bold",align,
                      family=chosen,serif=chosen=="serif",balanced=True,leading=1.15)

    def handwriting(value,box,size=64,align="left",color=None):
        return text(value,box,size,22,align,color,"nanum_pen")

    r.text(d,brief.store.name,(72,52,750,55),fg,27,18,True)
    if logo:
        mark=Image.open(BytesIO(logo)).convert("RGBA");mark.thumbnail((150,65))
        canvas.paste(mark,(1008-mark.width,50),mark)

    if variant=="orbit_script":
        text(design.headline,(72,144,936,155),96,align="center")
        handwriting(design.subhead,(140,300,830,105),72,align="right")
        cy=(425+top_end)/2
        arc_label(r,canvas,brief.product,(440,cy),(365,max(100,(top_end-430)/2)),fg)
        arc_label(r,canvas,brief.store.name,(440,cy),(365,max(100,(top_end-430)/2)),fg,lower=True)
        r.photo(canvas,data,(15,410,840,top_end-410),panel,fg,brief.product,
                design.image_fit,12,angle=-16,rotate_tall=True)
        d.line((911,475,911,top_end-40),fill=accent,width=2)
    elif variant=="service_board":
        text(design.headline,(72,155,936,170),100)
        r.text(d,design.subhead,(76,350,820,110),fg,31,21)
        d.line((72,485,392,485),fill=fg,width=2)
        if brief.price is not None:
            r.price(d,brief,(72,525,350,205),fg,accent,muted,large=True)
        r.photo(canvas,data,(432,460,648,top_end-460),panel,fg,brief.product,
                design.image_fit,12,angle=0)
    elif variant=="photo_mood":
        text(design.headline,(72,160,936,180),107,align="center")
        handwriting(design.subhead,(110,330,860,110),76,align="center",color="#FFFFFF")
    elif variant=="cast_shadow":
        handwriting(design.headline,(380,155,628,105),72,align="right")
        r.decorative_type(canvas,brief.product,(40,270,1000,190),fg,family)
        r.photo(canvas,data,(0,390,850,top_end-390),panel,fg,brief.product,
                design.image_fit,12,shadow_style="long")
        r.text(d,design.subhead,(835,505,173,top_end-545),fg,29,18)
    elif variant=="wave_split":
        text(design.headline,(72,145,920,155),100)
        handwriting(design.subhead,(72,330,440,130),64)
        r.photo(canvas,data,(350,365,730,top_end-365),panel,fg,brief.product,
                design.image_fit,12,angle=-10)
        # Small marks are decorative, never fabricated claims or amenity icons.
        for x,y,dx,dy in [(110,530,55,-22),(80,588,64,0),(103,647,53,25)]:
            d.line((x,y,x+dx,y+dy),fill=contrast_ink(fg),width=7)
    else: # edge_closeup
        text(design.headline,(72,176,342,280),96)
        handwriting(design.subhead,(76,495,330,165),58)
        if brief.price is not None:
            r.price(d,brief,(72,700,350,150),fg,accent,muted,large=True)
        edge_photo(r,canvas,data,top_end,panel,fg,brief.product,design.image_fit)

    y=facts_y
    if price_h:
        r.price(d,brief,(72,y,936,price_h),facts_fg,facts_accent,facts_muted,
                large=design.emphasis=="price")
        y+=price_h
    r.text(d,detail,(72,y,936,detail_h),facts_fg,24,24);y+=detail_h+10
    if brief.period:
        r.text(d,brief.period,(72,y,936,period_h),facts_muted,22,22);y+=period_h
    if contact:
        r.text(d,contact,(72,y,936,contact_h),facts_muted,20,20);y+=contact_h
    d.line((72,y+10,1008,y+10),fill=facts_muted,width=1)
    r.text(d,design.cta,(72,y+24,936,40),facts_fg,24,18,True)
    output=BytesIO();canvas.save(output,"PNG",optimize=True)
    return output.getvalue()

