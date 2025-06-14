import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import List, Optional
from conf import email_conf
from fastapi_mail import FastMail, MessageSchema
from PIL import Image
import io

class EmailService:
    def __init__(self):
        # For FastAPI-Mail (simple HTML emails)
        self.fastmail = FastMail(email_conf)
        # For direct SMTP (inline images)
        self.smtp_host = email_conf.MAIL_SERVER
        self.smtp_port = email_conf.MAIL_PORT
        self.smtp_user = email_conf.MAIL_USERNAME
        
        # Extract actual string from SecretStr object
        if hasattr(email_conf.MAIL_PASSWORD, "get_secret_value"):
            self.smtp_password = email_conf.MAIL_PASSWORD.get_secret_value()
        else:
            self.smtp_password = email_conf.MAIL_PASSWORD
            
        self.smtp_from = email_conf.MAIL_FROM
        self.use_ssl = email_conf.MAIL_SSL_TLS
        self.use_tls = email_conf.MAIL_STARTTLS
        
        print(f"Email Service initialized with: {self.smtp_host}:{self.smtp_port}")
        print(f"SSL: {self.use_ssl}, TLS: {self.use_tls}")
    
    def resize_image(self, image_data, max_width=800, quality=85):
        """Resize an image to a reasonable size for email"""
        try:
            img = Image.open(io.BytesIO(image_data))
            
            # Calculate new height maintaining aspect ratio
            width_percent = max_width / float(img.width)
            new_height = int(float(img.height) * width_percent)
            
            # Resize the image
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert to bytes
            output = io.BytesIO()
            
            # Save with appropriate format and quality
            format = img.format if img.format else 'JPEG'
            if format.upper() == 'JPEG' or format.upper() == 'JPG':
                img.save(output, format=format, quality=quality)
            else:
                img.save(output, format=format)
                
            output.seek(0)
            return output.getvalue()
        except Exception as e:
            print(f"Warning: Could not resize image: {e}")
            return image_data  # Return original if resize fails
            
    async def send_email_with_image(
        self,
        subject: str,
        recipients: List[str],
        body: str,
        image_data: bytes,
        image_filename: str
    ) -> bool:
        """
        Send an email with inline image using direct SMTP connection.
        Optimized for Gmail with port 465 and SSL.
        """
        try:
            # Resize image to prevent issues with large images
            print(f"Original image size: {len(image_data)/1024:.1f} KB")
            image_data = self.resize_image(image_data)
            print(f"Resized image size: {len(image_data)/1024:.1f} KB")
            
            # Create message
            msg_root = MIMEMultipart('related')
            msg_root['Subject'] = subject
            msg_root['From'] = self.smtp_from
            msg_root['To'] = ", ".join(recipients)
            
            # Alternative part for HTML body
            msg_alternative = MIMEMultipart('alternative')
            msg_root.attach(msg_alternative)
            msg_alternative.attach(MIMEText(body, 'html'))
            
            # Attach the image as inline
            image = MIMEImage(image_data)
            image.add_header('Content-ID', '<inline_image>')
            image.add_header('Content-Disposition', 'inline', filename=image_filename)
            msg_root.attach(image)
            
            # Create context (for SSL/TLS)
            context = ssl.create_default_context()
            
            print(f"Connecting to {self.smtp_host}:{self.smtp_port} with SSL={self.use_ssl}")
            
            try:
                # For Gmail with port 465, use SMTP_SSL
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context)
                server.set_debuglevel(1)  # Enable debug output
                
                print(f"Authenticating as {self.smtp_user}...")
                # Make sure password is a string, not SecretStr
                server.login(self.smtp_user, self.smtp_password) 
                
                print(f"Sending email to {recipients}...")
                server.sendmail(self.smtp_from, recipients, msg_root.as_string())
                
                print("Closing connection...")
                server.quit()
                
                print("Email with image sent successfully")
                return True
                
            except Exception as smtp_error:
                print(f"SMTP Error: {smtp_error}")
                # Try alternative connection method as fallback
                if not self.use_ssl and self.use_tls:
                    print("Trying alternative connection with STARTTLS...")
                    server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                    server.set_debuglevel(1)
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_from, recipients, msg_root.as_string())
                    server.quit()
                    print("Email sent successfully with STARTTLS")
                    return True
                else:
                    raise
                    
        except Exception as e:
            print(f"Error sending email with image: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def send_email(self, subject: str, recipients: List[str], body: str) -> bool:
        """
        Send an email using FastAPI Mail (HTML only, no inline images).
        """
        try:
            message = MessageSchema(
                subject=subject,
                recipients=recipients,
                body=body,
                subtype="html"
            )
            await self.fastmail.send_message(message)
            print("Email sent successfully")
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
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
            {image_placeholder}
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