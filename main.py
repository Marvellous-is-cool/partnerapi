from fastapi import FastAPI, File, Form, UploadFile, HTTPException,Query
from schemas.delivery_schema import CreateDeliveryRequest, RiderSignup, BikeDeliveryRequest, CarDeliveryRequest, TransactionUpdateRequest, RiderLocationUpdate
from firebase_admin import messaging, credentials
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
    riders_collection
)
import hashlib
from fastapi import BackgroundTasks
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

from fastapi import BackgroundTasks
from email_service import EmailService
from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

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
    if vehicle_type.lower() not in ["bike", "car", "bus/truck"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid vehicle type. Must be 'bike', 'car', or 'bus/truck'."
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
    online: bool = Query(...),
):
    """
    Endpoint to update rider's online status.
    """
    # Get the rider first
    rider = get_rider_by_id(rider_id)
    
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    # Verify rider account is active
    if rider.get("status") != "active":
        raise HTTPException(status_code=403, detail="Rider account is not active, can't update status")
    
    # prepare update data
    update_online_data = {
        "is_online": online,
        "last_online": datetime.now() if online else None,
        "last_offline": datetime.now() if not online else None,
        "last_activity": datetime.now()
    }
    
    # Update rider online status in database
    success = update_rider_details_db(rider_id, update_online_data)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update rider online status")
    
    return {
        "status": "success",
        "message": f"Rider is now {'online' if online else 'offline'}",
        "rider_id": rider_id,
        "online": online
    }

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
        online_riders = filtered_riders
    
    return {
        "status": "success",
        "count": len(online_riders),
        "riders": online_riders
    }


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


@app.get("/deliveries/{delivery_id}")
def fetch_delivery_by_id(delivery_id: str):
    """
    Endpoint to fetch a delivery by its ID.
    """
    delivery = get_delivery_by_id(delivery_id)

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    return {"status": "success", "delivery": delivery}


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
    
@app.post("/delivery/bike")
async def create_bike_delivery(request: BikeDeliveryRequest):
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
    
    # Prepare the delivery data
    delivery_data = {
        "user_id": request.user_id,
        "price": request.price,
        "distance": request.distance,
        "startpoint": request.startpoint,
        "endpoint": request.endpoint,
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
                except Exception as e:
                    print(f"Error notifying riders: {str(e)}")
                    
        except Exception as e:
            print(f"Error sending delivery notifications: {str(e)}")
    
    return {
        "status": "success",
        "message": "Bike delivery created successfully!",
        "delivery_id": delivery_id
    }

@app.post("/delivery/car")
async def create_car_delivery(request: CarDeliveryRequest):
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
    
    # Prepare the delivery data
    delivery_data = {
        "user_id": request.user_id,
        "price": request.price,
        "distance": request.distance,
        "startpoint": request.startpoint,
        "endpoint": request.endpoint,
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
                except Exception as e:
                    print(f"Error notifying riders: {str(e)}")
                    
        except Exception as e:
            print(f"Error sending delivery notifications: {str(e)}")
    
    return {
        "status": "success",
        "message": "Car delivery created successfully!",
        "delivery_id": delivery_id
    }

@app.post("/delivery/bus-truck")
async def create_car_delivery(request: CarDeliveryRequest):
    """
    Endpoint to create a new car delivery request.
    """
    # Validate vehicle type
    if request.vehicletype.lower() != "bus" or request.vehicletype.lower() != "truck":
        raise HTTPException(
            status_code=400,
            detail="Invalid vehicle type. Must be 'bus' or 'truck."
        )
    
    # Validate transaction type
    if request.transactiontype.lower() not in ["cash", "online"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid transaction type. Choose 'cash' or 'online'."
        )
    
    # Validate delivery speed
    if request.deliveryspeed.lower() not in ["bus", "truck"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid delivery speed. Choose 'bus' or 'truck'."
        )
    
    # Prepare the delivery data
    delivery_data = {
        "user_id": request.user_id,
        "price": request.price,
        "distance": request.distance,
        "startpoint": request.startpoint,
        "endpoint": request.endpoint,
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
                except Exception as e:
                    print(f"Error notifying riders: {str(e)}")
                    
        except Exception as e:
            print(f"Error sending delivery notifications: {str(e)}")
    
    return {
        "status": "success",
        "message": "Bus / Truck delivery created successfully!",
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
    timestamp: Optional[str] = None

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
    # Verify that both sender and receiver exist
    sender = get_user_by_id(sender_id) or get_rider_by_id(sender_id)
    receiver = get_user_by_id(receiver_id) or get_rider_by_id(receiver_id)
    
    if not sender or not receiver:
        raise HTTPException(status_code=404, detail="Sender or receiver not found")
    
    # Verify that the delivery exists
    delivery = get_delivery_by_id(delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    # Use client timestamp if provided, otherwise use server timestamp
    timestamp = message.timestamp if message.timestamp else datetime.utcnow().isoformat()
    
    # Create the chat message with the timestamp
    chat_id = create_chat(sender_id, receiver_id, message.message, delivery_id, timestamp=timestamp)
    
    # Send push notification to the receiver using OneSignal
    try:
        from utils.push_utils import send_push_notification
        
        # Get sender name for the notification
        sender_name = f"{sender.get('firstname', '')} {sender.get('lastname', '')}"
        if not sender_name.strip():
            sender_name = "Someone"
            
        # Send the notification
        notification_title = f"Message from {sender_name}"
        notification_result = send_push_notification(
            receiver_id, 
            message.message, 
            title=notification_title,
            data={
                "type": "chat_message",
                "delivery_id": delivery_id,
                "sender_id": sender_id,
                "chat_id": chat_id
            }
        )
        
        # Log the notification result
        if notification_result["status"] == "error":
            print(f"OneSignal notification error: {notification_result['message']}")
    except Exception as e:
        print(f"Error sending OneSignal push notification: {str(e)}")
    
    return {
        "status": "success",
        "message": "Message sent successfully",
        "chat_id": chat_id
    }


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
                    "current": "pending",
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
            
            # Update the delivery status to completed
            update_data = {
                "status": {
                    "current": "completed",
                    "timestamp": datetime.utcnow()
                }
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


@app.put("/delivery/{delivery_id}/rider-location")
async def update_rider_location(
    delivery_id: str,
    rider_id: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    eta_minutes: Optional[int] = Form(None)
):
    """
    Endpoint to update rider's current location and ETA for a delivery.
    """
    try:
        # Verify delivery exists
        delivery = get_delivery_by_id(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        
        # Verify rider exists and is assigned to this delivery
        if delivery.get("rider_id") != rider_id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned rider can update location for this delivery"
            )
        
        # Check if delivery is in a valid state for location updates
        current_status = delivery.get("status", {}).get("current")
        if current_status not in ["ongoing", "inprogress"]:
            raise HTTPException(
                status_code=400,
                detail="Location can only be updated for ongoing or in-progress deliveries"
            )
        
        # Prepare location update data
        location_data = {
            "rider_location": {
                "rider_id": rider_id,
                "latitude": latitude,
                "longitude": longitude,
                "last_updated": datetime.utcnow()
            }
        }
        
        # Add ETA if provided
        if eta_minutes is not None:
            location_data["rider_location"]["eta_minutes"] = eta_minutes
            location_data["rider_location"]["eta_time"] = datetime.utcnow() + timedelta(minutes=eta_minutes)
        
        # Update the delivery in database
        success = update_delivery(delivery_id, location_data)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update rider location"
            )
        
        return {
            "status": "success",
            "message": "Rider location updated successfully",
            "delivery_id": delivery_id,
            "updated_data": location_data
        }
    
    except Exception as e:
        print(f"Error updating rider location: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update rider location: {str(e)}"
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
        
@app.get("/deliveries/{delivery_id}/rider-location")
async def get_delivery_location(delivery_id: str):
    """
    Endpoint to get delivery's current location and ETA for a delivery.
    """
    try:
        # Verify delivery exists
        delivery = get_delivery_by_id(delivery_id)
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        
        # Check if delivery is in a valid state for location updates
        current_status = delivery.get("status", {}).get("current")
        if current_status not in ["ongoing", "inprogress"]:
            raise HTTPException(
                status_code=400,
                detail="Location can only be retrieved for ongoing or in-progress deliveries"
            )
        
        # Get rider location from delivery data
        rider_location = delivery.get("rider_location")
        if not rider_location:
            raise HTTPException(
                status_code=404,
                detail="No location data available for this delivery"
            )
            
        
        return {
            "status": "success",
            "delivery_id": delivery_id,
            "rider_id": rider_location.get("rider_id"),
            "location_data": {
                "latitude": rider_location.get("latitude"),
                "longitude": rider_location.get("longitude"),
                "last_updated": rider_location.get("last_updated"),
                "eta_minutes": rider_location.get("eta_minutes"),
                "eta_time": rider_location.get("eta_time")
            }
        }
    
    except Exception as e:
        print(f"Error getting rider location: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get rider location: {str(e)}"
        )
    

# delete delivery by id
@app.delete("/deliveries/{delivery_id}/delete")
async def delete_delivery(delivery_id: str):
    delivery = get_delivery_by_id(delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    success = delete_delivery_by_id(delivery_id)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to delete delivery {delivery_id}")
    
    return {"status": "success", "message": "Delivery deleted successfully"}    

# delete all deliveries
@app.delete("/deliveries/delete")
async def delete_delivery(execute_code: str):
    code = "askthatmanheisagooodman"
    if execute_code != code:
        raise HTTPException(status_code=403, detail="Invalid code")
    
    # Call the delete_all_deliveries function
    deleted_count = delete_all_deliveries()
    
    # Check if any deliveries were deleted
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="No deliveries found to delete")
    
    return {"status": "success", "message": f"All deliveries deleted successfully. Total: {deleted_count}"}


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
async def send_custom_email(email_data: EmailRequest):
    """
    Endpoint to send custom emails.
    """
    try:
        formatted_message = email_service.custom_email_template(email_data.body)
        
        # Send email synchronously for testing
        success = await email_service.send_email(
            subject=email_data.subject,
            recipients=[email_data.email],
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
            "recipient": email_data.email
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
