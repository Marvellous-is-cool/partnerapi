import asyncio
from fastapi import FastAPI, File, Form, UploadFile, HTTPException,Body, Query, WebSocket, WebSocketDisconnect
from schemas.delivery_schema import CreateDeliveryRequest, OfflineDeliveryRequest, RiderSignup, BikeDeliveryRequest, CarDeliveryRequest, ScheduledDeliveryRequest, TransactionUpdateRequest, RiderLocationUpdate
from firebase_admin import messaging, credentials
import base64
from database import (
    get_all_deliveries,
    get_delivery_by_id,
    get_rider_by_email,
    get_rider_by_phone,
    get_user_by_phone,
    insert_delivery,
    insert_rider,
    ping_database,
    get_rider_by_id,
    get_all_riders,
    insert_user,
    get_user_by_email,
    get_user_by_id,
    insert_admin,
    get_admin_by_email,
    get_admin_by_username,
    get_admin_by_id,
    get_all_users,
    get_all_admins,
    update_rider_location_db,
    update_rider_status,
    update_rider_details_db,
    update_admin_role,
    update_admin_details_db,
    update_user_details_db,
    update_delivery,
    get_file_by_id,
    create_chat,
    get_chat_history,
    mark_messages_as_read,
    rate_rider,
    rate_user,
    get_rider_ratings,
    get_user_ratings,
    delete_rider_by_id,
    delete_admin_by_id,
    delete_delivery_by_id,
    delete_user_by_id,
    delete_selected_riders,
    delete_selected_users,
    delete_all_deliveries,
    get_file_by_id,
    get_user_by_id, 
    get_rider_by_id,
    riders_collection,
    archive_delivery,
    permanently_delete_delivery,
    restore_delivery,
    get_archived_deliveries,
    archived_deliveries_collection,
    delivery_collection
)
import hashlib
from fastapi import BackgroundTasks, Depends
import random
import string
from datetime import datetime, timedelta
from utils.email_utils import send_reset_code_email 
from utils.push_utils import send_push_notification
from schemas.delivery_schema import BikeDeliveryRequest, CarDeliveryRequest
from typing import Optional
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Dict, Any
from pydantic import BaseModel, EmailStr
from fastapi.responses import Response 
import os
from onesignal_sdk.client import Client
from onesignal_sdk.error import OneSignalHTTPError

from fastapi import BackgroundTasks, HTTPException
from email_service import EmailService
from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

import os
from geocoding import GoogleMapsService, get_coordinates
import json
import hashlib
import string
import random
from typing import Dict, Set

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": str(e),
                    "detail": "Internal server error"
                }
            )

from fastapi import BackgroundTasks
from email_service import EmailService
from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyQuery
from fastapi import Security

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import pytz

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()


api_key_query = APIKeyQuery(name="admin_key", auto_error=True)
ADMIN_DELETE_KEY = os.getenv("ADMIN_DELETE_KEY")

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": str(e),
                    "detail": "Internal server error"
                }
            )
            
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.rider_locations: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, rider_id: str):
        await websocket.accept()
        self.active_connections[rider_id] = websocket
        print(f"Rider {rider_id} connected via WebSocket")

    def disconnect(self, rider_id: str):
        if rider_id in self.active_connections:
            del self.active_connections[rider_id]
        print(f"Rider {rider_id} disconnected from WebSocket")

    async def send_personal_message(self, message: dict, rider_id: str):
        if rider_id in self.active_connections:
            try:
                await self.active_connections[rider_id].send_text(json.dumps(message))
                return True
            except:
                self.disconnect(rider_id)
                return False
        return False

    async def broadcast_new_delivery(self, message: dict, nearby_rider_ids: list):
        """Send real-time delivery notifications to nearby riders"""
        successful_sends = 0
        for rider_id in nearby_rider_ids:
            if await self.send_personal_message(message, rider_id):
                successful_sends += 1
        return successful_sends
    
    
class EmailWithAttachments(BaseModel):
    email: str
    subject: str
    body: str
    attachments: Optional[List[dict]] = None
    
# import os
# from onesignal_sdk.client import Client
# from onesignal_sdk.error import OneSignalHTTPError

app = FastAPI()

# ================== Middleware Configuration =================
app.add_middleware(ErrorHandlingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================= Email Configuration =================
# initialize the email service
email_service = EmailService()

class EmailRequest(BaseModel):
    email: EmailStr
    subject: str
    body: str
    
    @property
    def message(self):
        return self.body



class DeleteRequest(BaseModel):
    ids: List[str]
    
    
    
# Initialize the connection manager
manager = ConnectionManager()


@app.get("/")
def read_root():
    """
    Root endpoint to confirm API is running.
    """
    return {"message": "Welcome to the Delivery App API"}

# Initialize the app if not already initialized
# try:
#     app = firebase_admin.get_app()
# except ValueError:
#     # Initialize the app with credentials
#     try:
#         cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
#         app = firebase_admin.initialize_app(cred)
#     except Exception as e:
#         print(f"Failed to initialize Firebase Admin SDK: {e}")
#         app = None


@app.on_event("startup")
async def load_scheduled_deliveries():
    """
    Load all pending scheduled deliveries into the scheduler at startup.
    This ensures deliveries are still processed if the server restarts.
    """
    try:
        # Query for scheduled deliveries that haven't been processed yet
        query = {
            "is_scheduled": True,
            "scheduled_status": "pending",
            "scheduled_datetime": {"$gt": datetime.utcnow()}
        }
        
        scheduled_deliveries = list(delivery_collection.find(query))
        for delivery in scheduled_deliveries:
            delivery_id = str(delivery["_id"])
            scheduled_datetime = delivery["scheduled_datetime"]
            
            # Add to scheduler
            add_scheduled_delivery_to_queue(delivery_id, scheduled_datetime)
            
        print(f"Loaded {len(scheduled_deliveries)} pending scheduled deliveries")
    except Exception as e:
        print(f"Error loading scheduled deliveries: {str(e)}")


@app.get("/ping")
def test_database_connection():
    """
    Endpoint to test MongoDB connection.
    """
    if ping_database():
        return {"status": "success", "message": "MongoDB connection is successful!"}
    else:
        return {"status": "error", "message": "Failed to connect to MongoDB."}


# Function to hash password using SHA-256
def hash_password_sha256(password: str) -> str:
    """
    Hash the password using SHA-256 algorithm.
    """
    sha256_hash = hashlib.sha256()
    sha256_hash.update(password.encode("utf-8"))
    return sha256_hash.hexdigest()


# ================= Rider Endpoints =================
@app.post("/ridersignup")
async def rider_signup(
    firstname: str = Form(...),
    lastname: str = Form(...),
    gender: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    emergency_contact_name: str = Form(...),
    emergency_contact_phone: str = Form(...),
    accountbank: str = Form(...),
    accountname: str = Form(...),
    accountnumber: str = Form(...),
    # bvn: str = Form(...),
    homeaddressdetails: str = Form(...),
    branding: str = Form(...),
    vehicle_type: str = Form(...),
    nationalid: UploadFile = File(...),
    recent_facial_picture: UploadFile = File(...),
    recent_utility_bill: UploadFile = File(None),
    registration_papers: UploadFile = File(...),
    license: UploadFile = File(...),
    email_notification: bool = Form(True),
    push_notification: bool = Form(True),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Endpoint to handle rider signup with required details and multiple file uploads.
    """
    # Validate vehicle type
    if vehicle_type.lower() not in ["bike", "car", "bus", "truck"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid vehicle type. Must be 'bike', 'car', 'bus' or 'truck'."
        )

    # Hash the password using SHA-256
    hashed_password = hash_password_sha256(password)

    # Prepare the rider data
    rider_data = {
        "firstname": firstname,
        "lastname": lastname,
        "gender": gender,
        "email": email,
        "phone": phone,
        "password": hashed_password,
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_phone": emergency_contact_phone,
        "accountbank": accountbank,
        "accountname": accountname,
        "accountnumber": accountnumber,
        # "bvn": bvn,
        "homeaddressdetails": homeaddressdetails,
        "branding": branding,
        "vehicle_type": vehicle_type.lower(),
        "email_notification": email_notification,
        "push_notification": push_notification,
        "earnings": 0,
        "status": "inactive",
        "date_joined": datetime.now(),
        "facial_picture_url": None,  # This will be updated after file upload
        "is_online": False,
        "last_online": None,
        "last_offline": datetime.now(),
        "last_activity": datetime.now(),
        "current_location": None
    }

    # Read the uploaded files
    nationalid_file = await nationalid.read()
    facial_picture = await recent_facial_picture.read()
    utility_bill = await recent_utility_bill.read() if recent_utility_bill else None
    registration_papers_file = await registration_papers.read()
    license_file = await license.read()

    # Insert rider data into MongoDB and save the uploaded files in GridFS
    rider_id, file_ids = insert_rider(
        rider_data,
        nationalid_file,
        facial_picture,
        utility_bill,
        registration_papers_file,
        license_file,
    )

    # Update the facial_picture_url
    facial_pic_id = file_ids.get("facial_picture")
    if facial_pic_id:
        facial_picture_url = f"https://deliveryapi-ten.vercel.app/files/{facial_pic_id}"
        update_rider_details_db(rider_id, {"facial_picture_url": facial_picture_url})
        rider_data["facial_picture_url"] = facial_picture_url

    
    if rider_id:
        # Send a welcome email in background
        background_tasks.add_task(
            email_service.send_email,
            subject="Welcome to Delivery App",
            recipients=[email],
            body=email_service.rider_signup_template(firstname)
        )    
    
    return {
        "status": "success",
        "message": "Rider signed up successfully!",
        "rider_id": rider_id,
        "file_ids": file_ids,
        "facial_picture_url": rider_data["facial_picture_url"]
    }


@app.post("/ridersignin")
async def rider_signin(
    phone: str = Form(...), 
    password: str = Form(...),
):
    """
    Endpoint to handle rider sign-in. Verifies phone and password (SHA-256 hash).
    """
    # Hash the password for comparison
    hashed_password = hash_password_sha256(password)

    # Find the rider in the database
    rider = get_rider_by_phone(phone)

    if rider and rider["password"] == hashed_password:
        # Convert ObjectId to string for serialization
        rider_id = str(rider["_id"])
        
            
        # Return rider data
        rider["_id"] = rider_id
        return {
            "status": "success",
            "message": "Rider signed in successfully!",
            "rider": rider,  # Return full rider data
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")


# update rider online status
@app.put("/riders/{rider_id}/online-status")
async def update_rider_online_status(
    rider_id: str,
    data: dict = Body(...)
):
    """
    Update a rider's online status.
    Expects a JSON body with "is_online" field.
    """
    try:
        # Validate input
        is_online = data.get("is_online")
        if is_online is None:
            raise HTTPException(
                status_code=400,
                detail="Missing required field: is_online"
            )
        
        # Check if rider exists
        rider = get_rider_by_id(rider_id)
        if not rider:
            raise HTTPException(
                status_code=404,
                detail="Rider not found"
            )
        
        # Update appropriate timestamps based on status change
        update_data = {
            "is_online": is_online,
            "last_activity": datetime.utcnow()
        }
        
        if is_online:
            update_data["last_online"] = datetime.utcnow()
        else:
            update_data["last_offline"] = datetime.utcnow()
        
        success = update_rider_details_db(rider_id, update_data)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update rider's online status"
            )
        
        status_text = "activated" if is_online else "deactivated"
        return {
            "status": "success",
            "message": f"Rider's online status {status_text} successfully",
            "rider_id": rider_id,
            "is_online": is_online,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error updating rider online status: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred: {str(e)}"
        )


# @app.put("/riders/{rider_id}/online-status")
# async def update_rider_online_status(
#     rider_id: str,  
#     data: dict = Body(...)
# ):
#     """
#     Endpoint to update rider's online status.
#     """
    
#     # Extract online status from the request body.
#     online = data.get("online", False)
    
#     # Get the rider first
#     rider = get_rider_by_id(rider_id)
    
#     if not rider:
#         raise HTTPException(status_code=404, detail="Rider not found")
    
#     # Verify rider account is active
#     if rider.get("status") != "active":
#         raise HTTPException(status_code=403, detail="Rider account is not active, can't update status")
    
#     # prepare update data
#     update_online_data = {
#         "is_online": online,
#         "last_online": datetime.now() if online else None,
#         "last_offline": datetime.now() if not online else None,
#         "last_activity": datetime.now()
#     }
    
#     # Update rider online status in database
#     success = update_rider_details_db(rider_id, update_online_data)
    
#     if not success:
#         raise HTTPException(status_code=500, detail="Failed to update rider online status")
    
#     return {
#         "status": "success",
#         "message": f"Rider is now {'online' if online else 'offline'}",
#         "rider_id": rider_id,
#         "online": online
#     }

@app.put("/riders/{rider_id}/deactivate-online")
async def deactivate_rider_online_status(
    rider_id: str,
):
    """
    Endpoint to deactivate a rider's online status.
    This will set is_online to False and update last_offline timestamp.
    """
    
    try:
        # Get the rider first
        rider = get_rider_by_id(rider_id)
        
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        # Verify rider account is active
        if rider.get("status") != "active":
            raise HTTPException(
                status_code=403, 
                detail="Account is not active. Rider is not available for delivery"
            )
        
        # Prepare update data
        update_data = {
            "is_online": False,
            "last_offline": datetime.now(),
            "last_activity": datetime.now()
        }
        
        # Update rider online status in database
        success = update_rider_details_db(rider_id, update_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update rider online status")
        
        return {
            "status": "success",
            "message": "Rider is now offline",
            "rider_id": rider_id,
            "timestamp": datetime.now().isoformat()
        }
            
    except HTTPException as e: 
        raise e
    except Exception as e:
        print(f"Error deactivating rider {rider_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to deactivate rider: {str(e)}")
   
# check rider online status
@app.get("/riders/{rider_id}/online-status")
async def check_rider_online_status(
    rider_id: str,
):
    """
    Endpoint to check rider's online status.
    """
    # Get the rider first
    rider = get_rider_by_id(rider_id)
    
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    # Verify rider account is active
    if rider.get("status") != "active":
        raise HTTPException(
            status_code=403, 
            detail="Account is not active. Rider is not available for delivery"
        )
    
    return {
        "status": "success",
        "rider_id": rider_id,
        "is_online": rider.get("is_online", False),
        "last_online": rider.get("last_online"),
        "last_offline": rider.get("last_offline"),
        "last_activity": rider.get("last_activity"),
        "current_location": rider.get("current_location")
    }

@app.get("/riders/{rider_id}/details")
async def get_rider_details(rider_id: str):
    """
    Get comprehensive details about a rider including metrics, earnings, and delivery history.
    """
    try:
        # Get rider information
        rider = get_rider_by_id(rider_id)
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
            
        # Convert ObjectId to string for serialization
        rider_id_str = str(rider["_id"])
        rider["_id"] = rider_id_str
            
        # Get all deliveries for this rider
        rider_deliveries = list(delivery_collection.find({"rider_id": rider_id_str}))
        
        # Calculate delivery metrics
        total_deliveries = len(rider_deliveries)
        completed_deliveries = len([d for d in rider_deliveries if d.get("status", {}).get("current") == "completed"])
        canceled_deliveries = len([d for d in rider_deliveries if d.get("status", {}).get("current") == "cancelled"])
        rejected_deliveries = len([d for d in rider_deliveries if d.get("status", {}).get("current") == "rejected"])
        ongoing_deliveries = len([d for d in rider_deliveries if d.get("status", {}).get("current") in ["ongoing", "inprogress"]])
        
        # Calculate earnings
        total_earnings = rider.get("earnings", 0)
        # If earnings are not tracked in rider object, calculate from deliveries
        if total_earnings == 0:
            total_earnings = sum([d.get("price", 0) * 0.7 for d in rider_deliveries if d.get("status", {}).get("current") == "completed"])
        
        # Get rating information
        ratings = get_rider_ratings(rider_id_str)
        average_rating = 0
        if ratings:
            average_rating = sum(r.get("rating", 0) for r in ratings) / len(ratings)
        
        # Time analytics
        current_time = datetime.utcnow()
        
        # Calculate days active
        days_active = 0
        if rider.get("date_joined"):
            date_joined = rider["date_joined"] if isinstance(rider["date_joined"], datetime) else datetime.fromisoformat(rider["date_joined"].replace('Z', '+00:00'))
            days_active = (current_time - date_joined).days
        
        # Format recent deliveries for display
        recent_deliveries = sorted(
            rider_deliveries, 
            key=lambda x: x.get("last_updated", datetime.min) if isinstance(x.get("last_updated"), datetime) else datetime.min, 
            reverse=True
        )[:5]
        
        formatted_deliveries = []
        for delivery in recent_deliveries:
            formatted_deliveries.append({
                "delivery_id": str(delivery.get("_id")),
                "price": delivery.get("price", 0),
                "status": delivery.get("status", {}).get("current", "unknown"),
                "date": delivery.get("last_updated").isoformat() if isinstance(delivery.get("last_updated"), datetime) else delivery.get("last_updated"),
                "pickup": delivery.get("startpoint", {}).get("address", "Unknown location") if isinstance(delivery.get("startpoint"), dict) else delivery.get("startpoint", "Unknown"),
                "destination": delivery.get("endpoint", {}).get("address", "Unknown location") if isinstance(delivery.get("endpoint"), dict) else delivery.get("endpoint", "Unknown"),
                "vehicle_type": delivery.get("vehicletype", "unknown")
            })
        
        return {
            "status": "success",
            "rider": {
                "id": rider_id_str,
                "firstname": rider.get("firstname", ""),
                "lastname": rider.get("lastname", ""),
                "fullname": f"{rider.get('firstname', '')} {rider.get('lastname', '')}",
                "email": rider.get("email", ""),
                "phone": rider.get("phone", ""),
                "account_status": rider.get("status", ""),
                "vehicle_type": rider.get("vehicle_type", ""),
                "date_joined": rider.get("date_joined").isoformat() if isinstance(rider.get("date_joined"), datetime) else rider.get("date_joined", ""),
                "is_online": rider.get("is_online", False),
                "last_activity": rider.get("last_activity").isoformat() if isinstance(rider.get("last_activity"), datetime) else rider.get("last_activity", "")
            },
            "metrics": {
                "total_deliveries": total_deliveries,
                "completed_deliveries": completed_deliveries,
                "canceled_deliveries": canceled_deliveries,
                "rejected_deliveries": rejected_deliveries,
                "ongoing_deliveries": ongoing_deliveries,
                "pending_deliveries": total_deliveries - (completed_deliveries + canceled_deliveries + rejected_deliveries + ongoing_deliveries),
                "completion_rate": round(completed_deliveries / total_deliveries * 100, 1) if total_deliveries > 0 else 0,
                "cancellation_rate": round(canceled_deliveries / total_deliveries * 100, 1) if total_deliveries > 0 else 0,
                "total_earnings": round(total_earnings, 2),
                "days_active": days_active,
                "average_earnings_per_delivery": round(total_earnings / completed_deliveries, 2) if completed_deliveries > 0 else 0,
                "average_deliveries_per_day": round(total_deliveries / max(days_active, 1), 1)
            },
            "ratings": {
                "average_rating": round(average_rating, 1),
                "total_ratings": len(ratings),
                "5_star_ratings": len([r for r in ratings if r.get("rating", 0) == 5]),
                "4_star_ratings": len([r for r in ratings if r.get("rating", 0) == 4]),
                "3_star_ratings": len([r for r in ratings if r.get("rating", 0) == 3]),
                "2_star_ratings": len([r for r in ratings if r.get("rating", 0) == 2]),
                "1_star_ratings": len([r for r in ratings if r.get("rating", 0) == 1])
            },
            "recent_deliveries": formatted_deliveries,
            "location": rider.get("current_location", {}),
            "generated_at": current_time.isoformat()
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error getting rider details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get rider details: {str(e)}")


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two points using the Haversine formula.
    Returns distance in kilometers.
    """
    from math import radians, sin, cos, sqrt, atan2
    
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    radius = 6371  # Radius of Earth in kilometers
    
    return radius * c

def find_nearby_riders(pickup_latitude: float, pickup_longitude: float, vehicle_type: str, max_distance_km: float = 10.0):
    """
    Find nearby riders for a delivery.
    """
    try:
        # Query for active, online riders with the specified vehicle type
        query = {
            "is_online": True,
            "status": "active",
            "vehicle_type": vehicle_type.lower()
        }
        
        online_riders = list(riders_collection.find(query))    
        nearby_riders = []
        
        for rider in online_riders:
            rider_location = rider.get("current_location")
            if rider_location and "latitude" in rider_location and "longitude" in rider_location:
                distance = calculate_distance(
                    pickup_latitude, pickup_longitude,
                    rider_location["latitude"], rider_location["longitude"]
                )
                
                if distance <= max_distance_km:
                    rider["_id"] = str(rider["_id"])  # Convert ObjectId to string
                    rider["distance_km"] = round(distance, 2)
                    nearby_riders.append(rider)
                    
        # Sort by distance - nearest first
        nearby_riders.sort(key=lambda x: x["distance_km"])
        return nearby_riders
    
    except Exception as e:
        print(f"Error finding nearby riders: {e}")
        return []

def calculate_dynamic_radius(delivery_details: dict) -> float:
    """
    Calculate search radius based on delivery urgency, value, and other factors
    """
    base_radius = 10.0  # Default 10km
    
    # Adjust based on delivery speed/urgency
    delivery_speed = delivery_details.get("deliveryspeed", "standard")
    if delivery_speed == "express":
        urgency_multiplier = 1.5  # Wider search for urgent deliveries
    else:
        urgency_multiplier = 1.0
    
    # Adjust based on delivery value
    price = delivery_details.get("price", 0)
    if price >= 100:
        value_multiplier = 1.8  # Much wider search for high-value deliveries
    elif price >= 50:
        value_multiplier = 1.4
    elif price >= 20:
        value_multiplier = 1.2
    else:
        value_multiplier = 1.0
    
    # Adjust based on package size (larger packages need more capable riders)
    package_size = delivery_details.get("packagesize", "small")
    if package_size.lower() in ["large", "xl", "extra large"]:
        size_multiplier = 1.3
    elif package_size.lower() in ["medium", "m"]:
        size_multiplier = 1.1
    else:
        size_multiplier = 1.0
    
    # Adjust based on time of day (wider search during off-peak hours)
    current_hour = datetime.utcnow().hour
    if current_hour < 8 or current_hour > 20:  # Early morning or late evening
        time_multiplier = 1.6
    elif current_hour < 10 or current_hour > 18:  # Morning or evening
        time_multiplier = 1.3
    else:
        time_multiplier = 1.0
    
    # Calculate final radius
    final_radius = base_radius * urgency_multiplier * value_multiplier * size_multiplier * time_multiplier
    
    # Cap the radius (minimum 5km, maximum 50km)
    final_radius = max(5.0, min(50.0, final_radius))
    
    print(f"Dynamic radius calculated: {final_radius:.1f}km (base: {base_radius}, urgency: {urgency_multiplier}, value: {value_multiplier}, size: {size_multiplier}, time: {time_multiplier})")
    
    return final_radius

def get_urgency_level(delivery_details: dict) -> str:
    """Get urgency level for delivery"""
    delivery_speed = delivery_details.get("deliveryspeed", "standard")
    price = delivery_details.get("price", 0)
    
    if delivery_speed == "express" and price >= 50:
        return "critical"
    elif delivery_speed == "express":
        return "high"
    elif price >= 30:
        return "medium"
    else:
        return "low"

def calculate_estimated_earnings(delivery_details: dict) -> float:
    """Calculate estimated earnings for rider"""
    base_price = delivery_details.get("price", 0)
    # Assume rider gets 70% of delivery price
    return round(base_price * 0.7, 2)


async def notify_nearby_riders(delivery_id: str, pickup_location: dict, vehicle_type: str, background_tasks: BackgroundTasks):
    """
    Notify nearby riders about a new delivery request.
    """
    try:
        # Use the geocoding service to get coordinates
        pickup_lat, pickup_lng = get_coordinates(pickup_location)
        
        if not pickup_lat or not pickup_lng:
            print("Pickup location coordinates not provided and geocoding failed")
            return
        
        # Use dynamic radius calculation
        max_radius = calculate_dynamic_radius({
            "deliveryspeed": "standard",  # Default values
            "price": 0,
            "packagesize": "medium"
        })
        
        nearby_riders = find_nearby_riders(pickup_lat, pickup_lng, vehicle_type, max_distance_km=max_radius)
        
        if not nearby_riders:
            print(f"No nearby {vehicle_type} riders found for this delivery {delivery_id}, please wait for a while.")
            return
        
        print(f"Found {len(nearby_riders)} nearby riders for delivery {delivery_id}")
        
        # send email to each nearby rider
        for rider in nearby_riders:
            if rider.get("email") and rider.get("email_notification", True):
                background_tasks.add_task(
                    email_service.send_email,
                    subject=f"New {vehicle_type.title()} Delivery Available",
                    recipients=[rider["email"]],
                    body=email_service.new_delivery_notification_template(
                        rider["firstname"], 
                        delivery_id, 
                        round(rider["distance_km"], 1),
                        pickup_location.get("address", "Unknown location")
                    )
                )
            
                # Also send push notification if enabled
                if rider.get("push_notification", True):
                    send_push_notification(
                        user_id=rider["_id"],
                        message=f"New {vehicle_type} delivery available {rider['distance_km']:.1f}km away",
                        title="New Delivery Available",
                        data={
                            "type": "new_delivery",
                            "delivery_id": delivery_id,
                            "distance_km": rider["distance_km"]
                        }
                    )
            
        print(f"Notifications sent to {len(nearby_riders)} riders")
    
    except Exception as e:
        print(f"Error notifying nearby riders: {str(e)}")



# ================= Nearby Riders Endpoint =================

@app.get("/debug/geocode")
async def debug_geocode(address: str):
    """Test endpoint for geocoding addresses"""
    try:
        lat, lng = get_coordinates(address)
        if lat and lng:
            return {
                "status": "success",
                "address": address,
                "coordinates": {
                    "latitude": lat,
                    "longitude": lng
                }
            }
        else:
            return {
                "status": "error",
                "message": "Could not geocode the address",
                "address": address
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error during geocoding: {str(e)}",
            "address": address
        }

@app.get("/deliveries/{delivery_id}/nearby-riders")
async def get_nearby_riders_for_delivery(
    delivery_id: str,
    max_distance_km: Optional[float] = None,
    include_rejected: bool = False
):
    """
    Get nearby riders for a specific delivery using dynamic filtering.
    Uses the delivery's pickup location and vehicle type to find suitable riders.
    """
    try:
        # Get the delivery details
        delivery = get_delivery_by_id(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        
        # Extract delivery information needed for matching
        vehicle_type = delivery.get("vehicletype")
        if not vehicle_type:
            raise HTTPException(
                status_code=400, 
                detail="Delivery does not have a vehicle type specified"
            )
        
        # Parse pickup location
        startpoint = delivery.get("startpoint")
        
        # Get coordinates using geocoding service
        pickup_lat, pickup_lng = get_coordinates(startpoint)
        
        if not pickup_lat or not pickup_lng:
            # Check if there's rider_location data available
            if delivery.get("rider_location") and "latitude" in delivery["rider_location"]:
                pickup_lat = delivery["rider_location"]["latitude"]
                pickup_lng = delivery["rider_location"]["longitude"]
                print(f"Using rider location coordinates: {pickup_lat}, {pickup_lng}")
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Could not determine delivery pickup coordinates"
                )
        
        # Create structured startpoint_data with the coordinates we've found
        if isinstance(startpoint, str):
            try:
                startpoint_data = json.loads(startpoint)
                # Update with our coordinates if needed
                if not startpoint_data.get("latitude") or not startpoint_data.get("longitude"):
                    startpoint_data["latitude"] = pickup_lat
                    startpoint_data["longitude"] = pickup_lng
            except json.JSONDecodeError:
                # Create a new object with address and coordinates
                startpoint_data = {
                    "address": startpoint, 
                    "latitude": pickup_lat,
                    "longitude": pickup_lng
                }
        else:
            # If it's already a dict, use it but ensure it has our coordinates
            startpoint_data = startpoint or {}
            if not startpoint_data.get("latitude") or not startpoint_data.get("longitude"):
                startpoint_data["latitude"] = pickup_lat
                startpoint_data["longitude"] = pickup_lng
        
        # Use dynamic radius calculation if max_distance_km is not provided
        if max_distance_km is None:
            # Create delivery details dict for dynamic radius calculation
            delivery_details = {
                "deliveryspeed": delivery.get("deliveryspeed", "standard"),
                "price": delivery.get("price", 0),
                "packagesize": delivery.get("packagesize", "medium")
            }
            max_distance_km = calculate_dynamic_radius(delivery_details)
        
        # Find nearby riders using existing function
        nearby_riders = find_nearby_riders(
            pickup_lat, 
            pickup_lng, 
            vehicle_type, 
            max_distance_km
        )
        
        # Filter out riders who have rejected this delivery (unless explicitly requested)
        if not include_rejected:
            rejected_riders = delivery.get("rejected_riders", [])
            nearby_riders = [
                rider for rider in nearby_riders 
                if rider["_id"] not in rejected_riders
            ]
        
        # Check if delivery is already assigned
        assigned_rider_id = delivery.get("rider_id")
        
        # Add additional information to each rider
        enhanced_riders = []
        for rider in nearby_riders:
            rider_info = {
                **rider,
                "is_assigned_to_delivery": rider["_id"] == assigned_rider_id,
                "has_rejected_delivery": rider["_id"] in delivery.get("rejected_riders", []),
                "estimated_earnings": calculate_estimated_earnings({
                    "price": delivery.get("price", 0)
                }),
                "urgency_level": get_urgency_level({
                    "deliveryspeed": delivery.get("deliveryspeed", "standard"),
                    "price": delivery.get("price", 0)
                })
            }
            
            # Add rating information if available
            rider_ratings = get_rider_ratings(rider["_id"])
            if rider_ratings:
                avg_rating = sum(r.get("rating", 0) for r in rider_ratings) / len(rider_ratings)
                rider_info["average_rating"] = round(avg_rating, 1)
                rider_info["total_ratings"] = len(rider_ratings)
            else:
                rider_info["average_rating"] = 0
                rider_info["total_ratings"] = 0
            
            enhanced_riders.append(rider_info)
        
        # Sort riders by multiple criteria:
        # 1. Assigned rider first (if any)
        # 2. Then by distance
        # 3. Then by rating
        enhanced_riders.sort(key=lambda x: (
            not x["is_assigned_to_delivery"],  # Assigned rider first
            x["distance_km"],  # Then by distance
            -x["average_rating"]  # Then by rating (descending)
        ))
        
        # Prepare delivery summary for context
        delivery_summary = {
            "delivery_id": delivery_id,
            "vehicle_type": vehicle_type,
            "pickup_address": startpoint_data.get("address", "Unknown location"),
            "pickup_coordinates": {
                "latitude": pickup_lat,
                "longitude": pickup_lng
            },
            "delivery_status": delivery.get("status", {}).get("current", "unknown"),
            "price": delivery.get("price", 0),
            "delivery_speed": delivery.get("deliveryspeed", "standard"),
            "package_size": delivery.get("packagesize", "medium"),
            "distance": delivery.get("distance", "unknown"),
            "assigned_rider_id": assigned_rider_id,
            "rejected_riders_count": len(delivery.get("rejected_riders", [])),
            "search_radius_km": round(max_distance_km, 1)
        }
        
        return {
            "status": "success",
            "delivery": delivery_summary,
            "nearby_riders": enhanced_riders,
            "total_found": len(enhanced_riders),
            "search_parameters": {
                "vehicle_type": vehicle_type,
                "max_distance_km": round(max_distance_km, 1),
                "pickup_location": {
                    "latitude": pickup_lat,
                    "longitude": pickup_lng,
                    "address": startpoint_data.get("address")
                },
                "include_rejected_riders": include_rejected,
                "dynamic_radius_used": max_distance_km == calculate_dynamic_radius({
                    "deliveryspeed": delivery.get("deliveryspeed", "standard"),
                    "price": delivery.get("price", 0),
                    "packagesize": delivery.get("packagesize", "medium")
                })
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error getting nearby riders for delivery {delivery_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get nearby riders: {str(e)}"
        )


@app.get("/deliveries/{delivery_id}/top-rider")
async def get_rider_recommendations_for_delivery(
    delivery_id: str,
    limit: int = 5
):
    """
    Get top rider recommendations optimized for new delivery apps.
    Focuses more on availability and distance when rating data is limited.
    """
    try:
        # Get nearby riders using the main endpoint logic
        nearby_riders_response = await get_nearby_riders_for_delivery(
            delivery_id=delivery_id,
            include_rejected=False
        )
        
        if nearby_riders_response["total_found"] == 0:
            return {
                "status": "success",
                "delivery_id": delivery_id,
                "recommendations": [],
                "message": "No suitable riders found for this delivery"
            }
        
        riders = nearby_riders_response["nearby_riders"]
        delivery_info = nearby_riders_response["delivery"]
        
        # Calculate recommendation score for each rider (optimized for new apps)
        scored_riders = []
        for rider in riders:
            score = 0
            score_breakdown = {}
            
            # Distance score (INCREASED WEIGHT - max 40 points for new apps)
            distance_km = rider["distance_km"]
            if distance_km <= 1:
                distance_score = 40
            elif distance_km <= 2:
                distance_score = 35
            elif distance_km <= 3:
                distance_score = 30
            elif distance_km <= 5:
                distance_score = 25
            elif distance_km <= 10:
                distance_score = 20
            else:
                distance_score = 10
            score += distance_score
            score_breakdown["distance"] = distance_score
            
            # Online status and activity score (INCREASED WEIGHT - max 30 points)
            if rider.get("is_online", False):
                online_score = 30
                # Check if rider was recently active
                last_activity = rider.get("last_activity")
                if last_activity:
                    # Bonus for very recent activity (within last hour)
                    time_diff = datetime.utcnow() - last_activity
                    if time_diff.total_seconds() < 3600:  # 1 hour
                        online_score += 5
            else:
                online_score = 0
            score += online_score
            score_breakdown["availability"] = online_score
            
            # Vehicle match score (max 20 points)
            if rider.get("vehicle_type") == delivery_info["vehicle_type"]:
                vehicle_score = 20
            else:
                vehicle_score = 0
            score += vehicle_score
            score_breakdown["vehicle_match"] = vehicle_score
            
            # Modified rating score for new apps (max 15 points)
            avg_rating = rider.get("average_rating", 0)
            total_ratings = rider.get("total_ratings", 0)
            
            if total_ratings >= 3:
                # Use actual rating if rider has 3+ ratings
                rating_score = (avg_rating / 5) * 15
            elif total_ratings > 0:
                # Partial score for 1-2 ratings (be generous)
                rating_score = max(10, (avg_rating / 5) * 15)
            else:
                # Default score for new riders (neutral)
                rating_score = 8
            score += rating_score
            score_breakdown["rating"] = round(rating_score, 1)
            
            # Registration age bonus (NEW - max 10 points)
            # Reward riders who have been registered longer
            date_joined = rider.get("date_joined")
            if date_joined:
                days_registered = (datetime.utcnow() - date_joined).days
                if days_registered >= 30:
                    age_score = 10
                elif days_registered >= 14:
                    age_score = 7
                elif days_registered >= 7:
                    age_score = 5
                elif days_registered >= 3:
                    age_score = 3
                else:
                    age_score = 1
            else:
                age_score = 1
            score += age_score
            score_breakdown["registration_age"] = age_score
            
            # Account completeness bonus (NEW - max 5 points)
            completeness_score = 0
            if rider.get("facial_picture_url"):
                completeness_score += 2
            if rider.get("vehicle_picture_url"):
                completeness_score += 2
            if rider.get("accountnumber") and rider.get("accountbank"):
                completeness_score += 1
            score += completeness_score
            score_breakdown["profile_completeness"] = completeness_score
            
            # Already rejected penalty (keep this)
            if rider.get("has_rejected_delivery", False):
                score -= 15
                score_breakdown["rejection_penalty"] = -15
            
            # Add score information to rider
            rider["recommendation_score"] = round(score, 1)
            rider["score_breakdown"] = score_breakdown
            rider["recommendation_rank"] = None
            
            scored_riders.append(rider)
        
        # Sort by recommendation score (highest first)
        scored_riders.sort(key=lambda x: x["recommendation_score"], reverse=True)
        
        # Add rank and limit results
        top_riders = []
        for i, rider in enumerate(scored_riders[:limit]):
            rider["recommendation_rank"] = i + 1
            top_riders.append(rider)
        
        return {
            "status": "success",
            "delivery_id": delivery_id,
            "delivery_info": delivery_info,
            "recommendations": top_riders,
            "total_candidates": len(scored_riders),
            "showing_top": len(top_riders),
            "scoring_criteria": {
                "distance": "Max 40 points (optimized for new apps)",
                "availability": "Max 30 points (online status + recent activity)",
                "vehicle_match": "Max 20 points (exact match required)",
                "rating": "Max 15 points (generous for new riders)",
                "registration_age": "Max 10 points (days since signup)",
                "profile_completeness": "Max 5 points (photos, bank details)",
                "rejection_penalty": "-15 points if previously rejected"
            },
            "app_optimization": "Scoring optimized for apps with limited delivery history"
        }
        
    except Exception as e:
        print(f"Error getting rider recommendations for delivery {delivery_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get rider recommendations: {str(e)}"
        )


@app.get("/deliveries/{delivery_id}/rider-stats")
async def get_delivery_rider_statistics(delivery_id: str):
    """
    Get statistical information about riders in relation to a specific delivery.
    """
    try:
        # Get nearby riders data
        nearby_riders_response = await get_nearby_riders_for_delivery(
            delivery_id=delivery_id,
            include_rejected=True  # Include all riders for complete stats
        )
        
        if nearby_riders_response["total_found"] == 0:
            return {
                "status": "success",
                "delivery_id": delivery_id,
                "message": "No riders found for statistical analysis",
                "statistics": {}
            }
        
        riders = nearby_riders_response["nearby_riders"]
        delivery_info = nearby_riders_response["delivery"]
        
        # Calculate statistics
        total_riders = len(riders)
        online_riders = len([r for r in riders if r.get("is_online", False)])
        rejected_riders = len([r for r in riders if r.get("has_rejected_delivery", False)])
        available_riders = total_riders - rejected_riders
        
        # Distance statistics
        distances = [r["distance_km"] for r in riders]
        avg_distance = sum(distances) / len(distances) if distances else 0
        min_distance = min(distances) if distances else 0
        max_distance = max(distances) if distances else 0
        
        # Rating statistics
        rated_riders = [r for r in riders if r.get("total_ratings", 0) > 0]
        if rated_riders:
            ratings = [r["average_rating"] for r in rated_riders]
            avg_rating = sum(ratings) / len(ratings)
            min_rating = min(ratings)
            max_rating = max(ratings)
        else:
            avg_rating = min_rating = max_rating = 0
        
        # Distance distribution
        distance_ranges = {
            "0-2km": len([r for r in riders if r["distance_km"] <= 2]),
            "2-5km": len([r for r in riders if 2 < r["distance_km"] <= 5]),
            "5-10km": len([r for r in riders if 5 < r["distance_km"] <= 10]),
            "10km+": len([r for r in riders if r["distance_km"] > 10])
        }
        
        statistics = {
            "total_riders_in_area": total_riders,
            "online_riders": online_riders,
            "offline_riders": total_riders - online_riders,
            "available_riders": available_riders,
            "rejected_riders": rejected_riders,
            "assigned_rider": delivery_info.get("assigned_rider_id") is not None,
            "distance_stats": {
                "average_distance_km": round(avg_distance, 2),
                "min_distance_km": round(min_distance, 2),
                "max_distance_km": round(max_distance, 2),
                "search_radius_km": delivery_info["search_radius_km"]
            },
            "rating_stats": {
                "riders_with_ratings": len(rated_riders),
                "riders_without_ratings": total_riders - len(rated_riders),
                "average_rating": round(avg_rating, 1),
                "min_rating": round(min_rating, 1),
                "max_rating": round(max_rating, 1)
            },
            "distance_distribution": distance_ranges,
            "delivery_details": {
                "vehicle_type": delivery_info["vehicle_type"],
                "delivery_speed": delivery_info["delivery_speed"],
                "price": delivery_info["price"],
                "status": delivery_info["delivery_status"]
            }
        }
        
        return {
            "status": "success",
            "delivery_id": delivery_id,
            "statistics": statistics,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Error getting rider statistics for delivery {delivery_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get rider statistics: {str(e)}"
        )




# ================= Delivery Endpoints =================

# get all online riders
@app.get("/riders/online")
async def get_all_online_riders(
    vehicle_type: Optional[str] = None,
    max_distance_km: Optional[float] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
):
    """
    Endpoint to get all online riders.
    Optionally filter by vehicle type and distance from a given location.
    """
    
    # Base query to get all online and active riders
    query = {
        "is_online": True,
        "status": "active"
    }
    
    # filter by vehicle type if provided
    if vehicle_type:
        query["vehicle_type"] = vehicle_type.lower()
        
    # Get all matching riders
    online_riders = list(riders_collection.find(query))
    
    # Convert ObjectId to string for all riders
    for rider in online_riders:
        rider["_id"] = str(rider["_id"])
    
    # Filter by distance if location parameters are provided
    if max_distance_km and latitude is not None and longitude is not None:
        filtered_riders = []
        for rider in online_riders:
            rider_location = rider.get("current_location", {})
            if rider_location and "latitude" in rider_location and "longitude" in rider_location:
                # Calculate distance using Haversine formula
                distance = calculate_distance(
                    latitude, longitude,
                    rider_location["latitude"], rider_location["longitude"]
                )
                if distance <= max_distance_km:
                    rider["distance_km"] = round(distance, 2)
                    filtered_riders.append(rider)
                    
        filtered_riders.sort(key=lambda x: x["distance_km"])
        online_riders = filtered_riders
    
    return {
        "status": "success",
        "count": len(online_riders),
        "riders": online_riders
    }
     
# WebSocket endpoint 
@app.websocket("/ws/rider/{rider_id}")
async def websocket_endpoint(websocket: WebSocket, rider_id: str):
    await manager.connect(websocket, rider_id)
    try:
        while True:
            # Listen for incoming messages (heartbeat, location updates, etc.)
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "heartbeat":
                await websocket.send_text(json.dumps({
                    "type": "heartbeat_ack", 
                    "timestamp": datetime.utcnow().isoformat()
                }))
            elif message.get("type") == "location_update":
                # Update rider location in real-time
                manager.rider_locations[rider_id] = {
                    "latitude": message.get("latitude"),
                    "longitude": message.get("longitude"),
                    "timestamp": datetime.utcnow()
                }
                
    except WebSocketDisconnect:
        manager.disconnect(rider_id)


@app.get("/riders/{rider_id}")
def fetch_rider_by_id(rider_id: str):
    """
    Endpoint to fetch rider's data by their ID.
    """
    rider = get_rider_by_id(rider_id)

    if rider:
        # Convert ObjectId to string for serialization
        rider["_id"] = str(rider["_id"])
        
        # Add facial picture URL if file_ids exist
        if "file_ids" in rider and rider["file_ids"].get("recent_facial_picture"):
            facial_pic_id = rider["file_ids"]["recent_facial_picture"]
            rider["facial_picture_url"] = f"https://deliveryapi-ten.vercel.app/files/{facial_pic_id}"
        
        return {"status": "success", "rider": rider}
    else:
        raise HTTPException(status_code=404, detail="Rider not found")


@app.get("/riders")
def fetch_all_riders():
    """
    Endpoint to fetch all riders' data.
    """
    riders = get_all_riders()
    return {"status": "success", "riders": riders}

# delete rider by id
@app.delete("/riders/{rider_id}/delete")
async def delete_rider(rider_id: str):
    rider = get_rider_by_id(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    success = delete_rider_by_id(rider_id)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to delete rider {rider_id}")
    
    return {"status": "success", "message": "Rider deleted successfully"}    

# delete selected riders
@app.delete("/riders/delete")
async def delete_multiple_riders(request: DeleteRequest):
    deleted_count = delete_selected_riders(request.ids)
    if deleted_count == 0:
        raise HTTPException(status_code=500, detail="No riders found to delete")
    
    return {"status": "success", "message": f"Deleted {deleted_count} riders successfully"}

# ================= User Endpoints =================

@app.post("/usersignup")
async def user_signup(
    firstname: str = Form(...),
    lastname: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: str = Form(...),
    email_notification: bool = Form(True),
    push_notification: bool = Form(True),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Endpoint to handle user signup.
    """
    # Check if email already exists
    existing_user = get_user_by_phone(phone)
    if existing_user:
        raise HTTPException(
            status_code=400, detail="A user with this phone number already exists."
        )

    # Hash the password using SHA-256
    hashed_password = hash_password_sha256(password)

    # Prepare user data
    user_data = {
        "firstname": firstname,
        "lastname": lastname,
        "email": email,
        "password": hashed_password,  
        "phone": phone,
        "email_notification": email_notification,
        "push_notification": push_notification,
        "date_joined": datetime.now()
    }

    # Insert user into the database
    user_id = insert_user(user_data)
    
    if user_id:
        # Send a welcome email in background
        background_tasks.add_task(
            email_service.send_email,
            subject="Welcome to Delivery App",
            recipients=[email],
            body=email_service.user_signup_template(firstname)
        )

    return {
        "status": "success",
        "message": "User signed up successfully!",
        "user_id": user_id,
    }


@app.post("/usersignin")
async def user_signin(
    phone: str = Form(...), 
    password: str = Form(...),
    fcm_token: Optional[str] = Form(None)
):
    """
    Endpoint to handle user sign-in. Verifies phone and password (SHA-256 hash).
    """
    # Hash the password for comparison
    hashed_password = hash_password_sha256(password)

    # Find the user in the database
    user = get_user_by_phone(phone)

    if user and user["password"] == hashed_password:
        # Convert ObjectId to string for serialization
        user_id = str(user["_id"])
        
        # Update FCM token if provided
        if fcm_token:
            update_user_details_db(user_id, {"fcm_token": fcm_token})
            
        # Return user data
        user["_id"] = user_id
        return {
            "status": "success",
            "message": "User signed in successfully!",
            "user": user,  # Return all user data
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/users/{user_id}")
def fetch_user_by_id(user_id: str):
    """
    Endpoint to fetch user's data by their ID.
    """
    user = get_user_by_id(user_id)

    if user:
        # Convert ObjectId to string for serialization
        user["_id"] = str(user["_id"])
        return {"status": "success", "user": user}
    else:
        raise HTTPException(status_code=404, detail="User not found")


@app.get("/users")
def fetch_all_users():
    """
    Endpoint to fetch all users' data.
    """
    users = get_all_users()
    return {"status": "success", "users": users}


# delete user by id
@app.delete("/users/{user_id}/delete")
async def delete_user(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    success = delete_user_by_id(user_id)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to delete user {user_id}")
    
    return {"status": "success", "message": "User deleted successfully"}    

# delete selected users
@app.delete("/users/delete")
async def delete_multiple_users(request: DeleteRequest):
    deleted_count = delete_selected_users(request.ids)
    if deleted_count == 0:
        raise HTTPException(status_code=500, detail="No users found to delete")
    
    return {"status": "success", "message": f"Deleted {deleted_count} users successfully"}

# ================= Deliveries Endpoints =================


@app.get("/deliveries")
def fetch_all_deliveries():
    """
    Endpoint to fetch all deliveries, sorted by latest first.
    """
    deliveries = get_all_deliveries()

    if not deliveries:
        raise HTTPException(status_code=404, detail="No deliveries found")

    # Sort deliveries by timestamp in descending order (latest first)
    # First try to sort by status.timestamp, then fallback to other timestamp fields
    sorted_deliveries = sorted(
        deliveries,
        key=lambda d: (
            d.get("status", {}).get("timestamp", "")
            or d.get("last_updated", "")
            or d.get("date_created", "")
            or ""
        ),
        reverse=True
    )

    return {"status": "success", "deliveries": sorted_deliveries}


# =================== Deliveries Schedule Functions & Endpoint ==================

async def send_scheduled_delivery_notifications(user_id: str, delivery_id: str, message: str, email_subject: str, email_body: str):
    """Helper function to send notifications for scheduled deliveries"""
    user = get_user_by_id(user_id)
    if not user:
        return
        
    # Send email if enabled
    if user.get("email") and user.get("email_notification", True):
        await email_service.send_email(
            subject=email_subject,
            recipients=[user["email"]],
            body=email_body
        )
    
    # Send push notification if enabled
    if user.get("push_notification", True):
        send_push_notification(
            user_id=user_id,
            message=message,
            title=email_subject,
            data={
                "type": "scheduled_delivery_update",
                "delivery_id": delivery_id
            }
        )

def add_scheduled_delivery_to_queue(delivery_id: str, scheduled_datetime: datetime):
    """
    Add a delivery to the scheduler queue to be processed at the scheduled time.
    """
    scheduler.add_job(
        process_scheduled_delivery,
        trigger=DateTrigger(run_date=scheduled_datetime, timezone=pytz.UTC),
        args=[delivery_id],
        id=f"delivery_{delivery_id}",
        replace_existing=True
    )
    print(f"Scheduled delivery {delivery_id} for {scheduled_datetime}")

def process_scheduled_delivery(delivery_id: str):
    """
    Process a scheduled delivery when its time arrives.
    """
    try:
        # Get delivery details
        delivery = get_delivery_by_id(delivery_id)
        
        if not delivery:
            print(f"Error: Scheduled delivery {delivery_id} not found")
            return
            
        if delivery.get("status", {}).get("current") != "pending":
            print(f"Skipping delivery {delivery_id}: Not in pending status")
            return
            
        # Update delivery status to indicate it's being processed
        update_data = {
            "scheduled_status": "processing",
            "last_updated": datetime.utcnow()
        }
        
        update_delivery(delivery_id, update_data)
        
        # Get user for notifications
        user_id = delivery.get("user_id")
        user = get_user_by_id(user_id) if user_id else None
        
        if user:
            # Send notifications that delivery is now being processed
            background_tasks = BackgroundTasks()
            
            # Format data for notifications
            pickup_address = delivery.get("startpoint", {}).get("address", "Unknown location")
            
            # SEND EMAIL NOTIFICATION
            if user.get("email") and user.get("email_notification", True):
                try:
                    email_body = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                        <h2 style="color: #333;">Your Scheduled Delivery is Now Being Processed</h2>
                        <p style="font-size: 16px; color: #555;">We're now processing your scheduled delivery and finding a rider for you.</p>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <p style="margin: 5px 0;"><strong>Delivery ID:</strong> {delivery_id}</p>
                            <p style="margin: 5px 0;"><strong>Pickup:</strong> {pickup_address}</p>
                        </div>
                        <p style="font-size: 14px; color: #777;">You'll be notified once a rider accepts your delivery.</p>
                        <hr style="margin: 20px 0;">
                        <p style="font-size: 12px; color: #999;">
                            Thank you for using Mico Delivery services.
                        </p>
                        </div>
                    </body>
                    </html>
                    """
                    
                    # Use asyncio to run this synchronously in the background task
                    asyncio.create_task(email_service.send_email(
                        subject="Your Scheduled Delivery is Being Processed",
                        recipients=[user["email"]],
                        body=email_body
                    ))
                except Exception as e:
                    print(f"Error sending processing email notification: {str(e)}")
            
            # SEND PUSH NOTIFICATION
            if user.get("push_notification", True):
                try:
                    send_push_notification(
                        user_id=user_id,
                        message="Your scheduled delivery is now being processed. We're finding a rider for you.",
                        title="Scheduled Delivery Processing",
                        data={
                            "type": "scheduled_delivery_processing",
                            "delivery_id": delivery_id
                        }
                    )
                except Exception as e:
                    print(f"Error sending push notification: {str(e)}")
        
        # Find nearby riders for this delivery
        vehicle_type = delivery.get("vehicletype", "bike")
        pickup_location = delivery.get("startpoint", {})
        
        # Notify nearby riders about the delivery
        background_tasks = BackgroundTasks()
        asyncio.run(
            notify_nearby_riders(
                delivery_id=delivery_id,
                pickup_location=pickup_location,
                vehicle_type=vehicle_type,
                background_tasks=background_tasks
            )
        )
        
        # Mark as processed
        update_data = {
            "scheduled_status": "processed",
            "last_updated": datetime.utcnow()
        }
        update_delivery(delivery_id, update_data)
        
        print(f"Successfully processed scheduled delivery {delivery_id}")
        
    except Exception as e:
        print(f"Error processing scheduled delivery {delivery_id}: {str(e)}")
        # Mark as failed
        try:
            update_data = {
                "scheduled_status": "failed",
                "last_updated": datetime.utcnow()
            }
            update_delivery(delivery_id, update_data)
        except:
            pass

# schedule delivery
@app.post("/delivery/schedule")
async def schedule_delivery(
    request: ScheduledDeliveryRequest, 
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Schedule a delivery for a future date and time.
    The delivery will be processed when the scheduled time arrives.
    """
    try:
        # Extract request data
        delivery_data = request.dict()
        
        # Convert to datetime object
        scheduled_datetime = datetime.combine(
            request.scheduled_date, 
            request.scheduled_time
        )
        
        # Check if the scheduled time is in the future
        if scheduled_datetime <= datetime.utcnow():
            raise HTTPException(
                status_code=400,
                detail="Scheduled time must be in the future"
            )
        
         # Process locations (handle both string and dict formats)
        for location_field in ['startpoint', 'endpoint']:
            if isinstance(delivery_data[location_field], str):
                try:
                    # Try parsing as JSON
                    location_dict = json.loads(delivery_data[location_field])
                    delivery_data[location_field] = location_dict
                except json.JSONDecodeError:
                    # It's a plain text address
                    delivery_data[location_field] = {"address": delivery_data[location_field]}
                    
        if 'status' in delivery_data:
            status_data = delivery_data['status']
            # Convert simpler status structure to full structure if needed
            if not isinstance(status_data, dict) or 'deliverystatus' not in status_data:
                delivery_data['status'] = {
                    "deliverystatus": "pending",
                    "orderstatus": "pending",
                    "riderid": None,
                    "transactioninfo": {
                        "status": "pending",
                        "payment_method": None,
                        "payment_id": None,
                        "payment_date": None
                    }
                }
        
        # Add transaction_info to match regular delivery structure
        delivery_data["transaction_info"] = {
            "payment_status": "pending",
            "payment_date": None,
            "amount_paid": delivery_data["price"],
            "payment_reference": None,
            "last_updated": datetime.utcnow()
        }
        
        # Add scheduled delivery specific fields
        delivery_data.update({
            "scheduled_datetime": scheduled_datetime,
            "scheduled_date_str": request.scheduled_date.isoformat(),  # Store as string
            "scheduled_time_str": request.scheduled_time.isoformat(),  # Store as string
            "scheduled_status": "pending", 
            "created_at": datetime.utcnow(),
            "is_scheduled": True
        })
        
        # Remove date and time objects that MongoDB can't serialize
        if 'scheduled_date' in delivery_data:
            del delivery_data['scheduled_date']
        if 'scheduled_time' in delivery_data:
            del delivery_data['scheduled_time']
        
        # Insert delivery into database
        delivery_id = insert_delivery(delivery_data)
        
        if not delivery_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to create scheduled delivery"
            )
            
        # Add to schedule processor
        add_scheduled_delivery_to_queue(delivery_id, scheduled_datetime)
        
        # Get user for notifications
        user = get_user_by_id(request.user_id)
        if user:
            # Format the delivery time in a user-friendly way
            formatted_time = scheduled_datetime.strftime("%A, %B %d at %I:%M %p")
            
            # SEND EMAIL NOTIFICATION
            if user.get("email") and user.get("email_notification", True):
                background_tasks.add_task(
                    email_service.send_email,
                    subject="Delivery Scheduled Successfully",
                    recipients=[user["email"]],
                    body=f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                        <h2 style="color: #333;">Delivery Scheduled Successfully</h2>
                        <p style="font-size: 16px; color: #555;">Your delivery has been scheduled for <strong>{formatted_time}</strong>.</p>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <p style="margin: 5px 0;"><strong>From:</strong> {delivery_data['startpoint'].get('address')}</p>
                            <p style="margin: 5px 0;"><strong>To:</strong> {delivery_data['endpoint'].get('address')}</p>
                            <p style="margin: 5px 0;"><strong>Scheduled for:</strong> {formatted_time}</p>
                        </div>
                        <p style="font-size: 14px; color: #777;">We'll notify you when your delivery is being processed.</p>
                        <hr style="margin: 20px 0;">
                        <p style="font-size: 12px; color: #999;">
                            Thank you for using Mico Delivery services.
                        </p>
                        </div>
                    </body>
                    </html>
                    """
                )
            
            # SEND PUSH NOTIFICATION
            if user.get("push_notification", True):
                try:
                    send_push_notification(
                        user_id=request.user_id,
                        message=f"Your delivery has been scheduled for {formatted_time}",
                        title="Delivery Scheduled Successfully",
                        data={
                            "type": "scheduled_delivery_created",
                            "delivery_id": delivery_id,
                            "scheduled_time": scheduled_datetime.isoformat()
                        }
                    )
                except Exception as e:
                    print(f"Error sending push notification: {str(e)}")
        
        return {
            "status": "success",
            "message": "Delivery scheduled successfully",
            "delivery_id": delivery_id,
            "scheduled_for": scheduled_datetime.isoformat()
        }        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error scheduling delivery: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule delivery: {str(e)}"
        )

# get scheduled delivery with filters
@app.get("/deliveries/scheduled")
async def get_scheduled_deliveries(
    status: Optional[str] = None,
):
    """
    Get a list of scheduled deliveries. Can filter by status.
    Valid status values: pending, processing, processed, failed, cancelled
    """
    try:
        # Build query
        query = {"is_scheduled": True}
        if status:
            query["scheduled_status"] = status
        
        # Get scheduled deliveries
        scheduled_deliveries = list(delivery_collection.find(query))
        
        # Format response
        for delivery in scheduled_deliveries:
            delivery["_id"] = str(delivery["_id"])
            if "scheduled_datetime" in delivery and isinstance(delivery["scheduled_datetime"], datetime):
                delivery["scheduled_datetime"] = delivery["scheduled_datetime"].isoformat()
        
        return {
            "status": "success",
            "count": len(scheduled_deliveries),
            "scheduled_deliveries": scheduled_deliveries
        }
        
    except Exception as e:
        print(f"Error getting scheduled deliveries: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scheduled deliveries: {str(e)}"
        )

# endpoint to cancel a scheduled delivery
@app.put("/delivery/{delivery_id}/cancel-scheduled")
async def cancel_scheduled_delivery(
    delivery_id: str,
    user_id: str = Form(...),
):
    """
    Cancel a scheduled delivery by moving it to archived_deliveries collection.
    Only the user who created the delivery or an admin can cancel it.
    """
    try:
        # Get the delivery
        delivery = get_delivery_by_id(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        
        # Check if it's actually a scheduled delivery
        if not delivery.get("is_scheduled", False):
            raise HTTPException(status_code=400, detail="This is not a scheduled delivery")
            
        # Check ownership
        if delivery.get("user_id") != user_id:
            # Optional: Add admin check here if needed
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to cancel this delivery"
            )
            
        # Check if it can be cancelled (not already processed)
        if delivery.get("scheduled_status") in ["processed"]:
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel a delivery that has already been processed"
            )
            
        # 1. Remove from scheduler if it's still there
        try:
            scheduler.remove_job(f"delivery_{delivery_id}")
            print(f"Removed delivery {delivery_id} from scheduler")
        except Exception as e:
            # Job might already have been removed or executed
            print(f"Could not remove job from scheduler: {str(e)}")
            
        # 2. Move to archived_deliveries collection
        success = archive_delivery(delivery_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to cancel scheduled delivery"
            )
        
        return {
            "status": "success",
            "message": "Scheduled delivery cancelled successfully and archived",
            "delivery_id": delivery_id
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error cancelling scheduled delivery: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel scheduled delivery: {str(e)}"
        )


# ===================== Offline Deliveries Endpoint ====================

@app.post("/deliveries/offline")
async def create_offline_delivery(
    request: OfflineDeliveryRequest
):
    """
    Endpoint for administrators to record deliveries that occurred offline.
    Creates a record with the same structure as regular deliveries.
    """
    try:
        # Verify user exists
        user = get_user_by_id(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Verify rider exists
        rider = get_rider_by_id(request.rider_id)
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
            
        # Parse completion date
        try:
            completion_datetime = datetime.strptime(request.completion_date, "%Y-%m-%d %H:%M")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD HH:MM")
        
        # Extract request data
        delivery_data = request.dict()
        
        # Process locations (handle both string and dict formats)
        for location_field in ['startpoint', 'endpoint']:
            if isinstance(delivery_data[location_field], str):
                try:
                    # Try parsing as JSON
                    location_dict = json.loads(delivery_data[location_field])
                    delivery_data[location_field] = location_dict
                except json.JSONDecodeError:
                    # It's a plain text address, geocode it
                    lat, lng = get_coordinates(delivery_data[location_field])
                    if lat and lng:
                        delivery_data[location_field] = {
                            "address": delivery_data[location_field],
                            "latitude": lat,
                            "longitude": lng
                        }
                    else:
                        delivery_data[location_field] = delivery_data[location_field]
        
        # Use consistent field names with your regular deliveries
        delivery_data["vehicletype"] = delivery_data.pop("vehicle_type")
        delivery_data["transactiontype"] = delivery_data.pop("transaction_type")
        delivery_data["packagesize"] = delivery_data.pop("package_size")
        delivery_data["deliveryspeed"] = delivery_data.pop("delivery_speed")
        
        # Build complete delivery record structure matching your regular deliveries
        delivery_data.update({
            "status": {
                "current": "completed",
                "timestamp": completion_datetime
            },
            "transaction_info": {
                "payment_status": request.payment_status,
                "payment_date": completion_datetime if request.payment_status == "paid" else None,
                "amount_paid": request.price if request.payment_status == "paid" else 0,
                "payment_reference": request.payment_reference,
                "last_updated": datetime.utcnow()
            },
            "created_at": completion_datetime,
            "last_updated": datetime.utcnow(),
            "is_offline_record": True  # Additional flag to identify offline records
        })
        
        # Use MongoDB's automatic ObjectId generation exactly like regular deliveries
        delivery_id = insert_delivery(delivery_data)
        
        if not delivery_id:
            raise HTTPException(status_code=500, detail="Failed to create offline delivery record")
            
        return {
            "status": "success",
            "message": "Offline delivery recorded successfully",
            "delivery_id": delivery_id
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error creating offline delivery: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to create offline delivery: {str(e)}"
        )

@app.get("/deliveries/offline")
async def get_offline_deliveries(
    user_id: Optional[str] = None,
    rider_id: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    payment_status: Optional[str] = None
):
    """
    Retrieve all offline delivery records with optional filters.
    """
    try:
        # Build base query for offline deliveries
        query = {"is_offline_record": True}
        
        # Add optional filters if provided
        if user_id:
            query["user_id"] = user_id
        
        if rider_id:
            query["rider_id"] = rider_id
            
        if payment_status:
            query["transaction_info.payment_status"] = payment_status
            
        # Date range filtering
        date_filter = {}
        if from_date:
            try:
                from_datetime = datetime.strptime(from_date, "%Y-%m-%d")
                date_filter["$gte"] = from_datetime
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
                
        if to_date:
            try:
                # Set time to end of day for inclusive filtering
                to_datetime = datetime.strptime(to_date, "%Y-%m-%d")
                to_datetime = to_datetime.replace(hour=23, minute=59, second=59)
                date_filter["$lte"] = to_datetime
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
                
        if date_filter:
            query["completion_date"] = date_filter
        
        # Get offline deliveries
        offline_deliveries = list(delivery_collection.find(query))
        
        if not offline_deliveries:
            return {
                "status": "success",
                "message": "No offline deliveries found",
                "deliveries": []
            }
            
        # Format for response
        for delivery in offline_deliveries:
            delivery["_id"] = str(delivery["_id"])
            
            # Format datetime objects
            for key, value in delivery.items():
                if isinstance(value, datetime):
                    delivery[key] = value.isoformat()
                
            # Format nested datetime objects
            if "status" in delivery and "timestamp" in delivery["status"]:
                if isinstance(delivery["status"]["timestamp"], datetime):
                    delivery["status"]["timestamp"] = delivery["status"]["timestamp"].isoformat()
                    
            if "transaction_info" in delivery:
                if "payment_date" in delivery["transaction_info"] and isinstance(delivery["transaction_info"]["payment_date"], datetime):
                    delivery["transaction_info"]["payment_date"] = delivery["transaction_info"]["payment_date"].isoformat()
                if "last_updated" in delivery["transaction_info"] and isinstance(delivery["transaction_info"]["last_updated"], datetime):
                    delivery["transaction_info"]["last_updated"] = delivery["transaction_info"]["last_updated"].isoformat()
                    
        # Sort deliveries by timestamp in descending order (latest first)
        sorted_deliveries = sorted(
            offline_deliveries,
            key=lambda d: (
                d.get("completion_date", "")
                or d.get("status", {}).get("timestamp", "")
                or d.get("last_updated", "")
                or d.get("created_at", "")
                or ""
            ),
            reverse=True
        )
        
        return {
            "status": "success",
            "count": len(sorted_deliveries),
            "deliveries": sorted_deliveries
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error fetching offline deliveries: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve offline deliveries: {str(e)}"
        )

# ====================== Deliveries Archive Endpoints ======================

#  endpoint to view archived deliveries
@app.get("/deliveries/archived")
async def get_archived_deliveries_endpoint(
    admin_key: str = Security(api_key_query)
):
    """
    Get all archived deliveries
    """
    try:
        # Verify admin key
        if not admin_key or hashlib.sha256(admin_key.encode()).hexdigest() != hashlib.sha256(ADMIN_DELETE_KEY.encode()).hexdigest():
            raise HTTPException(status_code=403, detail="Invalid admin key")

        # Get all documents from archived collection
        cursor = archived_deliveries_collection.find()
        archived_list = []

        # Process each document
        for delivery in cursor:
            try:
                # Convert ObjectId to string
                delivery["_id"] = str(delivery["_id"])
                
                # Convert any other ObjectIds
                if "user_id" in delivery:
                    delivery["user_id"] = str(delivery["user_id"])
                if "rider_id" in delivery:
                    delivery["rider_id"] = str(delivery["rider_id"])
                if "archived_from_id" in delivery:
                    delivery["archived_from_id"] = str(delivery["archived_from_id"])
                
                # Convert datetime objects to ISO format
                for key, value in delivery.items():
                    if isinstance(value, datetime):
                        delivery[key] = value.isoformat()
                
                archived_list.append(delivery)
            except Exception as e:
                print(f"Error processing document: {str(e)}")
                continue

        return {
            "status": "success",
            "archived_deliveries": archived_list,
            "count": len(archived_list)
        }

    except Exception as e:
        print(f"Error in get_archived_deliveries_endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving archived deliveries: {str(e)}"
        )
 
# get deliveries 
@app.get("/deliveries/{delivery_id}")
def fetch_delivery_by_id(delivery_id: str):
    """
    Endpoint to fetch a delivery by its ID.
    """
    delivery = get_delivery_by_id(delivery_id)

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    return {"status": "success", "delivery": delivery}

# ------------------------- DELIVERIES ACHIVES -----------------------

# delete delivery by id
@app.delete("/deliveries/{delivery_id}/delete")
async def archive_delivery_endpoint(delivery_id: str):
    """
    Move a delivery to archieve instead of deleting
    """
    delivery = get_delivery_by_id(delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    success = archive_delivery(delivery_id)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to delete delivery {delivery_id}")
    
    return {"status": "success", "message": "Delivery deleted successfully"}    

# delete all deliveries
@app.delete("/deliveries/delete")
async def achive_all_deliveries(admin_key: str = Security(api_key_query)):
    """
    Achive all deliveries instead of deleting them all
    """
    
    # Verify admin key
    if not admin_key or hashlib.sha256(admin_key.encode()).hexdigest() != hashlib.sha256(ADMIN_DELETE_KEY.encode()).hexdigest():
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    
    # Get all active deliveries
    deliveries = delivery_collection.find({})
    archived_count = 0
    
    ## Archive each delivery
    for delivery in deliveries:
        delivery_id = str(delivery["_id"])
        if archive_delivery(delivery_id):
            archived_count += 1
    
    if archived_count == 0:
        raise HTTPException(status_code=404, detail="No deliveries found to archive")
    
    return {
        "status": "success", 
        "message": f"All deliveries archived successfully. Total: {archived_count}"
    }

#  endpoint for permanent deletion
@app.delete("/deliveries/{delivery_id}/permanent")
async def permanent_delete_delivery(
    delivery_id: str,
    admin_key: str = Security(api_key_query),
    from_archive: bool = True
):
    """
    Permanently delete a delivery with admin key verification
    """
    # Verify admin key
    if not admin_key or hashlib.sha256(admin_key.encode()).hexdigest() != hashlib.sha256(ADMIN_DELETE_KEY.encode()).hexdigest():
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    success = permanently_delete_delivery(delivery_id, archive=from_archive)
    if not success:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    return {"status": "success", "message": "Delivery permanently deleted"}

#  endpoint to restore archived delivery
@app.post("/deliveries/{delivery_id}/restore")
async def restore_delivery_endpoint(
    delivery_id: str,
    admin_key: str = Security(api_key_query)
):
    """
    Restore a delivery from archive
    """
    # Verify admin key
    if not admin_key or hashlib.sha256(admin_key.encode()).hexdigest() != hashlib.sha256(ADMIN_DELETE_KEY.encode()).hexdigest():
        raise HTTPException(status_code=403, detail="Invalid admin key")
        
    success = restore_delivery(delivery_id)
    if not success:
        raise HTTPException(status_code=404, detail="Archived delivery not found")
    
    return {"status": "success", "message": "Delivery restored successfully"}

# endpoint to delete all achieved deliveries
@app.delete("/deliveries/permanent-delete-all")
async def permanent_delete_all_deliveries(
    admin_key: str = Security(api_key_query),
    from_archive: bool = True
):
    """
    Permanently delete all deliveries with admin key verification
    """
    # Verify admin key
    if not admin_key or hashlib.sha256(admin_key.encode()).hexdigest() != hashlib.sha256(ADMIN_DELETE_KEY.encode()).hexdigest():
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    collection = archived_deliveries_collection if from_archive else delivery_collection
    result = collection.delete_many({})
    deleted_count = result.deleted_count
    
    if deleted_count == 0:
        raise HTTPException(
            status_code=404, 
            detail=f"No {'archived ' if from_archive else ''}deliveries found to delete"
        )
    
    return {
        "status": "success", 
        "message": f"All {'archived ' if from_archive else ''}deliveries permanently deleted. Total: {deleted_count}"
    }
   
    

# validate deliveries
def validate_delivery_status(delivery: dict, action: str):
    """"
    Validate id the delivery status allows the requested access
    """
    
    current_status = delivery.get("status", {}).get("current", "")
    
    # Status transition validations
    valid_transitions = {
        "pending": ["accept", "reject"],
        "ongoing": ["cancel", "complete", "inprogress"],
        "inprogress": ["complete", "cancel"],
        "completed": [],  # Completed deliveries cannot be modified
        "cancelled": [],  # Cancelled deliveries cannot be modified
        "rejected": ["accept", "undo_reject"]
    }
    
    if current_status not in valid_transitions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid delivery status: {current_status}"
        )
        
    if action not in valid_transitions[current_status]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot {action} a delivery in '{current_status}' status. Valid actions are: {', '.join(valid_transitions[current_status])}"
        )

# update deliveries
@app.put("/delivery/{delivery_id}/update")
async def update_delivery_status(
    delivery_id: str,
    rider_id: str = Form(...),
    action: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Endpoint to update delivery status and manage rider interactions.
    """
    try:
        # Verify delivery exists
        delivery = get_delivery_by_id(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        
        # Verify rider exists
        rider = get_rider_by_id(rider_id)
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        # validate status transition
        # validate_delivery_status(delivery, action)
        
        # Initialize update data
        update_data = {}
        
        if action == "accept":
            # Check if delivery is already accepted
            if "rider_id" in delivery and delivery["rider_id"]:
                raise HTTPException(
                    status_code=400,
                    detail="This delivery has already been accepted by another rider"
                )
            
            # Check if rider previously rejected this delivery
            rejected_riders = delivery.get("rejected_riders", [])
            if rider_id in rejected_riders:
                # Remove from rejected list first
                rejected_riders.remove(rider_id)
                update_data["rejected_riders"] = rejected_riders
            
            # Update delivery with rider info and status
            update_data.update({
                "rider_id": rider_id,
                "status": {
                    "current": "ongoing",
                    "timestamp": datetime.utcnow()
                }
            })
            
        elif action == "reject":
            # Cannot reject if already accepted by this rider
            if delivery.get("rider_id") == rider_id:
                raise HTTPException(
                    status_code=400,
                    detail="You have already accepted this delivery. Use cancel instead."
                )
                
            rejected_riders = delivery.get("rejected_riders", [])
            if rider_id not in rejected_riders:
                rejected_riders.append(rider_id)
                update_data["rejected_riders"] = rejected_riders
                
        elif action == "undo_reject":
            rejected_riders = delivery.get("rejected_riders", [])
            if rider_id in rejected_riders:
                rejected_riders.remove(rider_id)
                update_data["rejected_riders"] = rejected_riders
                
        elif action == "cancel":
            # Only the assigned rider can cancel
            if delivery.get("rider_id") != rider_id:
                raise HTTPException(
                    status_code=400,
                    detail="Only the assigned rider can cancel this delivery"
                )
                
            # Reset the delivery status
            update_data = {
                "rider_id": None,
                "status": {
                    "current": "cancelled",
                    "timestamp": datetime.utcnow()
                }
            }
        elif action == "complete":
            # Only the assigned rider can complete the delivery
            if delivery.get("rider_id") != rider_id:
                raise HTTPException(
                    status_code=403,
                    detail="Only the assigned rider can complete this delivery"
                )
            
            # Check if delivery is in the correct state to be completed
            current_status = delivery.get("status", {}).get("current")
            if current_status not in ["ongoing", "inprogress"]:
                raise HTTPException(
                    status_code=400,
                    detail="Only ongoing or in-progress deliveries can be completed"
                )
            
            # Get current transaction info to preserve it
            transaction_info = delivery.get("transaction_info", {})
            
            # Ensure payment status stays as "pending" regardless of delivery completion
            if transaction_info.get("payment_status") != "pending":
                transaction_info["payment_status"] = "pending"
                transaction_info["last_updated"] = datetime.utcnow()
            
            # Update the delivery status to completed and ensure transaction remains pending
            update_data = {
                "status": {
                    "current": "completed",
                    "timestamp": datetime.utcnow()
                },
                "transaction_info": transaction_info  # Explicitly include transaction_info
            }
            
        elif action == "inprogress":
            # Only the assigned rider can mark as in progress
            if delivery.get("rider_id") != rider_id:
                raise HTTPException(
                    status_code=403,
                    detail="Only the assigned rider can mark this delivery as in progress"
                )
            
            # Check if delivery is in the correct state to be marked as in progress
            if delivery.get("status", {}).get("current") != "ongoing":
                raise HTTPException(
                    status_code=400,
                    detail="Only ongoing deliveries can be marked as in progress"
                )
            
            # Update the delivery status to in progress
            update_data = {
                "status": {
                    "current": "inprogress",
                    "timestamp": datetime.utcnow()
                }
            }
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No updates required")
        
        # Update the delivery in database
        success = update_delivery(delivery_id, update_data)
        
        # EMAIL NOTIFICATION
        if success and action != 'reject':
            # Get user and rider for notifications
            delivery = get_delivery_by_id(delivery_id)
            user = get_user_by_id(delivery.get("user_id"))
            rider = get_rider_by_id(rider_id)
            
            # Send notification emails
            if user and user.get("email") and user.get("email_notification", True):
                background_tasks.add_task(
                    email_service.send_email,
                    subject=f"Delivery Update: {action}",
                    recipients=[user["email"]],
                    body=email_service.delivery_template(action, delivery_id)
                )
            
            if rider and rider.get("email") and rider.get("email_notification", True):
                background_tasks.add_task(
                    email_service.send_email,
                    subject=f"Delivery Update: {action}",
                    recipients=[rider["email"]],
                    body=email_service.delivery_template(action, delivery_id)
                )
                
            # PUSH NOTIFICATION
            try:
                # check if user has push notifications enabled
                if user and user.get("push_notification", True):
                    send_push_notification(
                        user_id=delivery.get("user_id"),
                        message=f"Your delivery status has been updated to {action}",
                        title="Delivery Status Update",
                        data={
                            "type": "delivery_update",
                            "delivery_id": delivery_id,
                            "status": action
                        }
                    )
                    
                # check if rider has push notifications enabled
                if rider and rider.get("push_notification", True):
                    send_push_notification(
                        user_id=rider_id,
                        message=f"Your delivery status has been updated to {action}",
                        title="Delivery Status Update",
                        data={
                            "type": "delivery_update",
                            "delivery_id": delivery_id,
                            "status": action 
                        }
                    )
            except Exception as e:
                print(f"Error sending push notification: {str(e)}")
                
                
        # Check if the update was successful but log errors without disrupting flow
        if not success:
            print(f"Warning: Failed to update delivery {delivery_id} with {action} action.")
            print(f"Update data: {update_data}")
                
            
        if not success:
            print(f"Failed to update delivery {delivery_id} with data: {update_data}")
            raise HTTPException(
                status_code=500,
                detail="Failed to update delivery status in database"
            )
        
        return {
            "status": "success",
            "message": f"Delivery {action} successful",
            "delivery_id": delivery_id,
            "updated_data": update_data
        }
    except Exception as e:
        print(f"Error in update_delivery_status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update delivery status: {str(e)}"
        )

@app.get("/delivery/{delivery_id}/status")
async def get_delivery_status(
    delivery_id: str,
):
    """
    Endpoint to get delivery status and manage rider interactions.
    """
    try:
        # Verify delivery exists
        delivery = get_delivery_by_id(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        
        # Get delivery status from database
        current_status = delivery.get("status", {}).get("current", "pending"),
        timestamp =  delivery.get("status", {}).get("timestamp"),
        rider_id = delivery.get("rider_id"),
        rider_location = delivery.get("rider_location")
        
        return {
            "status": {
                "current": current_status,
                "timestamp": timestamp
            },
            "rider_id": rider_id,
            "rider_location": rider_location,
            "delivery_id": delivery_id,
            "message": "Delivery status retrieved successfully",
        }
    except Exception as e:
        print(f"Error in get_delivery_status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get delivery status: {str(e)}"
        )
 
@app.put("/delivery/{delivery_id}/transaction")
async def update_delivery_transaction(
    delivery_id: str,
    transaction_data: TransactionUpdateRequest
):
    """
    Endpoint to update transaction information for a delivery.
    """
    try:
        # Verify delivery exists
        delivery = get_delivery_by_id(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        
        # Prepare update data
        update_data = {}
        
        # Only include fields that are provided
        if transaction_data.transaction_type is not None:
            if transaction_data.transaction_type.lower() not in ["cash", "online"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid transaction type. Choose 'cash' or 'online'."
                )
            update_data["transactiontype"] = transaction_data.transaction_type.lower()
        
        # Create or update transaction info
        transaction_info = delivery.get("transaction_info", {})
        
        if transaction_data.payment_status is not None:
            if transaction_data.payment_status.lower() not in ["pending", "paid", "failed"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid payment status. Choose 'pending', 'paid', or 'failed'."
                )
            transaction_info["payment_status"] = transaction_data.payment_status.lower()
        
        if transaction_data.payment_reference is not None:
            transaction_info["payment_reference"] = transaction_data.payment_reference
        
        if transaction_data.payment_date is not None:
            transaction_info["payment_date"] = transaction_data.payment_date
        
        if transaction_data.amount_paid is not None:
            transaction_info["amount_paid"] = transaction_data.amount_paid
        
        # Add last updated timestamp
        transaction_info["last_updated"] = datetime.utcnow()
        
        # Add transaction info to update data
        if transaction_info:
            update_data["transaction_info"] = transaction_info
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No transaction data provided for update")
        
        # Update the delivery in database
        success = update_delivery(delivery_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update transaction information"
            )
        
        return {
            "status": "success",
            "message": "Transaction information updated successfully",
            "delivery_id": delivery_id,
            "updated_data": update_data
        }
    
    except Exception as e:
        print(f"Error updating transaction information: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update transaction information: {str(e)}"
        )

@app.get("/riders/{rider_id}/available-deliveries")
async def get_available_deliveries_for_rider(
    rider_id: str,
    max_distance_km: float = 10.0
):
    """Get available deliveries near a rider's current location"""
    try:
        rider = get_rider_by_id(rider_id)
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        rider_location = rider.get("current_location")
        if not rider_location:
            return {
                "status": "success",
                "available_deliveries": [],
                "message": "No location available for rider"
            }
        
        # Find pending deliveries near rider
        pending_deliveries = list(delivery_collection.find({
            "status.current": "pending",
            "vehicletype": rider.get("vehicle_type"),
            "rider_id": None
        }))
        
        nearby_deliveries = []
        for delivery in pending_deliveries:
            pickup_location = delivery.get("startpoint", {})
            if pickup_location.get("latitude") and pickup_location.get("longitude"):
                distance = calculate_distance(
                    rider_location["latitude"], rider_location["longitude"],
                    pickup_location["latitude"], pickup_location["longitude"]
                )
                
                if distance <= max_distance_km:
                    delivery["_id"] = str(delivery["_id"])
                    delivery["distance_km"] = round(distance, 2)
                    nearby_deliveries.append(delivery)
        
        # Sort by distance
        nearby_deliveries.sort(key=lambda x: x["distance_km"])
        
        return {
            "status": "success",
            "available_deliveries": nearby_deliveries[:10],  # Limit to 10 nearest
            "count": len(nearby_deliveries)
        }
        
    except Exception as e:
        print(f"Error getting available deliveries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/riders/{rider_id}/activate")
async def activate_rider(rider_id: str):
    """
    Endpoint to activate a rider by changing their status from 'inactive' to 'active'.
    """
    # Get the rider first
    rider = get_rider_by_id(rider_id)
    
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    if rider["status"] == "active":
        raise HTTPException(status_code=400, detail="Rider is already active")
    
    # Update rider status to active
    success = update_rider_status(rider_id, "active")
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update rider status")
    
    return {
        "status": "success",
        "message": "Rider activated successfully",
        "rider_id": rider_id
    }

@app.put("/riders/{rider_id}/deactivate")
async def activate_rider(rider_id: str):
    """
    Endpoint to deactivate a rider by changing their status from 'inactive' to 'active'.
    """
    # Get the rider first
    rider = get_rider_by_id(rider_id)
    
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    if rider["status"] == "inactive":
        raise HTTPException(status_code=400, detail="Rider is already inactive")
    
    # Update rider status to inactive
    success = update_rider_status(rider_id, "inactive")
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update rider status")
    
    return {
        "status": "success",
        "message": "Rider deactivated successfully",
        "rider_id": rider_id
    }

@app.put("/riders/{rider_id}/location")
async def update_rider_location(
    rider_id: str,
    latitude: float = Form(...),
    longitude: float = Form(...),
    eta_minutes: Optional[int] = Form(None)
):
    """
    Update rider's current location with ETA and check for nearby deliveries.
    Combines functionality of both location update endpoints.
    """
    try:
        # Verify rider exists
        rider = get_rider_by_id(rider_id)
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        # Prepare standard location data for riders_collection
        current_location = {
            "latitude": latitude,
            "longitude": longitude,
            "last_updated": datetime.utcnow()
        }
        
        # Add ETA if provided
        if eta_minutes is not None:
            current_location["eta_minutes"] = eta_minutes
            current_location["eta_time"] = datetime.utcnow() + timedelta(minutes=eta_minutes)
        
        # Use the centralized update_rider_location_db function to update both collections
        success = update_rider_location_db(rider_id, latitude, longitude, eta_minutes)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update location")
        
        # LEGACY SUPPORT: Also update rider_location field for backwards compatibility
        # This can be removed once all clients are updated to use current_location
        rider_location_data = {
            "rider_location": {
                "rider_id": rider_id,
                "latitude": latitude,
                "longitude": longitude,
                "last_updated": datetime.utcnow()
            }
        }
        
        if eta_minutes is not None:
            rider_location_data["rider_location"]["eta_minutes"] = eta_minutes
            rider_location_data["rider_location"]["eta_time"] = datetime.utcnow() + timedelta(minutes=eta_minutes)
        
        # Check for nearby pending deliveries
        available_deliveries = []
        pending_deliveries = list(delivery_collection.find({
            "status.current": "pending",
            "vehicletype": rider.get("vehicle_type"),
            "rider_id": None
        }))
        
        for delivery in pending_deliveries:
            pickup_location = delivery.get("startpoint", {})
            if pickup_location.get("latitude") and pickup_location.get("longitude"):
                distance = calculate_distance(
                    latitude, longitude,
                    pickup_location["latitude"], pickup_location["longitude"]
                )
                
                if distance <= 5.0:  # Within 5km
                    delivery["_id"] = str(delivery["_id"])
                    delivery["distance_km"] = round(distance, 2)
                    available_deliveries.append(delivery)
        
        # Sort by distance
        available_deliveries.sort(key=lambda x: x["distance_km"])
        
        return {
            "status": "success",
            "message": "Rider location updated successfully",
            "rider_id": rider_id,
            "location": current_location,
            "eta_minutes": eta_minutes,
            "eta_time": current_location.get("eta_time"),
            "nearby_deliveries": len(available_deliveries),
            "available_deliveries": available_deliveries[:3]  # Show top 3
        }
        
    except Exception as e:
        print(f"Error updating rider location: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update location: {str(e)}")

@app.get("/riders/{rider_id}/location")
async def get_rider_location(rider_id: str):
    """
    Get a rider's current location information.
    Returns location coordinates, timestamp and ETA if available.
    """
    try:
        # Verify rider exists
        rider = get_rider_by_id(rider_id)
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        # Get rider's current location
        location_data = rider.get("current_location")
        if not location_data:
            raise HTTPException(
                status_code=404,
                detail="No location data available for this rider"
            )
            
        # Check if rider is currently assigned to an active delivery
        active_delivery = None
        active_deliveries = list(delivery_collection.find({
            "rider_id": rider_id,
            "status.current": {"$in": ["ongoing", "inprogress"]}
        }))
        if active_deliveries:
            active_delivery = {
                "delivery_id": str(active_deliveries[0]["_id"]),
                "status": active_deliveries[0].get("status", {}).get("current"),
                "pickup": active_deliveries[0].get("startpoint", {}).get("address", "Unknown"),
                "destination": active_deliveries[0].get("endpoint", {}).get("address", "Unknown"),
            }
            
            
        return {
            "status": "success",
            "is_online": rider.get("is_online", False),
            "location": {
                "latitude": location_data.get("latitude"),
                "longitude": location_data.get("longitude"),
                "last_updated": location_data.get("last_updated"),
                "eta_minutes": location_data.get("eta_minutes"),
                "eta_time": location_data.get("eta_time")
            },
            "active_delivery": active_delivery
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error getting rider location: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get rider location: {str(e)}"
        )

@app.put("/riders/{rider_id}/update")
async def update_rider_details(
    rider_id: str,
    *,  # Force keyword arguments for all following parameters
    firstname: Optional[str] = None,
    lastname: Optional[str] = None,
    phone: Optional[str] = None,
    emergency_contact_name: Optional[str] = None,
    emergency_contact_phone: Optional[str] = None,
    accountbank: Optional[str] = None,
    accountname: Optional[str] = None,
    accountnumber: Optional[str] = None,
    homeaddressdetails: Optional[str] = None,
    email_notification: Optional[bool] = None,
    push_notification: Optional[bool] = None,
):
    """
    Endpoint to update rider's details.
    """
    # Get the rider first
    rider = get_rider_by_id(rider_id)
    
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    # Prepare update data (only include fields that are provided)
    update_data = {}
    if firstname: update_data["firstname"] = firstname
    if lastname: update_data["lastname"] = lastname
    if phone: update_data["phone"] = phone
    if emergency_contact_name: update_data["emergency_contact_name"] = emergency_contact_name
    if emergency_contact_phone: update_data["emergency_contact_phone"] = emergency_contact_phone
    if accountbank: update_data["accountbank"] = accountbank
    if accountname: update_data["accountname"] = accountname
    if accountnumber: update_data["accountnumber"] = accountnumber
    if homeaddressdetails: update_data["homeaddressdetails"] = homeaddressdetails
    if email_notification is not None: update_data["email_notification"] = email_notification
    if push_notification is not None: update_data["push_notification"] = push_notification
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    # Update rider details
    success = update_rider_details_db(rider_id, update_data)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update rider details")
    
    return {
        "status": "success",
        "message": "Rider details updated successfully",
        "rider_id": rider_id
    }

@app.put("/riders/{rider_id}/update-nationalid")
async def update_rider_nationalid(
    rider_id: str,
    nationalid: UploadFile = File(...),
):
    """
    Endpoint to update rider's national ID document.
    """
    try:
        rider = get_rider_by_id(rider_id)
        
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        update_data = {}
        file_updates = {}
        
        nationalid_file = await nationalid.read()
        if nationalid_file:
            from database import save_file_to_gridfs
            file_id = save_file_to_gridfs(nationalid_file, nationalid.filename)
            if file_id:
                file_updates["nationalid"] = file_id
        
        if file_updates:
            existing_file_ids = rider.get("file_ids", {})
            existing_file_ids.update(file_updates)
            update_data["file_ids"] = existing_file_ids
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid file provided")
        
        success = update_rider_details_db(rider_id, update_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update national ID")
        
        return {
            "status": "success",
            "message": "National ID updated successfully",
            "rider_id": rider_id
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"Error updating national ID: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update national ID: {str(e)}")

@app.put("/riders/{rider_id}/update-facial-picture")
async def update_rider_facial_picture(
    rider_id: str,
    facial_picture: UploadFile = File(...),
):
    """
    Endpoint to update rider's facial picture.
    """
    try:
        rider = get_rider_by_id(rider_id)
        
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        update_data = {}
        file_updates = {}
        
        facial_picture_file = await facial_picture.read()
        if facial_picture_file:
            from database import save_file_to_gridfs
            file_id = save_file_to_gridfs(facial_picture_file, facial_picture.filename)
            if file_id:
                file_updates["facial_picture"] = file_id
                facial_picture_url = f"https://deliveryapi-ten.vercel.app/files/{file_id}"
                update_data["facial_picture_url"] = facial_picture_url
        
        if file_updates:
            existing_file_ids = rider.get("file_ids", {})
            existing_file_ids.update(file_updates)
            update_data["file_ids"] = existing_file_ids
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid file provided")
        
        success = update_rider_details_db(rider_id, update_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update facial picture")
        
        return {
            "status": "success",
            "message": "Facial picture updated successfully",
            "rider_id": rider_id,
            "facial_picture_url": update_data.get("facial_picture_url")
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"Error updating facial picture: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update facial picture: {str(e)}")

@app.put("/riders/{rider_id}/update-utility-bill")
async def update_rider_utility_bill(
    rider_id: str,
    utility_bill: UploadFile = File(...),
):
    """
    Endpoint to update rider's utility bill.
    """
    try:
        rider = get_rider_by_id(rider_id)
        
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        update_data = {}
        file_updates = {}
        
        utility_bill_file = await utility_bill.read()
        if utility_bill_file:
            from database import save_file_to_gridfs
            file_id = save_file_to_gridfs(utility_bill_file, utility_bill.filename)
            if file_id:
                file_updates["utility_bill"] = file_id
        
        if file_updates:
            existing_file_ids = rider.get("file_ids", {})
            existing_file_ids.update(file_updates)
            update_data["file_ids"] = existing_file_ids
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid file provided")
        
        success = update_rider_details_db(rider_id, update_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update utility bill")
        
        return {
            "status": "success",
            "message": "Utility bill updated successfully",
            "rider_id": rider_id
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"Error updating utility bill: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update utility bill: {str(e)}")

@app.put("/riders/{rider_id}/update-registration-papers")
async def update_rider_registration_papers(
    rider_id: str,
    registration_papers: UploadFile = File(...),
):
    """
    Endpoint to update rider's vehicle registration papers.
    """
    try:
        rider = get_rider_by_id(rider_id)
        
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        update_data = {}
        file_updates = {}
        
        registration_papers_file = await registration_papers.read()
        if registration_papers_file:
            from database import save_file_to_gridfs
            file_id = save_file_to_gridfs(registration_papers_file, registration_papers.filename)
            if file_id:
                file_updates["registration_papers"] = file_id
        
        if file_updates:
            existing_file_ids = rider.get("file_ids", {})
            existing_file_ids.update(file_updates)
            update_data["file_ids"] = existing_file_ids
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid file provided")
        
        success = update_rider_details_db(rider_id, update_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update registration papers")
        
        return {
            "status": "success",
            "message": "Registration papers updated successfully",
            "rider_id": rider_id
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"Error updating registration papers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update registration papers: {str(e)}")

@app.put("/riders/{rider_id}/update-license")
async def update_rider_license(
    rider_id: str,
    license: UploadFile = File(...),
):
    """
    Endpoint to update rider's driver's license.
    """
    try:
        rider = get_rider_by_id(rider_id)
        
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        update_data = {}
        file_updates = {}
        
        license_file = await license.read()
        if license_file:
            from database import save_file_to_gridfs
            file_id = save_file_to_gridfs(license_file, license.filename)
            if file_id:
                file_updates["license"] = file_id
        
        if file_updates:
            existing_file_ids = rider.get("file_ids", {})
            existing_file_ids.update(file_updates)
            update_data["file_ids"] = existing_file_ids
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid file provided")
        
        success = update_rider_details_db(rider_id, update_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update license")
        
        return {
            "status": "success",
            "message": "License updated successfully",
            "rider_id": rider_id
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"Error updating license: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update license: {str(e)}")


@app.put("/riders/{rider_id}/vehicle-picture")
async def update_the_rider_vehicle_picture(
    rider_id: str,
    vehicle_picture: UploadFile = File(...)
):
    """
    Endpoint to update or add a rider's vehicle picture.
    """
    # Verify rider exists
    rider = get_rider_by_id(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    try:
        # Read the uploaded file
        vehicle_picture_data = await vehicle_picture.read()
        
        # Save the vehicle picture to GridFS and get the file ID
        from database import save_file_to_gridfs
        file_id = save_file_to_gridfs(vehicle_picture_data, vehicle_picture.filename)
        
        if not file_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to save vehicle picture"
            )
        
        # Update the rider's profile with the picture URL and file ID
        vehicle_picture_url = f"https://deliveryapi-ten.vercel.app/files/{file_id}"
        
        # Prepare update data
        update_data = {"vehicle_picture_url": vehicle_picture_url}
        
        # Update file_ids collection if it exists
        existing_file_ids = rider.get("file_ids", {})
        existing_file_ids["vehicle_picture"] = file_id
        update_data["file_ids"] = existing_file_ids
        
        success = update_rider_details_db(
            rider_id, 
            update_data
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update rider profile with vehicle picture URL"
            )
        
        return {
            "status": "success",
            "message": "Vehicle picture updated successfully",
            "vehicle_picture_url": vehicle_picture_url
        }
    
    except Exception as e:
        print(f"Error updating vehicle picture: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update vehicle picture: {str(e)}"
        )

@app.put("/users/{user_id}/update")
async def update_user_details(
    user_id: str,
    firstname: str = Form(None),
    lastname: str = Form(None),
    phone: str = Form(None),
    email_notification: bool = Form(None),
    push_notification: bool = Form(None),
):
    """
    Endpoint to update user's details.
    """
    # Get the user first
    user = get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prepare update data (only include fields that are provided)
    update_data = {}
    if firstname: update_data["firstname"] = firstname
    if lastname: update_data["lastname"] = lastname
    if phone: update_data["phone"] = phone
    if email_notification is not None: update_data["email_notification"] = email_notification
    if push_notification is not None: update_data["push_notification"] = push_notification
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    # Update user details
    success = update_user_details_db(user_id, update_data)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user details")
    
    return {
        "status": "success",
        "message": "User details updated successfully",
        "user_id": user_id
    }

@app.put("/auth/change-password/{user_type}/{user_id}")
async def change_password(
    user_type: str,
    user_id: str,
    old_password: str = Form(...),
    new_password: str = Form(...),
):
    """
    Endpoint to change password for both riders and users.
    Requires verification of old password before changing.
    """
    if user_type not in ["rider", "user"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid user type. Must be 'rider' or 'user'."
        )
    
    # Get the user/rider based on type
    if user_type == "rider":
        user_data = get_rider_by_id(user_id)
        update_function = update_rider_details_db
    else:
        user_data = get_user_by_id(user_id)
        update_function = update_user_details_db
    
    if not user_data:
        raise HTTPException(status_code=404, detail=f"{user_type.capitalize()} not found")
    
    # Verify old password
    hashed_old_password = hash_password_sha256(old_password)
    if user_data["password"] != hashed_old_password:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Hash and update new password
    hashed_new_password = hash_password_sha256(new_password)
    success = update_function(user_id, {"password": hashed_new_password})
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update password")
    
    return {
        "status": "success",
        "message": "Password updated successfully"
    }


# Function to generate random reset code
def generate_reset_code():
    """Generate a 6-digit reset code"""
    return ''.join(random.choices(string.digits, k=6))

@app.post("/auth/forgot-password/{user_type}")
async def forgot_password(
    user_type: str,
    *,
    email: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Endpoint to handle forgot password requests.
    Generates a reset code and sends it to user's email.
    """
    if user_type not in ["rider", "user"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid user type. Must be 'rider' or 'user'."
        )
    
    # Get user data based on type
    if user_type == "rider":
        user_data = get_rider_by_email(email)
        update_function = update_rider_details_db
    else:
        user_data = get_user_by_email(email)
        update_function = update_user_details_db
    
    if not user_data:
        raise HTTPException(
            status_code=404,
            detail=f"No {user_type} found with this email"
        )
    
    # Generate and store reset code
    reset_code = generate_reset_code()
    hashed_reset_code = hash_password_sha256(reset_code)
    
    # Store the reset code and its expiration
    success = update_function(
        str(user_data["_id"]),
        {
            "reset_code": hashed_reset_code,
            "reset_code_expiry": datetime.utcnow() + timedelta(minutes=15)
        }
    )
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to process password reset request"
        )
    
    # Send email and check if it was successful
    email_sent = send_reset_code_email(email, reset_code, user_type)
    
    if not email_sent:
        # Rollback the reset code update
        update_function(
            str(user_data["_id"]),
            {
                "reset_code": None,
                "reset_code_expiry": None
            }
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to send reset code email. Please try again later."
        )
    
    return {
        "status": "success",
        "message": "Password reset code has been sent to your email"
    }

@app.post("/auth/reset-password/{user_type}")
async def reset_password(
    user_type: str,
    email: str = Form(...),
    reset_code: str = Form(...),
    new_password: str = Form(...)
):
    """
    Endpoint to reset password using the reset code.
    """
    if user_type not in ["rider", "user"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid user type. Must be 'rider' or 'user'."
        )
    
    # Get user data based on type
    if user_type == "rider":
        user_data = get_rider_by_email(email)
        update_function = update_rider_details_db
    else:
        user_data = get_user_by_email(email)
        update_function = update_user_details_db
    
    if not user_data:
        raise HTTPException(
            status_code=404,
            detail=f"No {user_type} found with this email"
        )
    
    # Verify reset code and its expiration
    if not user_data.get("reset_code"):
        raise HTTPException(
            status_code=400,
            detail="No reset code was requested"
        )
    
    if datetime.utcnow() > user_data.get("reset_code_expiry"):
        raise HTTPException(
            status_code=400,
            detail="Reset code has expired"
        )
    
    hashed_reset_code = hash_password_sha256(reset_code)
    if user_data["reset_code"] != hashed_reset_code:
        raise HTTPException(
            status_code=400,
            detail="Invalid reset code"
        )
    
    # Update password and remove reset code data
    hashed_password = hash_password_sha256(new_password)
    success = update_function(
        str(user_data["_id"]),
        {
            "password": hashed_password,
            "reset_code": None,
            "reset_code_expiry": None
        }
    )
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to reset password"
        )
    
    return {
        "status": "success",
        "message": "Password has been reset successfully"
    }


@app.post("/check-email/{user_type}")
async def check_user_email(user_type: str, email: str = Form(...)):
    """
    Endpoint to check email.
    """
    try:  # Add this try block if it's not already there
        if user_type not in ["rider", "user"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid user type. Must be 'rider' or 'user'."
            )
        
        # Get user data based on type
        if user_type == "rider":
            user_data = get_rider_by_email(email)
        else:
            user_data = get_user_by_email(email)
        
        exists = bool(user_data)
        
        return {
            "status": "endpoint ran successfully",
            "message": exists
        }
    except Exception as e:  # Add this except block
        print(f"Error checking email: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check email: {str(e)}"
        ) 
    

def parse_location_string(location_str: str) -> dict:
    """
    Parse location string to extract coordinates and address
    Expected format: JSON string like '{"latitude": 6.5244, "longitude": 3.3792, "address": "Lagos, Nigeria"}'
    """
    try:
        if isinstance(location_str, str):
            # Try to parse as JSON first
            location_dict = json.loads(location_str)
            return location_dict
        elif isinstance(location_str, dict):
            # Already a dictionary
            return location_str
        else:
            # Plain address string, no coordinates
            return {"address": str(location_str), "latitude": None, "longitude": None}
    except json.JSONDecodeError:
        # If JSON parsing fails, treat as plain address
        return {"address": location_str, "latitude": None, "longitude": None}
    
@app.post("/delivery/bike")
async def create_bike_delivery(request: BikeDeliveryRequest, background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Endpoint to create a new bike delivery request.
    """
    # Validate vehicle type
    if request.vehicletype.lower() != "bike":
        raise HTTPException(
            status_code=400,
            detail="Invalid vehicle type. Must be 'bike'."
        )
    
    # Validate transaction type
    if request.transactiontype.lower() not in ["cash", "online"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid transaction type. Choose 'cash' or 'online'."
        )
    
    # Validate delivery speed
    if request.deliveryspeed.lower() not in ["express", "standard"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid delivery speed. Choose 'express' or 'standard'."
        )
    
    # Parse location data
    startpoint_data = parse_location_string(request.startpoint)
    endpoint_data = parse_location_string(request.endpoint)
    
    # Prepare the delivery data
    delivery_data = {
        "user_id": request.user_id,
        "price": request.price,
        "distance": request.distance,
        "startpoint": startpoint_data,
        "endpoint": endpoint_data,
        "stops": request.stops,
        "vehicletype": request.vehicletype.lower(),
        "transactiontype": request.transactiontype.lower(),
        "packagesize": request.packagesize,
        "deliveryspeed": request.deliveryspeed.lower(),
        "status": request.status.dict(),
        "transaction_info": {
            "payment_status": "pending",
            "payment_date": None,
            "amount_paid": request.price,
            "payment_reference": None,
            "last_updated": datetime.utcnow()
        }
    }
    
    # Insert the delivery data into the database
    delivery_id = insert_delivery(delivery_data)
    
    # Send notifications if delivery was created successfully
    if delivery_id:
        try:
            # Get user info for notifications
            user = get_user_by_id(request.user_id)
            
            if user:
                # 1. PUSH NOTIFICATION TO USER
                if user.get("push_notification", True):
                    try:
                        send_push_notification(
                            user_id=request.user_id,
                            message=f"Your {request.vehicletype.lower()} delivery has been created and riders are being notified",
                            title="New Delivery Created",
                            data={
                                "type": "new_delivery",
                                "delivery_id": delivery_id,
                                "vehicle_type": request.vehicletype.lower(),
                            }
                        )
                    except Exception as e:
                        print(f"Error sending push notification to user: {str(e)}")
                
                # 2. NOTIFY AVAILABLE RIDERS (with matching vehicle type)
                try:
                    # Get all active riders with matching vehicle type
                    matching_riders = list(riders_collection.find({
                        "status": "active",
                        "vehicle_type": request.vehicletype.lower(),
                        "push_notification": True
                    }))
                    
                    # Send push notification to each matching rider
                    for rider in matching_riders:
                        rider_id = str(rider["_id"])
                        send_push_notification(
                            user_id=rider_id,
                            message=f"New {request.vehicletype.lower()} delivery available! Price: ${request.price} - Distance: {request.distance} km",
                            title="New Delivery Available",
                            data={
                                "type": "new_delivery_opportunity",
                                "delivery_id": delivery_id,
                                "price": request.price,
                                "vehicle_type": request.vehicletype.lower(),
                                "distance": request.distance,
                            }
                        )
                    print(f"Push notifications sent to {len(matching_riders)} riders")
                        
                except Exception as e:
                    print(f"Error notifying riders: {str(e)}")
                    

                # 3. SEND EMAIL NOTIFICATION TO NEARBY RIDERS
                try:
                    # Check if we have location coordinates in parsed startpoint
                    if (startpoint_data.get("latitude") and 
                        startpoint_data.get("longitude")):
                        
                        # Send location-based email notifications to nearby riders
                        await notify_nearby_riders(
                            delivery_id,
                            startpoint_data,  # Use parsed location data
                            request.vehicletype.lower(),
                            background_tasks
                        )
                        print(f"Location-based email notifications sent for delivery {delivery_id}")
                    else:
                        print(f"No location coordinates provided for delivery {delivery_id}")
                        
                except Exception as e:
                    print(f"Error sending location-based email notifications: {str(e)}")
                    
        except Exception as e:
            print(f"Error sending delivery notifications: {str(e)}")
    
    return {
        "status": "success",
        "message": "Bike delivery created successfully!",
        "delivery_id": delivery_id
    }

@app.post("/delivery/car")
async def create_car_delivery(request: CarDeliveryRequest, background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Endpoint to create a new car delivery request.
    """
    # Validate vehicle type
    if request.vehicletype.lower() != "car":
        raise HTTPException(
            status_code=400,
            detail="Invalid vehicle type. Must be 'car'."
        )
    
    # Validate transaction type
    if request.transactiontype.lower() not in ["cash", "online"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid transaction type. Choose 'cash' or 'online'."
        )
    
    # Validate delivery speed
    if request.deliveryspeed.lower() not in ["express", "standard"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid delivery speed. Choose 'express' or 'standard'."
        )
        
    # Parse location data
    startpoint_data = parse_location_string(request.startpoint)
    endpoint_data = parse_location_string(request.endpoint)
    
    # Prepare the delivery data
    delivery_data = {
        "user_id": request.user_id,
        "price": request.price,
        "distance": request.distance,
        "startpoint": startpoint_data,
        "endpoint": endpoint_data,
        "stops": request.stops,
        "vehicletype": request.vehicletype.lower(),
        "transactiontype": request.transactiontype.lower(),
        "deliveryspeed": request.deliveryspeed.lower(),
        "status": request.status.dict(),
        "transaction_info": {
            "payment_status": "pending",
            "payment_date": None,
            "amount_paid": request.price,
            "payment_reference": None,
            "last_updated": datetime.utcnow()
        }
    }
    
    # Insert the delivery data into the database
    delivery_id = insert_delivery(delivery_data)
    
    # Send notifications if delivery was created successfully
    if delivery_id:
        try:
            # Get user info for notifications
            user = get_user_by_id(request.user_id)
            
            if user:
                # 1. PUSH NOTIFICATION TO USER
                if user.get("push_notification", True):
                    try:
                        send_push_notification(
                            user_id=request.user_id,
                            message=f"Your {request.vehicletype.lower()} delivery has been created and riders are being notified",
                            title="New Delivery Created",
                            data={
                                "type": "new_delivery",
                                "delivery_id": delivery_id,
                                "vehicle_type": request.vehicletype.lower(),
                            }
                        )
                    except Exception as e:
                        print(f"Error sending push notification to user: {str(e)}")
                
                # 2. NOTIFY AVAILABLE RIDERS (with matching vehicle type)
                try:
                    # Get all active riders with matching vehicle type
                    matching_riders = list(riders_collection.find({
                        "status": "active",
                        "vehicle_type": request.vehicletype.lower(),
                        "push_notification": True
                    }))
                    
                    # Send push notification to each matching rider
                    for rider in matching_riders:
                        rider_id = str(rider["_id"])
                        send_push_notification(
                            user_id=rider_id,
                            message=f"New {request.vehicletype.lower()} delivery available! Price: ${request.price} - Distance: {request.distance} km",
                            title="New Delivery Available",
                            data={
                                "type": "new_delivery_opportunity",
                                "delivery_id": delivery_id,
                                "price": request.price,
                                "vehicle_type": request.vehicletype.lower(),
                                "distance": request.distance,
                            }
                        )
                    print(f"Push notifications sent to {len(matching_riders)} riders")
                        
                except Exception as e:
                    print(f"Error notifying riders: {str(e)}")
                    

                # 3. SEND EMAIL NOTIFICATION TO NEARBY RIDERS
                try:
                    # Check if we have location coordinates in parsed startpoint
                    if (startpoint_data.get("latitude") and 
                        startpoint_data.get("longitude")):
                        
                        # Send location-based email notifications to nearby riders
                        await notify_nearby_riders(
                            delivery_id,
                            startpoint_data,  # Use parsed location data
                            request.vehicletype.lower(),
                            background_tasks
                        )
                        print(f"Location-based email notifications sent for delivery {delivery_id}")
                    else:
                        print(f"No location coordinates provided for delivery {delivery_id}")
                        
                except Exception as e:
                    print(f"Error sending location-based email notifications: {str(e)}")
        except Exception as e:
            print(f"Error sending delivery notifications: {str(e)}")
    
    return {
        "status": "success",
        "message": "Car delivery created successfully!",
        "delivery_id": delivery_id
    }

@app.post("/delivery/bus")
async def create_bus_delivery(request: CarDeliveryRequest, background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Endpoint to create a new car delivery request.
    """
    # Validate vehicle type
    if request.vehicletype.lower() != "bus":
        raise HTTPException(
            status_code=400,
            detail="Invalid vehicle type. Must be 'bus'"
        )
    
    # Validate transaction type
    if request.transactiontype.lower() not in ["cash", "online"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid transaction type. Choose 'cash' or 'online'."
        )
        
    # For bus deliveries, set delivery speed to "bus" (override client input)
    delivery_speed = "bus"
    
    # Parse location data
    startpoint_data = parse_location_string(request.startpoint)
    endpoint_data = parse_location_string(request.endpoint)
    
    # Prepare the delivery data
    delivery_data = {
        "user_id": request.user_id,
        "price": request.price,
        "distance": request.distance,
        "startpoint": startpoint_data,
        "endpoint": endpoint_data,
        "stops": request.stops,
        "vehicletype": request.vehicletype.lower(),
        "transactiontype": request.transactiontype.lower(),
        "deliveryspeed": delivery_speed,
        "status": request.status.dict(),
        "transaction_info": {
            "payment_status": "pending",
            "payment_date": None,
            "amount_paid": request.price,
            "payment_reference": None,
            "last_updated": datetime.utcnow()
        }
    }
    
    # Insert the delivery data into the database
    delivery_id = insert_delivery(delivery_data)
    
    # Send notifications if delivery was created successfully
    if delivery_id:
        try:
            # Get user info for notifications
            user = get_user_by_id(request.user_id)
            
            if user:
                # 1. PUSH NOTIFICATION TO USER
                if user.get("push_notification", True):
                    try:
                        send_push_notification(
                            user_id=request.user_id,
                            message=f"Your {request.vehicletype.lower()} delivery has been created and riders are being notified",
                            title="New Delivery Created",
                            data={
                                "type": "new_delivery",
                                "delivery_id": delivery_id,
                                "vehicle_type": request.vehicletype.lower(),
                            }
                        )
                    except Exception as e:
                        print(f"Error sending push notification to user: {str(e)}")
                
                # 2. NOTIFY AVAILABLE RIDERS (with matching vehicle type)
                try:
                    # Get all active riders with matching vehicle type
                    matching_riders = list(riders_collection.find({
                        "status": "active",
                        "vehicle_type": request.vehicletype.lower(),
                        "push_notification": True
                    }))
                    
                    # Send push notification to each matching rider
                    for rider in matching_riders:
                        rider_id = str(rider["_id"])
                        send_push_notification(
                            user_id=rider_id,
                            message=f"New {request.vehicletype.lower()} delivery available! Price: ${request.price} - Distance: {request.distance} km",
                            title="New Delivery Available",
                            data={
                                "type": "new_delivery_opportunity",
                                "delivery_id": delivery_id,
                                "price": request.price,
                                "vehicle_type": request.vehicletype.lower(),
                                "distance": request.distance,
                            }
                        )
                    print(f"Push notifications sent to {len(matching_riders)} riders")
                        
                except Exception as e:
                    print(f"Error notifying riders: {str(e)}")
                    

                # 3. SEND EMAIL NOTIFICATION TO NEARBY RIDERS
                try:
                    # Check if we have location coordinates in parsed startpoint
                    if (startpoint_data.get("latitude") and 
                        startpoint_data.get("longitude")):
                        
                        # Send location-based email notifications to nearby riders
                        await notify_nearby_riders(
                            delivery_id,
                            startpoint_data,# Use parsed location data
                            request.vehicletype.lower(),
                            background_tasks
                        )
                        print(f"Location-based email notifications sent for delivery {delivery_id}")
                    else:
                        print(f"No location coordinates provided for delivery {delivery_id}")
                        
                except Exception as e:
                    print(f"Error sending location-based email notifications: {str(e)}")
                    
        except Exception as e:
            print(f"Error sending delivery notifications: {str(e)}")
    
    return {
        "status": "success",
        "message": "Bus delivery created successfully!",
        "delivery_id": delivery_id
    }


@app.post("/delivery/truck")
async def create_truck_delivery(request: CarDeliveryRequest, background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Endpoint to create a new car delivery request.
    """
    # Validate vehicle type
    if request.vehicletype.lower() != "truck":
        raise HTTPException(
            status_code=400,
            detail="Invalid vehicle type. Must be 'truck."
        )
    
    # Validate transaction type
    if request.transactiontype.lower() not in ["cash", "online"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid transaction type. Choose 'cash' or 'online'."
        )
        
        
    # For truck deliveries, set delivery speed to "truck" (override client input)
    delivery_speed = "truck"
        
    # Parse location data
    startpoint_data = parse_location_string(request.startpoint)
    endpoint_data = parse_location_string(request.endpoint)
    
    # Prepare the delivery data
    delivery_data = {
        "user_id": request.user_id,
        "price": request.price,
        "distance": request.distance,
        "startpoint": startpoint_data,
        "endpoint": endpoint_data,
        "stops": request.stops,
        "vehicletype": request.vehicletype.lower(),
        "transactiontype": request.transactiontype.lower(),
        "deliveryspeed": delivery_speed,
        "status": request.status.dict(),
        "transaction_info": {
            "payment_status": "pending",
            "payment_date": None,
            "amount_paid": request.price,
            "payment_reference": None,
            "last_updated": datetime.utcnow()
        }
    }
    
    # Insert the delivery data into the database
    delivery_id = insert_delivery(delivery_data)
    
    # Send notifications if delivery was created successfully
    if delivery_id:
        try:
            # Get user info for notifications
            user = get_user_by_id(request.user_id)
            
            if user:
                # 1. PUSH NOTIFICATION TO USER
                if user.get("push_notification", True):
                    try:
                        send_push_notification(
                            user_id=request.user_id,
                            message=f"Your {request.vehicletype.lower()} delivery has been created and riders are being notified",
                            title="New Delivery Created",
                            data={
                                "type": "new_delivery",
                                "delivery_id": delivery_id,
                                "vehicle_type": request.vehicletype.lower(),
                            }
                        )
                    except Exception as e:
                        print(f"Error sending push notification to user: {str(e)}")
                
                # 2. NOTIFY AVAILABLE RIDERS (with matching vehicle type)
                try:
                    # Get all active riders with matching vehicle type
                    matching_riders = list(riders_collection.find({
                        "status": "active",
                        "vehicle_type": request.vehicletype.lower(),
                        "push_notification": True
                    }))
                    
                    # Send push notification to each matching rider
                    for rider in matching_riders:
                        rider_id = str(rider["_id"])
                        send_push_notification(
                            user_id=rider_id,
                            message=f"New {request.vehicletype.lower()} delivery available! Price: ${request.price} - Distance: {request.distance} km",
                            title="New Delivery Available",
                            data={
                                "type": "new_delivery_opportunity",
                                "delivery_id": delivery_id,
                                "price": request.price,
                                "vehicle_type": request.vehicletype.lower(),
                                "distance": request.distance,
                            }
                        )
                    print(f"Push notifications sent to {len(matching_riders)} riders")
                        
                except Exception as e:
                    print(f"Error notifying riders: {str(e)}")
                    

                # 3. SEND EMAIL NOTIFICATION TO NEARBY RIDERS
                try:
                    # Check if we have location coordinates in parsed startpoint
                    if (startpoint_data.get("latitude") and 
                        startpoint_data.get("longitude")):
                        
                        # Send location-based email notifications to nearby riders
                        await notify_nearby_riders(
                            delivery_id,
                            startpoint_data,  # Use parsed location data
                            request.vehicletype.lower(),
                            background_tasks
                        )
                        print(f"Location-based email notifications sent for delivery {delivery_id}")
                    else:
                        print(f"No location coordinates provided for delivery {delivery_id}")
                        
                except Exception as e:
                    print(f"Error sending location-based email notifications: {str(e)}")
                    
        except Exception as e:
            print(f"Error sending delivery notifications: {str(e)}")
    
    return {
        "status": "success",
        "message": "Truck delivery created successfully!",
        "delivery_id": delivery_id
    }

@app.get("/files/{file_id}")
async def get_file(file_id: str):
    """
    Endpoint to retrieve files stored in GridFS.
    """
    try:
        binary_data = get_file_by_id(file_id)
        if not binary_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        return Response(
            content=binary_data,
            media_type="image/jpeg",
            headers={
                "Content-Disposition": "inline",
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*"
            }
        )
    except Exception as e:
        print(f"Error retrieving file: {e}")
        raise HTTPException(status_code=404, detail="File not found")


@app.put("/riders/{rider_id}/vehicle-picture")
async def update_rider_vehicle_picture(
    rider_id: str,
    vehicle_picture: UploadFile = File(...)
):
    """
    Endpoint to update or add a rider's vehicle picture.
    """
    # Verify rider exists
    rider = get_rider_by_id(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    try:
        # Read the uploaded file
        vehicle_picture_data = await vehicle_picture.read()
        
        # Save the vehicle picture to GridFS and get the file ID
        from database import save_file_to_gridfs
        file_id = save_file_to_gridfs(vehicle_picture_data, vehicle_picture.filename)
        
        if not file_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to save vehicle picture"
            )
        
        # Update the rider's profile with the picture URL and file ID
        vehicle_picture_url = f"https://deliveryapi-ten.vercel.app/files/{file_id}"
        
        # Prepare update data
        update_data = {"vehicle_picture_url": vehicle_picture_url}
        
        # Update file_ids collection if it exists
        existing_file_ids = rider.get("file_ids", {})
        existing_file_ids["vehicle_picture"] = file_id
        update_data["file_ids"] = existing_file_ids
        
        success = update_rider_details_db(
            rider_id, 
            update_data
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update rider profile with vehicle picture URL"
            )
        
        return {
            "status": "success",
            "message": "Vehicle picture updated successfully",
            "vehicle_picture_url": vehicle_picture_url
        }
    
    except Exception as e:
        print(f"Error updating vehicle picture: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update vehicle picture: {str(e)}"
        )


@app.put("/riders/{rider_id}/vehicle-picture")
async def update_rider_vehicle_picture(
    rider_id: str,
    vehicle_picture: UploadFile = File(...)
):
    """
    Endpoint to update or add a rider's vehicle picture.
    """
    # Verify rider exists
    rider = get_rider_by_id(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    try:
        # Read the uploaded file
        vehicle_picture_data = await vehicle_picture.read()
        
        # Save the vehicle picture to GridFS and get the file ID
        from database import save_file_to_gridfs
        file_id = save_file_to_gridfs(vehicle_picture_data, vehicle_picture.filename)
        
        if not file_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to save vehicle picture"
            )
        
        # Update the rider's profile with the picture URL and file ID
        vehicle_picture_url = f"https://deliveryapi-ten.vercel.app/files/{file_id}"
        
        # Prepare update data
        update_data = {"vehicle_picture_url": vehicle_picture_url}
        
        # Update file_ids collection if it exists
        existing_file_ids = rider.get("file_ids", {})
        existing_file_ids["vehicle_picture"] = file_id
        update_data["file_ids"] = existing_file_ids
        
        success = update_rider_details_db(
            rider_id, 
            update_data
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update rider profile with vehicle picture URL"
            )
        
        return {
            "status": "success",
            "message": "Vehicle picture updated successfully",
            "vehicle_picture_url": vehicle_picture_url
        }
    
    except Exception as e:
        print(f"Error updating vehicle picture: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update vehicle picture: {str(e)}"
        )

class ChatMessage(BaseModel):
    message: str
    timestamp: str  # Required field for client-side timestamp

@app.post("/chat/{delivery_id}/{sender_id}/{receiver_id}")
async def send_message(
    delivery_id: str,
    sender_id: str,
    receiver_id: str,
    message: ChatMessage
):
    """
    Send a chat message between user and rider.
    """
    
    try: 
        # Verify that both sender and receiver exist
        sender = get_user_by_id(sender_id) or get_rider_by_id(sender_id)
        receiver = get_user_by_id(receiver_id) or get_rider_by_id(receiver_id)
    
        if not sender or not receiver:
            raise HTTPException(status_code=404, detail="Sender or receiver not found")
        
        # Verify that the delivery exists
        delivery = get_delivery_by_id(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        
        # Always use client-provided timestamp to ensure correct local time
        timestamp = message.timestamp
        message_id = create_chat(sender_id, receiver_id, message.message, delivery_id, timestamp=timestamp)
        
        if not message_id:
            raise HTTPException(status_code=500, detail="Failed to create message")
        
        # Send push notification to the receiver using OneSignal
        from utils.push_utils import send_push_notification
            
        # Get sender name for the notification
        sender_name = f"{sender.get('firstname', '')} {sender.get('lastname', '')}"
        if not sender_name.strip():
                sender_name = "Someone"
        
        # prepare the notification data
        notification_data = {
            "type": 'chat',
            'delivery_id': delivery_id,
            'sender_id': sender_id,
            'message_id': message_id,
        }
                
        # Send the notification
        send_push_notification(
            user_id=receiver_id,
            message=message.message[:100] + ('...' if len(message.message) > 100 else ''),
            title=f"Message from {sender_name}",
            data=notification_data
        )
        
        return {
            "status": "success",
            "message_id": message_id,
            "delivery_id": delivery_id,
            "timestamp": timestamp,
        }
    
    except HTTPException as e:
        raise e
    
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@app.get("/chat/{delivery_id}")
async def get_messages(delivery_id: str):
    """
    Get all chat messages for a specific delivery.
    """
    # Verify that the delivery exists
    delivery = get_delivery_by_id(delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    # Get chat history
    messages = get_chat_history(delivery_id)
    
    return {
        "status": "success",
        "messages": messages
    }

@app.put("/chat/{delivery_id}/{receiver_id}/mark-read")
async def mark_read(delivery_id: str, receiver_id: str):
    """
    Mark all messages as read for a specific delivery and receiver.
    """
    success = mark_messages_as_read(receiver_id, delivery_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to mark messages as read"
        )
    
    return {
        "status": "success",
        "message": "Messages marked as read"
    }


@app.put("/users/{user_id}/delivery/{delivery_id}/edit")
async def edit_delivery_details(
    user_id: str,
    delivery_id: str,
    startpoint: Optional[str] = Form(None),
    endpoint: Optional[str] = Form(None),
    stops: Optional[str] = Form(None),  # JSON string of stops
    packagesize: Optional[str] = Form(None),
    deliveryspeed: Optional[str] = Form(None),
    transactiontype: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    distance: Optional[str] = Form(None),
    vehicletype: Optional[str] = Form(None),
    deliverytype: Optional[str] = Form(None),
):
    """
    Endpoint for users to edit their delivery details.
    Only allows editing if the delivery is still in 'pending' status.
    """
    try:
        # Verify delivery exists
        delivery = get_delivery_by_id(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        
        # Verify user owns this delivery
        if delivery.get("user_id") != user_id:
            raise HTTPException(
                status_code=403, 
                detail="You can only edit your own deliveries"
            )
        
        # Check if delivery is in a state that can be edited
        current_status = delivery.get("status", {}).get("current")
        if current_status not in ["pending"]:
            raise HTTPException(
                status_code=400,
                detail="Only pending deliveries can be edited"
            )
        
        # Prepare update data
        update_data = {}
        
        # Only include fields that are provided
        if startpoint:
            update_data["startpoint"] = startpoint
        
        if endpoint:
            update_data["endpoint"] = endpoint
        
        if stops:
            try:
                # Parse JSON string to list
                import json
                stops_list = json.loads(stops)
                if not isinstance(stops_list, list):
                    raise ValueError("Stops must be a list")
                update_data["stops"] = stops_list
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid JSON format for stops"
                )
        
        if packagesize:
            update_data["packagesize"] = packagesize
        
        if deliveryspeed:
            if deliveryspeed.lower() not in ["express", "standard"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid delivery speed. Choose 'express' or 'standard'."
                )
            update_data["deliveryspeed"] = deliveryspeed.lower()
        
        if transactiontype:
            if transactiontype.lower() not in ["cash", "online"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid transaction type. Choose 'cash' or 'online'."
                )
            update_data["transactiontype"] = transactiontype.lower()
            
        if price is not None:  # Using 'is not None' to allow 0.0 as a valid price
            update_data["price"] = float(price)
            
        if distance:
            update_data["distance"] = distance
            
        if vehicletype:
            if vehicletype.lower() not in ["bike", "car"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid vehicle type. Choose 'bike' or 'car'."
                )
            update_data["vehicletype"] = vehicletype.lower()
            
        if deliverytype:
            if deliverytype.lower() not in ["standard", "express", "scheduled"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid delivery type. Choose 'standard', 'express', or 'scheduled'."
                )
            update_data["deliverytype"] = deliverytype.lower()
        
        if not update_data:
            raise HTTPException(
                status_code=400, 
                detail="No data provided for update"
            )
        
        # Add last updated timestamp
        update_data["last_updated"] = datetime.utcnow()
        
        # Update the delivery in database
        success = update_delivery(delivery_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update delivery details"
            )
        
        return {
            "status": "success",
            "message": "Delivery details updated successfully",
            "delivery_id": delivery_id,
            "updated_data": update_data
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error updating delivery details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update delivery details: {str(e)}"
        )

@app.get("/test/users-with-player-ids")
async def get_users_with_player_ids():
    """Get a list of users with registered player IDs for testing"""
    from database import users_collection, riders_collection
    
    # Find users with player_ids
    users = list(users_collection.find(
        {"player_id": {"$exists": True}}, 
        {"_id": 1, "firstname": 1, "lastname": 1, "player_id": 1}
    ))
    
    # Find riders with player_ids
    riders = list(riders_collection.find(
        {"player_id": {"$exists": True}}, 
        {"_id": 1, "firstname": 1, "lastname": 1, "player_id": 1}
    ))
    
    # Convert ObjectIds to strings for JSON serialization
    for user in users:
        user["_id"] = str(user["_id"])
    
    for rider in riders:
        rider["_id"] = str(rider["_id"])
    
    return {
        "status": "success",
        "users": users,
        "riders": riders
    }
class RatingRequest(BaseModel):
    rating: int
    comment: str = None
    delivery_id: str

# Add these endpoints after your existing endpoints

@app.post("/users/{user_id}/rate-rider/{rider_id}")
async def user_rate_rider(
    user_id: str,
    rider_id: str,
    rating_data: RatingRequest
):
    """
    Endpoint for users to rate riders after a delivery.
    """
    # Verify user exists
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify rider exists
    rider = get_rider_by_id(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    # Verify delivery exists and is completed
    delivery = get_delivery_by_id(rating_data.delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    # Check if delivery is completed
    if delivery.get("status", {}).get("current") != "completed":
        raise HTTPException(
            status_code=400, 
            detail="Can only rate completed deliveries"
        )
    
    # Check if the delivery involves both the user and rider
    if delivery.get("user_id") != user_id or delivery.get("rider_id") != rider_id:
        raise HTTPException(
            status_code=403,
            detail="You can only rate riders for your own deliveries"
        )
    
    # Create rating data
    rating_info = {
        "user_id": user_id,
        "rider_id": rider_id,
        "delivery_id": rating_data.delivery_id,
        "rating": rating_data.rating,
        "comment": rating_data.comment,
        "timestamp": datetime.utcnow()
    }
    
    # Save the rating
    rating_id = rate_rider(rating_info)
    
    if not rating_id:
        raise HTTPException(
            status_code=500,
            detail="Failed to save rating"
        )
    
    return {
        "status": "success",
        "message": "Rider rated successfully",
        "rating_id": rating_id,
        "rider_id": rider_id,
        "user_id": user_id
    }

@app.post("/riders/{rider_id}/rate-user/{user_id}")
async def rider_rate_user(
    rider_id: str,
    user_id: str,
    rating_data: RatingRequest
):
    """
    Endpoint for riders to rate users after a delivery.
    """
    # Verify rider exists
    rider = get_rider_by_id(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    # Verify user exists
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify delivery exists and is completed
    delivery = get_delivery_by_id(rating_data.delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    # Check if delivery is completed
    if delivery.get("status", {}).get("current") != "completed":
        raise HTTPException(
            status_code=400, 
            detail="Can only rate completed deliveries"
        )
    
    # Check if the delivery involves both the user and rider
    if delivery.get("user_id") != user_id or delivery.get("rider_id") != rider_id:
        raise HTTPException(
            status_code=403,
            detail="You can only rate users for deliveries you completed"
        )
    
    # Create rating data
    rating_info = {
        "user_id": user_id,
        "rider_id": rider_id,
        "delivery_id": rating_data.delivery_id,
        "rating": rating_data.rating,
        "comment": rating_data.comment,
        "timestamp": datetime.utcnow()
    }
    
    # Save the rating
    rating_id = rate_user(rating_info)
    
    if not rating_id:
        raise HTTPException(
            status_code=500,
            detail="Failed to save rating"
        )
    
    return {
        "status": "success",
        "message": "User rated successfully",
        "rating_id": rating_id,
        "rider_id": rider_id,
        "user_id": user_id
    }

@app.get("/riders/{rider_id}/ratings")
async def get_rider_rating_history(rider_id: str):
    """
    Get all ratings for a specific rider.
    """
    # Verify rider exists
    rider = get_rider_by_id(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    # Get ratings
    ratings = get_rider_ratings(rider_id)
    
    # Calculate average rating
    if ratings:
        avg_rating = sum(r.get("rating", 0) for r in ratings) / len(ratings)
    else:
        avg_rating = 0
    
    return {
        "status": "success",
        "rider_id": rider_id,
        "average_rating": round(avg_rating, 1),
        "total_ratings": len(ratings),
        "ratings": ratings
    }

@app.get("/users/{user_id}/ratings")
async def get_user_rating_history(user_id: str):
    """
    Get all ratings for a specific user.
    """
    # Verify user exists
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get ratings
    ratings = get_user_ratings(user_id)
    
    # Calculate average rating
    if ratings:
        avg_rating = sum(r.get("rating", 0) for r in ratings) / len(ratings)
    else:
        avg_rating = 0
    
    return {
        "status": "success",
        "user_id": user_id,
        "average_rating": round(avg_rating, 1),
        "total_ratings": len(ratings),
        "ratings": ratings
    }


@app.get("/riders/{rider_id}/overall-rating")
async def get_rider_overall_rating(rider_id: str):
    """
    Get the overall rating for a specific rider.
    """
    # Verify rider exists
    rider = get_rider_by_id(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    # Get all ratings for this rider
    ratings = get_rider_ratings(rider_id)
    
    # Calculate average rating
    if ratings:
        total_ratings = len(ratings)
        avg_rating = sum(r.get("rating", 0) for r in ratings) / total_ratings
        
        # Get rating distribution
        rating_distribution = {
            "5": len([r for r in ratings if r.get("rating") == 5]),
            "4": len([r for r in ratings if r.get("rating") == 4]),
            "3": len([r for r in ratings if r.get("rating") == 3]),
            "2": len([r for r in ratings if r.get("rating") == 2]),
            "1": len([r for r in ratings if r.get("rating") == 1])
        }
    else:
        total_ratings = 0
        avg_rating = 0
        rating_distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    
    return {
        "status": "success",
        "rider_id": rider_id,
        "rider_name": f"{rider.get('firstname', '')} {rider.get('lastname', '')}",
        "average_rating": round(avg_rating, 1),
        "total_ratings": total_ratings,
        "rating_distribution": rating_distribution
    }

@app.get("/users/{user_id}/overall-rating")
async def get_user_overall_rating(user_id: str):
    """
    Get the overall rating for a specific user.
    """
    # Verify user exists
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all ratings for this user
    ratings = get_user_ratings(user_id)
    
    # Calculate average rating
    if ratings:
        total_ratings = len(ratings)
        avg_rating = sum(r.get("rating", 0) for r in ratings) / total_ratings
        
        # Get rating distribution
        rating_distribution = {
            "5": len([r for r in ratings if r.get("rating") == 5]),
            "4": len([r for r in ratings if r.get("rating") == 4]),
            "3": len([r for r in ratings if r.get("rating") == 3]),
            "2": len([r for r in ratings if r.get("rating") == 2]),
            "1": len([r for r in ratings if r.get("rating") == 1])
        }
    else:
        total_ratings = 0
        avg_rating = 0
        rating_distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    
    return {
        "status": "success",
        "user_id": user_id,
        "user_name": f"{user.get('firstname', '')} {user.get('lastname', '')}",
        "average_rating": round(avg_rating, 1),
        "total_ratings": total_ratings,
        "rating_distribution": rating_distribution
    }


@app.put("/users/{user_id}/profile-picture")
async def update_user_profile_picture(
    user_id: str,
    profile_picture: UploadFile = File(...)
):
    """
    Endpoint to update or add a user's profile picture.
    """
    # Verify user exists
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Read the uploaded file
        profile_picture_data = await profile_picture.read()
        
        # Save the profile picture to GridFS and get the file ID
        from database import save_file_to_gridfs
        file_id = save_file_to_gridfs(profile_picture_data, profile_picture.filename)
        
        if not file_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to save profile picture"
            )
        
        # Update the user's profile with the picture URL
        profile_picture_url = f"https://deliveryapi-ten.vercel.app/files/{file_id}"
        success = update_user_details_db(
            user_id, 
            {"profile_picture_url": profile_picture_url}
        )
        
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update user profile with picture URL"
            )
        
        return {
            "status": "success",
            "message": "Profile picture updated successfully",
            "profile_picture_url": profile_picture_url
        }
    
    except Exception as e:
        print(f"Error updating profile picture: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update profile picture: {str(e)}"
        )


def send_push_notification(
    user_id: str, 
    message: str, 
    title: str = "New Message", 
    data: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send push notification to a user or rider using Firebase Admin SDK.
    
    Args:
        user_id: The ID of the user or rider to send notification to
        message: The notification message
        title: The notification title
        data: Additional data to send with the notification
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    from database import get_user_by_id, get_rider_by_id
    
    # If Firebase Admin SDK is not initialized, just log and return
    if app is None:
        print(f"[PUSH] Firebase Admin SDK not initialized. Would send notification to {user_id}: {title} - {message}")
        return False
    
    # Get the user or rider to check if they have push notifications enabled
    # and to get their FCM token
    user = get_user_by_id(user_id)
    if not user:
        user = get_rider_by_id(user_id)
    
    if not user:
        print(f"[PUSH] User/Rider {user_id} not found")
        return False
    
    # Check if user has push notifications enabled
    if not user.get("push_notification", False):
        print(f"[PUSH] User/Rider {user_id} has disabled push notifications")
        return False
    
    # Get FCM token - you need to store this when the user logs in from a device
    fcm_token = user.get("fcm_token")
    if not fcm_token:
        print(f"[PUSH] No FCM token found for user/rider {user_id}")
        return False
    
    try:
        # Create a message
        message_payload = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=message,
            ),
            token=fcm_token,
        )
        
        # Add data payload if provided
        if data:
            message_payload.data = data
        
        # Send the message
        response = messaging.send(message_payload)
        print(f"[PUSH] Successfully sent notification to {user_id}: {response}")
        return True
        
    except Exception as e:
        print(f"[PUSH] Error sending notification: {str(e)}")
        return False

@app.post("/test-notification")
async def the_test_notification(
    receiver_id: str = Form(...),
    title: str = Form("Test Notification"),
    message: str = Form("This is a test message")
):
    """
    Test endpoint to send a push notification to a specific user or rider using OneSignal.
    """
    try:
        from utils.push_utils import send_push_notification
        
        # Send the notification using our utility function
        result = send_push_notification(
            receiver_id,
            message,
            title=title,
            data={'type': 'test_notification'}
        )
        
        return result
            
    except Exception as e:
        error_message = f"Unexpected error in test notification: {str(e)}"
        print(error_message)
        return {
            "status": "error",
            "message": error_message
        }

@app.post("/register-device")
async def register_user_device(
    user_id: str = Form(...),
    player_id: str = Form(...),
    user_type: str = Form(...)  # "user" or "rider"
):
    """
    Register or update a user's OneSignal player ID for push notifications
    """
    try:
        # Determine if this is a user or rider
        if user_type.lower() == "user":
            user = get_user_by_id(user_id)
            if not user:
                return {"status": "error", "message": "User not found"}
            
            # Update the user with the player ID
            success = update_user_details_db(user_id, {"player_id": player_id})
        elif user_type.lower() == "rider":
            rider = get_rider_by_id(user_id)
            if not rider:
                return {"status": "error", "message": "Rider not found"}
            
            # Update the rider with the player ID
            success = update_rider_details_db(user_id, {"player_id": player_id})
        else:
            return {"status": "error", "message": "Invalid user type. Must be 'user' or 'rider'"}
        
        if success:
            return {"status": "success", "message": f"OneSignal player ID registered for {user_type}"}
        else:
            return {"status": "error", "message": f"Failed to update {user_type} record"}
            
    except Exception as e:
        return {"status": "error", "message": f"Error registering device: {str(e)}"}
        
# ================= Admin Endpoints =================

@app.post("/admin/signup")
async def admin_signup(
    username: str = Form(...),
    role: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    
    
    """
    Endpoint to handle admin signup.
    """
    # Check if email already exists
    existing_admin_email = get_admin_by_email(email)
    existing_admin_username = get_admin_by_username(username)
    if existing_admin_email or existing_admin_username:
        raise HTTPException(
            status_code=400, detail="An admin already used this email or username."
        )

    # Hash the password using SHA-256
    hashed_password = hash_password_sha256(password)

    # Prepare admin data
    admin_data = {
        "username": username,
        "role": role,
        "email": email,
        "password": hashed_password,  
        "date_joined": datetime.now()
    }

    # Insert admin into the database
    admin_id = insert_admin(admin_data)

    return {
        "status": "success",
        "message": "admin signed up successfully!",
        "admin_id": admin_id,
    }


@app.get("/admins")
def fetch_all_admins():
    """
    Endpoint to fetch all admins' data.
    """
    admins = get_all_admins()
    return {"status": "success", "admins": admins}


@app.post("/admin/signin")
async def admin_signin(username: str = Form(...), password: str = Form(...)):
    """
    Endpoint to handle admin sign-in. Verifies email and password (SHA-256 hash).
    """
    # Hash the password for comparison
    hashed_password = hash_password_sha256(password)

    # Find the admin in the database
    admin = get_admin_by_username(username)

    if admin and admin["password"] == hashed_password:
        # Convert ObjectId to string for serialization
        admin["_id"] = str(admin["_id"])
        return {
            "status": "success",
            "message": "admin signed in successfully!",
            "admin": admin,  # Return all admin data
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    

@app.get("/admins/{admin_id}")
def fetch_admin_by_id(admin_id: str):
    """
    Endpoint to fetch admin's data by their ID.
    """
    admin = get_admin_by_id(admin_id)

    if admin:
        # Convert ObjectId to string for serialization
        admin["_id"] = str(admin["_id"])
        return {"status": "success", "admin": admin}
    else:
        raise HTTPException(status_code=404, detail="Admin not found")
    
# change admin role
@app.put("/admins/{admin_id}/change-role")
async def change_admin_role(admin_id: str, role: str = Form(...)):
    """
    Endpoint to update a admin by changing their role.
    """
    # Get the admin first
    admin = get_admin_by_id(admin_id)
    
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    if admin["role"] == role:
        raise HTTPException(status_code=400, detail=f"Admin is already in '{role}' role")
    
    # Update admin role
    success = update_admin_role(admin_id, role)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update admin role")
    
    return {
        "status": "success",
        "message": f"Admin role changed successfully to {role}",
        "admin_id": admin_id
    }


# change admin details
@app.put("/admins/{admin_id}/update")
async def update_admin_details(
    admin_id: str,
    username: Optional[str] = None,
    role: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
):
    """
    Endpoint to update admin's details.
    """
    # Get the admin first
    admin = get_admin_by_id(admin_id)
    
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    # Prepare update data (only include fields that are provided)
    update_data = {}
    if username: update_data["username"] = username
    if role: update_data["role"] = role
    if email: update_data["email"] = email
    if password:  # Only hash if password is provided
        hashed_password = hash_password_sha256(password)
        update_data["password"] = hashed_password
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    # Update admin details
    success = update_admin_details_db(admin_id, update_data)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update admin details")
    
    return {
        "status": "success",
        "message": "Admin details updated successfully",
        "admin_id": admin_id
    }
    
# delete admin by id
@app.delete("/admins/{admin_id}/delete")
async def delete_admin(admin_id: str):
    admin = get_admin_by_id(admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    success = delete_admin_by_id(admin_id)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to delete admin {admin_id}")
    
    return {"status": "success", "message": "Admin deleted successfully"}    

# SEND EMAILS
@app.post("/send-email")
async def send_custom_email(json_data: EmailWithAttachments):
    """
    Endpoint to send custom emails with optional inline image.
    Only supports JSON format with optional base64-encoded images.
    """
    try:
        # Process the JSON data
        email_addr = json_data.email
        email_subject = json_data.subject
        email_body = json_data.body
        
        # Process base64 attachments
        image_content = None
        image_filename = None
        
        if json_data.attachments and len(json_data.attachments) > 0:
            # Take the first attachment
            attachment = json_data.attachments[0]
            import base64
            image_content = base64.b64decode(attachment['content'])
            image_filename = attachment.get('filename', 'image.jpg')
        
        # Validate required fields
        if not email_addr or not email_subject or not email_body:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: email, subject, or body"
            )
        
        # Format the message using existing template
        formatted_message = email_service.custom_email_template(email_body, has_image=bool(image_content))
        
        # Send email with or without image attachment
        if image_content:
            success = await email_service.send_email_with_image(
                subject=email_subject,
                recipients=[email_addr],
                body=formatted_message,
                image_data=image_content,
                image_filename=image_filename
            )
        else: 
            success = await email_service.send_email(
                subject=email_subject,
                recipients=[email_addr],
                body=formatted_message
            )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to send email: Check server logs for details"
            )
        
        return {
            "status": "success",
            "message": "Email sent successfully",
            "recipient": email_addr
        }
        
    except Exception as e:
        print(f"Error in send_custom_email: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email: {str(e)}"
        )
        
        

def send_push_notification(
    user_id: str, 
    message: str, 
    title: str = "New Message", 
    data: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send push notification to a user or rider using Firebase Admin SDK.
    
    Args:
        user_id: The ID of the user or rider to send notification to
        message: The notification message
        title: The notification title
        data: Additional data to send with the notification
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    
    # If Firebase Admin SDK is not initialized, just log and return
    if app is None:
        print(f"[PUSH] Firebase Admin SDK not initialized. Would send notification to {user_id}: {title} - {message}")
        return False
    
    # Get the user or rider to check if they have push notifications enabled
    # and to get their FCM token
    user = get_user_by_id(user_id)
    if not user:
        user = get_rider_by_id(user_id)
    
    if not user:
        print(f"[PUSH] User/Rider {user_id} not found")
        return False
    
    # Check if user has push notifications enabled
    if not user.get("push_notification", False):
        print(f"[PUSH] User/Rider {user_id} has disabled push notifications")
        return False
    
    # Get FCM token - you need to store this when the user logs in from a device
    fcm_token = user.get("fcm_token")
    if not fcm_token:
        print(f"[PUSH] No FCM token found for user/rider {user_id}")
        return False
    
    try:
        # Create a message
        message_payload = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=message,
            ),
            token=fcm_token,
        )
        
        # Add data payload if provided
        if data:
            message_payload.data = data
        
        # Send the message
        response = messaging.send(message_payload)
        print(f"[PUSH] Successfully sent notification to {user_id}: {response}")
        return True
        
    except Exception as e:
        print(f"[PUSH] Error sending notification: {str(e)}")
        return False

@app.post("/test-notification")
async def test_notification(
    receiver_id: str = Form(...),
    title: str = Form("Test Notification"),
    message: str = Form("This is a test message")
):
    """
    Test endpoint to send a push notification to a specific user or rider using OneSignal.
    """
    try:
        from utils.push_utils import send_push_notification
        
        # Send the notification using our utility function
        result = send_push_notification(
            receiver_id,
            message,
            title=title,
            data={'type': 'test_notification'}
        )
        
        return result
            
    except Exception as e:
        error_message = f"Unexpected error in test notification: {str(e)}"
        print(error_message)
        return {
            "status": "error",
            "message": error_message
        }

@app.post("/register-device")
async def register_device(
    user_id: str = Form(...),
    player_id: str = Form(...),
    user_type: str = Form(...)  # "user" or "rider"
):
    """
    Register or update a user's OneSignal player ID for push notifications
    """
    try:
        # Determine if this is a user or rider
        if user_type.lower() == "user":
            user = get_user_by_id(user_id)
            if not user:
                return {"status": "error", "message": "User not found"}
            
            # Update the user with the player ID
            success = update_user_details_db(user_id, {"player_id": player_id})
        elif user_type.lower() == "rider":
            rider = get_rider_by_id(user_id)
            if not rider:
                return {"status": "error", "message": "Rider not found"}
            
            # Update the rider with the player ID
            success = update_rider_details_db(user_id, {"player_id": player_id})
        else:
            return {"status": "error", "message": "Invalid user type. Must be 'user' or 'rider'"}
        
        if success:
            return {"status": "success", "message": f"OneSignal player ID registered for {user_type}"}
        else:
            return {"status": "error", "message": f"Failed to update {user_type} record"}
            
    except Exception as e:
        return {"status": "error", "message": f"Error registering device: {str(e)}"}
        
#
