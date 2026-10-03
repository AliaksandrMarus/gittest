"""Сводный векторный PDF А3 из листов sheets/*.svg (pip install cairosvg pypdf)."""
import glob
import io
import os

import cairosvg
import pypdf

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
writer = pypdf.PdfWriter()
for f in sorted(glob.glob(os.path.join(ROOT, "sheets", "*.svg"))):
    writer.append(io.BytesIO(cairosvg.svg2pdf(url=f)))
out = os.path.join(ROOT, "Проект_дом_9x12_Бобруйск.pdf")
writer.write(out)
print("ok", out)
