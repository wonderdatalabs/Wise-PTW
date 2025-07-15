import io
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# Open the screenshot
img = Image.open("Captura de tela 2025-05-01 204933.png")

# Create PDF with same dimensions as the image
img_width, img_height = img.size
pdf_buffer = io.BytesIO()
c = canvas.Canvas(pdf_buffer, pagesize=(img_width, img_height))
c.drawImage(ImageReader(img), 0, 0, width=img_width, height=img_height)
c.save()

# Write to file
with open("test_document.pdf", "wb") as f:
    pdf_buffer.seek(0)
    f.write(pdf_buffer.getvalue())

print("Created test_document.pdf successfully")