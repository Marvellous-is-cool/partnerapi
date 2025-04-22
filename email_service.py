from fastapi_mail import FastMail, MessageSchema
from conf import email_conf
from typing import List

class EmailService:
    def __init__(self):
        self.fastmail = FastMail(email_conf)

    async def send_email(self, subject: str, recipients: List[str], body: str) -> bool:
        """
        Send an email using FastAPI Mail.
        """
        
        try: 
            message = MessageSchema(
                subject=subject,
                recipients=recipients,
                body=body,
                subtype="html",
            )
            await self.fastmail.send_message(message)
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
        
    def rider_signup_template(self, firstname: str) -> str:
        """
        Generate the email template for rider signup.
        """
        return f"""
        <html>
            <body>
                <h1>Welcome {firstname}!</h1>
                <p>Thank you for signing up as a rider.</p>
            </body>
        </html>
        """
        
    def user_signup_template(self, firstname: str) -> str:
        """
        Generate the email template for user signup.
        """
        return f"""
        <html>
            <body>
                <h1>Welcome {firstname}!</h1>
                <p>Thank you for signing up as a user.</p>
            </body>
        </html>
        """
    
    def delivery_template(self, status: str, delivery_id: str) -> str:
        """
        Generate the email template for delivery.
        """
        return f"""
        <html>
            <body>
                <h1>Delivery Notification</h1>
                <p>Your delivery (ID: {delivery_id}) status has been updated to: {status}</p>
            </body>
        </html>
        """
        
    def custom_email_template(self, message: str) -> str:
        """
        Generate a template for custom email messages.
        """
        return f"""
        <html>
            <body>
                <div style="padding: 20px; background-color: #f7f7f7;">
                    {message}
                </div>
            </body>
        </html>
        """