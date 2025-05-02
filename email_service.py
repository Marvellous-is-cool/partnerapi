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
                subtype="html"
            )
            
            print(f"Attempting to send email to: {recipients}")
            print(f"Subject: {subject}")
            
            await self.fastmail.send_message(message)
            print("Email sent successfully")
            return True
            
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            print(f"Recipients: {recipients}")
            print(f"Subject: {subject}")
            return False
        
    def rider_signup_template(self, firstname: str) -> str:
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
            <h2 style="color: #333;">Welcome aboard, {firstname}! 🚀</h2>
            <p style="font-size: 16px; color: #555;">You're now part of the Mico Delivery team as a rider. We're excited to have you!</p>
            <p style="font-size: 14px; color: #777;">We'll keep you posted on delivery requests and updates.</p>
            <hr style="margin: 20px 0;">
            <p style="font-size: 14px; color: #777;">Once again we appreciate your interest in being a part of MICO Delivery.</p>
            <p style="font-size: 14px; color: #777;">Our customers app is currently live on playstore and apple store and customers are downloading the app.</p>
            <p style="font-size: 14px; color: #777;">We are still utilizing our marketing advertisement to ensure we have many customers download our app so you'd always have delivery orders on the app.</p>
            <p style="font-size: 14px; color: #777;">Most importantly, as one of our financial policies, you are expected to remit all payments due to MICO from all successful delivery orders carried out on or before 12pm daily. All payments are to be sent to;</p>
            <br />
            <p>MICO DELIVERY LTD
            <br />
            MONIEPOINT
            <br />
            8029323758</p>
            <br />
            <p style="font-size: 14px; color: #777;">Thank you for choosing MICO
            <br />MICO Delivery Team </p>
            <p style="font-size: 12px; color: #999;">
                This email was sent to you because you registered as a rider on the Mico platform. If this wasn't you, you can ignore this message.
            </p>
            </div>
        </body>
        </html>
        """
 
    def user_signup_template(self, firstname: str) -> str:
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
            <h2 style="color: #333;">Hi {firstname}, welcome to Mico! 👋</h2>
            <p style="font-size: 16px; color: #555;">Thanks for signing up as a user. We're glad to have you with us.</p>
            <p style="font-size: 14px; color: #777;">Start requesting deliveries and track them in real-time anytime!</p>
            <hr style="margin: 20px 0;">
            <p style="font-size: 12px; color: #999;">
                This email was sent to you because you registered as a user on the Mico platform. If this wasn't you, you can ignore this message.
            </p>
            </div>
        </body>
        </html>
        """


   
    def delivery_template(self, status: str, delivery_id: str) -> str:
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
            <h2 style="color: #333;">📦 Delivery Update</h2>
            <p style="font-size: 16px; color: #555;">Your delivery with ID <strong>{delivery_id}</strong> has been updated.</p>
            <p style="font-size: 16px; color: #333;"><strong>Status:</strong> {status.capitalize()}</p>
            <hr style="margin: 20px 0;">
            <p style="font-size: 12px; color: #999;">
                You're receiving this because you are involved in this delivery on Mico. If this isn't relevant to you, you may disregard it.
            </p>
            </div>
        </body>
        </html>
        """

    
    def custom_email_template(self, message: str) -> str:
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
            <div style="font-size: 16px; color: #555;">
                {message}
            </div>
            <hr style="margin: 20px 0;">
            <p style="font-size: 12px; color: #999;">
                This email was sent from Mico's platform. If you have questions, reply to this message or contact support.
            </p>
            </div>
        </body>
        </html>
        """
