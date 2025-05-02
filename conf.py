from fastapi_mail import ConnectionConfig

email_conf = ConnectionConfig(
    MAIL_USERNAME="8b597d001@smtp-brevo.com",
    MAIL_PASSWORD="DYANKtQw2jJpaOXL",
    MAIL_FROM="noreply@micoadmin.com",
    MAIL_FROM_NAME="Mico",
    MAIL_PORT=587,
    MAIL_SERVER="smtp-relay.brevo.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)
