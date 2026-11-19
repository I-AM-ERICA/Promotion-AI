"""Render six composition variants from a local photo; no CLOVA calls.

python -m examples.render_creative_gallery
python -m examples.render_creative_gallery --photo /path/photo.png --product 상품 --keep
"""
import argparse
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw
from promotion_assistant.creative_layouts import CREATIVE_IDS
from promotion_assistant.models import Brief, Design
from promotion_assistant.product_image import ProductProcessor
from promotion_assistant.renderer import Renderer
from promotion_assistant.templates import TEMPLATES

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--photo",type=Path)
    parser.add_argument("--product",default="에스프레소")
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--keep",action="store_true")
    mode.add_argument("--remove",action="store_true",help="Require background removal; fail visibly if segmentation fails")
    parser.add_argument("--output",type=Path,default=Path("outputs/creative-gallery"))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    original=(args.photo or Path("examples/assets/coffee.jpg")).read_bytes()
    processed=ProductProcessor().process(original,"keep" if args.keep else "remove" if args.remove else "auto")
    (args.output/"processed.png").write_bytes(processed.data)
    renderer=Renderer()
    brief=Brief(store={"store_id":"creative-example","name":"시안 미리보기"},product=args.product,
                message="같은 사진으로 비교하는 다양한 구도",price=None if args.photo else 3500)
    sheet=Image.new("RGB",(1128,1070),"#F5F4EF")
    draw=ImageDraw.Draw(sheet)
    draw.text((24,16),"같은 사진 · 새로운 구도 6개 / 검증용 문구",font=renderer.font(25,True),fill="#293C31")
    chosen=[t for t in TEMPLATES if t.id in CREATIVE_IDS]
    for i,template in enumerate(chosen):
        design=Design(template_id=template.id,palette=template.palette,headline="일상의 새로운 즐거움",
                      subhead="오늘을 조금 더 특별하게",
                      image_fit="cover" if template.id in ("edge_closeup","photo_mood") else "contain")
        png=renderer.render(brief,design,original if template.id=="photo_mood" else processed.data)
        (args.output/(template.id+".png")).write_bytes(png)
        image=Image.open(BytesIO(png));image.thumbnail((348,435))
        x,y=24+(i%3)*372,70+(i//3)*495
        sheet.paste(image,(x,y))
        draw.text((x,y+449),template.name,font=renderer.font(22,True),fill="#293C31")
    sheet.save(args.output/"comparison.png")
    print(f"Background: {processed.status}")
    if processed.warning:
        print(processed.warning)
    print(args.output.resolve())

if __name__=="__main__":
    main()

