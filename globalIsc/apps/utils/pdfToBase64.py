import base64
import io
from xhtml2pdf import pisa

def pdfToBase64(html):
    """
    Versión SUPER SIMPLE - Solo genera el PDF y punto
    """
    try:
        pdf_file = io.BytesIO()
        
        # Generar PDF
        pisa_status = pisa.CreatePDF(html, dest=pdf_file)
        
        if pisa_status.err:
            return {'pdf': '', 'error': str(pisa_status.err)}
        
        # Convertir a base64
        pdf_base64 = base64.b64encode(pdf_file.getvalue()).decode('utf-8')
        
        return {'pdf': pdf_base64}
        
    except Exception as e:
        return {'pdf': '', 'error': str(e)}