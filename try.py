import smtplib
from email.mime.text import MIMEText

EMAIL = "adebayoinioluwamarvellous1@gmail.com"
APP_PASSWORD = "awlm fhmz yvaz awxo"  # Just for testing here
TO = "andsowekilledit@example.com"

msg = MIMEText("This is a test email from Python.")
msg["Subject"] = "Testing email"
msg["From"] = EMAIL
msg["To"] = TO

try:
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL, APP_PASSWORD)
        server.sendmail(EMAIL, TO, msg.as_string())
    print("✅ Email sent successfully")
except Exception as e:
    print("❌ Failed to send email:", e)
