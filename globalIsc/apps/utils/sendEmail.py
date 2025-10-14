from django.core.mail import EmailMessage, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def sendEmail(subject, message, email, html_message=None):
    email_message = EmailMessage(
        subject=subject,
        body=message,
        to=[email]
    )
    if html_message:
        email_message.content_subtype = "html"  # Configura el tipo de contenido como HTML
        email_message.body = html_message  # Usa el mensaje HTML como cuerpo principal
    email_message.send()
    return email_message

def sendEmailWithTemplate(subject, template, context, email):
    htmlMessage = render_to_string(template, context)
    
    plainMessage = strip_tags(htmlMessage)
    
    email = send_mail(subject, plainMessage, None, email, html_message=htmlMessage)

    return email