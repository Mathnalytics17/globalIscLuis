import base64
import pdfkit

def html_to_pdf_base64(html_content):
    # Convertir HTML a PDF en memoria
    pdf_bytes = pdfkit.from_string(html_content, False)

    # Codificar el archivo PDF en base64
    base64_encoded = base64.b64encode(pdf_bytes).decode('utf-8')

    return base64_encoded