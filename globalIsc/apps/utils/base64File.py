# En tu función pdfToBase64, REEMPLAZA cualquier uso de pdfkit con xhtml2pdf

import base64
import io
from xhtml2pdf import pisa

def pdfToBase64(html_content):
    """
    Usa xhtml2pdf en lugar de pdfkit - NO necesita wkhtmltopdf
    """
    try:
        pdf_file = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            html_content, 
            dest=pdf_file,
            encoding='UTF-8'
        )
        
        if pisa_status.err:
            return {
                'pdf': '',
                'pages': 1,
                'error': f"Error xhtml2pdf: {pisa_status.err}"
            }
        
        pdf_base64 = base64.b64encode(pdf_file.getvalue()).decode('utf-8')
        pdf_file.close()
        
        # Estimar páginas
        estimated_pages = max(1, html_content.count('</div>') // 20)
        
        return {
            'pdf': pdf_base64,
            'pages': estimated_pages,
        }
        
    except Exception as e:
        return {
            'pdf': '',
            'pages': 1,
            'error': str(e)
        }