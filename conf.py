from fastapi_mail import ConnectionConfig

email_conf = ConnectionConfig(
    MAIL_USERNAME="adebayoinioluwamarvellous1@gmail.com",
    MAIL_PASSWORD="awlm fhmz yvaz awxo",
    MAIL_FROM="adebayoinioluwamarvellous1@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_SSL_TLS= False,
    MAIL_STARTTLS=True,
    USE_CREDENTIALS=True,
)