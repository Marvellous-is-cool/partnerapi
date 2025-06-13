from fastapi_mail import FastMail, MessageSchema, MessageType
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import List, Optional
from conf import email_conf


class EmailService:
    def __init__(self):
        self.fastmail = FastMail(email_conf)
        
    async def send_email_with_image(
        self,
        subject: str,
        recipients: List[str],
        body: str,
        image_data: Optional[bytes] = None,
        image_filename: Optional[str] = None
    ) -> bool:
        """
        Send an email with an optional inline image attachment.
        The image can be referenced in the HTML body using <img src="cid:inline_image">
        """
        try:
            # If no image, just use regular send_email method
            if not image_data:
                return await self.send_email(subject, recipients, body)
            
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.image import MIMEImage
            from fastapi_mail import MessageSchema, MessageType
            import uuid
        
            # Generate unique ID for this email
            email_id = str(uuid.uuid4())
            
            # Create a multipart/related message
            message_container = MIMEMultipart('related')
            message_container["Subject"] = subject
            message_container["From"] = self.fastmail.config.MAIL_FROM
            message_container["To"] = ", ".join(recipients)
            
            # Add HTML part
            html_part = MIMEText(body, "html")
            message.attach(html_part)
            
            # Add image if provided
            if image_data:
                image = MIMEImage(image_data)
                image_cid = f'<inline_image_{email_id}>'
                image.add_header('Content-ID', image_cid)
                image.add_header('Content-Disposition', 'inline', filename=image_filename or 'image.jpg')
                message.attach(image)
            
            # Create MessageSchema with the complete MIME message
            email_msg = MessageSchema(
                subject=subject,
                recipients=recipients,
                body=message.as_string(),
                subtype=MessageType.plain  # Using plain because we're providing the full MIME message
            )
            
            # Send the email
            await self.fastmail.send_message(email_msg)
            print("Email with image sent successfully")
            return True
            
        except Exception as e:
            print(f"Error sending email with image: {str(e)}")
            print(f"Recipients: {recipients}")
            print(f"Subject: {subject}")
            return False
        

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

    
    def new_delivery_notification_template(self, rider_name: str, delivery_id: str, distance_km: float, pickup_address: str) -> str:
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
            <h2 style="color: #333;">🚚 New Delivery Available, {rider_name}!</h2>
            <p style="font-size: 16px; color: #555;">A new delivery request is available near your location.</p>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p style="margin: 5px 0;"><strong>Delivery ID:</strong> {delivery_id}</p>
                <p style="margin: 5px 0;"><strong>Distance:</strong> {distance_km} km from your location</p>
                <p style="margin: 5px 0;"><strong>Pickup:</strong> {pickup_address}</p>
            </div>
            
            <p style="font-size: 14px; color: #777;">Open your rider app to view details and accept this delivery.</p>
            
            <hr style="margin: 20px 0;">
            <p style="font-size: 12px; color: #999;">
                You're receiving this because you're an active rider with email notifications enabled. 
                You can disable these notifications in your rider app settings.
            </p>
            </div>
        </body>
        </html>
        """
    
    
    def custom_email_template(self, message: str, has_image: bool = False) -> str:
        image_placeholder = '<img src="cid:inline_image" style="max-width: 100%; margin: 20px 0;" alt="Attached Image">' if has_image else ''
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
            <div style="font-size: 16px; color: #555;">
                {message}
            </div>
            {image_placeholder}
            <hr style="margin: 20px 0;">
            <p style="font-size: 12px; color: #999;">
                This email was sent from Mico's platform. If you have questions, reply to this message or contact support.
            </p>
            </div>
        </body>
        </html>
        """
