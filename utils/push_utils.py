from onesignal_sdk.client import Client
from onesignal_sdk.error import OneSignalHTTPError
from typing import Dict, Any, Optional
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OneSignal configuration
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID")
ONESIGNAL_REST_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY")

# Initialize the OneSignal client
onesignal_client = Client(app_id=ONESIGNAL_APP_ID, rest_api_key=ONESIGNAL_REST_API_KEY)

def send_push_notification(
    user_id: str, 
    message: str, 
    title: str = "New Message", 
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send a push notification to a user or rider using OneSignal.
    
    Args:
        user_id: The ID of the user or rider to send the notification to
        message: The message content
        title: The notification title
        data: Additional data to include with the notification
        
    Returns:
        Dict containing status and message
    """
    from database import get_user_by_id, get_rider_by_id, get_notification_user_by_id
    
    # Get the user or rider to check if push notifications are enabled
    receiver = get_user_by_id(user_id) or get_rider_by_id(user_id)
    if not receiver:
        error_message = f"Receiver not found with ID: {user_id}"
        logging.error(error_message)
        return {"status": "error", "message": error_message}
    
    # Check if push notifications are enabled
    if not receiver.get("push_notification", False):
        error_message = f"Push notifications are disabled for receiver {user_id}"
        logging.info(error_message)
        return {"status": "error", "message": error_message}
    
    # Get OneSignal device ID from noti collection
    noti_user = get_notification_user_by_id(user_id)
    if not noti_user:
        error_message = f"No notification registration found for user/rider {user_id}"
        logging.warning(error_message)
        return {"status": "error", "message": error_message}
    
    player_id = noti_user.get("external_user_id")
    if not player_id:
        error_message = f"No OneSignal player ID found for user/rider {user_id}"
        logging.warning(error_message)
        return {"status": "error", "message": error_message}
    
    # Create notification body
    notification_body = {
        'contents': {'en': message},
        'headings': {'en': title},
        'include_player_ids': [player_id],
    }
    
    # Add additional data if provided
    if data:
        notification_body['data'] = data
    
    # Send the notification
    try:
        response = onesignal_client.send_notification(notification_body)
        logging.info(f"[PUSH] Successfully sent OneSignal notification to {user_id}: {response.body}")
        return {
            "status": "success",
            "message": f"Notification sent successfully",
            "response": response.body
        }
    except OneSignalHTTPError as e:
        error_message = f"Error sending OneSignal notification: {str(e)}"
        logging.error(error_message)
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"Unexpected error sending notification: {str(e)}"
        logging.error(error_message)
        return {"status": "error", "message": error_message}