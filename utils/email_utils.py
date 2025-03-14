import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

# Email configuration
SMTP_SERVER = "mail.micodelivery.com"  # Update with your mail server
SMTP_PORT = 465  # SSL port
SENDER_EMAIL = "info@micodelivery.com"
SENDER_PASSWORD = "Micoinfo123*"  # Update with actual password

def send_email(recipient_email: str, subject: str, body: str) -> bool:
    """
    Send an email using SMTP with SSL.
    Returns True if email was sent successfully, False otherwise.
    """
    try:
        # Create message
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = SENDER_EMAIL
        message["To"] = recipient_email

        # Create SMTP SSL session
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, message.as_string())

        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def send_reset_code_email(email: str, reset_code: str, user_type: str) -> bool:
    """
    Send password reset code email.
    """
    subject = "Password Reset Code - Delivery App"
    body = f"""
    Hello,

    You have requested to reset your password for your {user_type} account.
    Your password reset code is: {reset_code}

    This code will expire in 15 minutes.

    If you did not request this reset, please ignore this email.

    Best regards,
    Delivery App Team
    """
    
    return send_email(email, subject, body)