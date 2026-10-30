"""Synthetic labeled corpus. No detector reads these labels at runtime."""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.pdfgen import canvas


@dataclass(frozen=True)
class VisualFixture:
    name: str
    pdf: bytes
    target: str
    expected: str


def font(size: int) -> ImageFont.FreeTypeFont:
    # Pillow searches platform font directories; no Linux-only absolute path.
    return ImageFont.truetype('DejaVuSans.ttf', size)


def corpus() -> tuple[VisualFixture, ...]:
    result = []
    for kind in ('clean','black','grey','red','diagonal','white_text','hidden_text','overlay','clipped'):
        out = io.BytesIO()
        pdf = canvas.Canvas(out, pagesize=(600,300), invariant=1)
        pdf.setFont('Helvetica', 24)
        # Isolated target word makes independent region ground truth explicit.
        pdf.drawString(40,220,'1000')
        pdf.drawString(40,100,'Clean control 1200')
        if kind in ('black','grey','red','diagonal'):
            pdf.setStrokeColorRGB(*({'grey':(.6,.6,.6),'red':(1,0,0)}.get(kind,(0,0,0))))
            pdf.setLineWidth(1.5)
            pdf.line(38,228,98,232 if kind=='diagonal' else 228)
        if kind=='white_text':
            pdf.setFillColorRGB(1,1,1)
            pdf.drawString(250,220,'9000')
        if kind=='hidden_text':
            text = pdf.beginText(250,220)
            text.setTextRenderMode(3)
            text.textOut('9000')
            pdf.drawText(text)
        if kind=='overlay':
            pdf.setFillColorRGB(1,1,1)
            pdf.rect(35,215,80,30,fill=1,stroke=0)
        if kind=='clipped':
            pdf.saveState()
            path = pdf.beginPath()
            path.rect(500,20,30,30)
            pdf.clipPath(path,stroke=0)
            pdf.drawString(250,220,'9000')
            pdf.restoreState()
        pdf.showPage()
        pdf.save()
        result.append(VisualFixture(kind,out.getvalue(),'9000' if kind in ('white_text','hidden_text','clipped') else '1000',
                                    'clean' if kind=='clean' else 'review'))
    for kind in ('scan_clean','scan_strike','scan_blur','scan_insertion'):
        image=Image.new('RGB',(1200,600),'white')
        draw=ImageDraw.Draw(image)
        draw.text((80,120),'1000',font=font(72),fill='black')
        draw.text((80,350),'Clean control 1200',font=font(48),fill='black')
        if kind=='scan_strike':
            draw.line((75,160,285,160),fill='black',width=4)
        if kind=='scan_insertion':
            draw.text((330,120),'1200',font=font(72),fill='black')
            draw.line((300,200,315,180,330,200),fill='black',width=3)
        if kind=='scan_blur':
            image=image.filter(ImageFilter.GaussianBlur(12))
        out=io.BytesIO()
        pdf=canvas.Canvas(out,pagesize=(600,300),invariant=1)
        pdf.drawInlineImage(image,0,0,width=600,height=300)
        pdf.showPage()
        pdf.save()
        result.append(VisualFixture(kind,out.getvalue(),'1000','unsupported_scan' if kind!='scan_strike' else 'review'))
    return tuple(result)
