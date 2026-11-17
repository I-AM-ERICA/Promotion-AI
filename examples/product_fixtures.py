"""Original geometric product illustrations for layout tests; not product photos."""
from io import BytesIO
from PIL import Image, ImageDraw


def product_fixture(kind):
    size = {"bottle": (330, 920), "shoe": (1000, 420), "box": (760, 600),
            "meal": (1300, 370), "set": (1000, 600), "jewelry": (650, 650)}[kind]
    image=Image.new("RGBA",size)
    d=ImageDraw.Draw(image)
    w,h=size
    if kind=="bottle":
        d.rounded_rectangle((45,240,w-45,h-22),radius=44,fill="#557A63")
        d.rounded_rectangle((83,150,w-83,300),radius=12,fill="#B59B63")
        d.rounded_rectangle((108,12,w-108,188),radius=45,fill="#2C352B")
        d.rectangle((62,410,w-62,725),fill="#ECE5CE")
        for y in (460,490,650):d.line((100,y,w-100,y),fill="#567364",width=5)
    elif kind=="shoe":
        d.polygon([(30,280),(200,210),(430,40),(620,90),(730,200),(930,220),(975,325),(48,365)],fill="#71918B")
        d.rounded_rectangle((20,320,980,405),radius=35,fill="#F0EBDE")
        for i in range(5):d.line((390+i*45,110+i*16,480+i*45,190+i*16),fill="#E9E9DC",width=13)
        d.line((90,365,920,365),fill="#B1BFB7",width=9)
    elif kind=="box":
        d.polygon([(30,165),(555,45),(730,170),(730,540),(200,590),(30,430)],fill="#BB8F60")
        d.polygon([(30,165),(555,45),(730,170),(200,300)],fill="#E4BD86")
        d.rectangle((340,320,610,490),fill="#F8EED6")
    elif kind=="meal":
        d.rounded_rectangle((15,15,w-15,h-15),radius=80,fill="#E4DECA")
        for i in range(6):
            x=55+i*195
            d.rounded_rectangle((x,65,x+170,305),radius=45,fill="#DED0A6")
            d.ellipse((x+15,80,x+155,290),fill=["#98633D","#679049","#D28954"][i%3])
    elif kind=="set":
        for i,color in enumerate(("#547F77","#D4AD78","#915D55")):
            x=40+i*320
            d.rounded_rectangle((x,145,x+275,580),radius=35,fill=color)
            d.rectangle((x+30,35,x+245,155),fill="#353C35")
            d.rectangle((x+35,285,x+240,470),fill="#ECE5D4")
    else:
        d.ellipse((90,90,560,560),outline="#A88842",width=78)
        d.ellipse((115,115,535,535),outline="#F0DDA6",width=20)
    return image


def fixture_bytes(kind):
    buffer=BytesIO();product_fixture(kind).save(buffer,"PNG")
    return buffer.getvalue()
