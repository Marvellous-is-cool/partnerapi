from fastapi_mail import ConnectionConfig
# from pydantic import EmailStr

email_conf = ConnectionConfig(
    MAIL_USERNAME="noreply@micoadmin.com",
    MAIL_PASSWORD="adpp tvcy iwnm jcgw",
    MAIL_FROM="noreply@micoadmin.com",
    MAIL_PORT=465,
    MAIL_FROM_NAME="Mico",
    MAIL_SERVER="smtp.gmail.com",
    MAIL_SSL_TLS=True,
    MAIL_STARTTLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)
