from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from schemas.delivery_schema import CreateDeliveryRequest, RiderSignup
from database import (
    get_all_deliveries,
    get_delivery_by_id,
    get_rider_by_email,
    insert_delivery,
    insert_rider,
    ping_database,
    get_rider_by_id,
    get_all_riders,
    insert_user,
    get_user_by_email,
    get_user_by_id,
    get_all_users,
    update_rider_status,
    update_rider_details_db,
    update_user_details_db,
)
import hashlib
from fastapi import BackgroundTasks
import random
import string
from datetime import datetime, timedelta
from utils.email_utils import send_reset_code_email  # Add this import at the top
from schemas.delivery_schema import BikeDeliveryRequest, CarDeliveryRequest
from typing import Optional
from fastapi.responses import StreamingResponse
from database import get_file_by_id  # Add this to your database imports

app = FastAPI()


@app.get("/")
def read_root():
    """
    Root endpoint to confirm API is running.
    """
    return {"message": "Welcome to the Delivery App API"}


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
    bvn: str = Form(...),
    homeaddressdetails: str = Form(...),
    branding: str = Form(...),
    vehicle_type: str = Form(...),
    nationalid: UploadFile = File(...),
    recent_facial_picture: UploadFile = File(...),
    recent_utility_bill: UploadFile = File(...),
    registration_papers: UploadFile = File(...),
    license: UploadFile = File(...),
    email_notification: bool = Form(True),
    push_notification: bool = Form(True),
):
    """
    Endpoint to handle rider signup with required details and multiple file uploads.
    """
    # Validate vehicle type
    if vehicle_type.lower() not in ["bike", "car", "truck"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid vehicle type. Must be 'bike', 'car', or 'truck'."
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
        "bvn": bvn,
        "homeaddressdetails": homeaddressdetails,
        "branding": branding,
        "vehicle_type": vehicle_type.lower(),
        "email_notification": email_notification,
        "push_notification": push_notification,
        "earnings": 0,
        "status": "inactive"
    }

    # Read the uploaded files
    nationalid_file = await nationalid.read()
    facial_picture = await recent_facial_picture.read()
    utility_bill = await recent_utility_bill.read()
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

    return {
        "status": "success",
        "message": "Rider signed up successfully!",
        "rider_id": rider_id,
        "file_ids": file_ids
    }


@app.post("/ridersignin")
async def rider_signin(email: str = Form(...), password: str = Form(...)):
    """
    Endpoint to handle rider sign-in. Verifies email and password (SHA-256 hash).
    """
    # Hash the password for comparison
    hashed_password = hash_password_sha256(password)

    # Find the rider in the database
    rider = get_rider_by_email(email)

    if rider and rider["password"] == hashed_password:
        # Convert ObjectId to string for serialization
        rider["_id"] = str(rider["_id"])
        return {
            "status": "success",
            "message": "Rider signed in successfully!",
            "rider": rider,  # Return full rider data
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")


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
            rider["facial_picture_url"] = f"https://deliveryapi-plum.vercel.app/files/{facial_pic_id}"
        
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
):
    """
    Endpoint to handle user signup.
    """
    # Check if email already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        raise HTTPException(
            status_code=400, detail="A user with this email already exists."
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
    }

    # Insert user into the database
    user_id = insert_user(user_data)

    return {
        "status": "success",
        "message": "User signed up successfully!",
        "user_id": user_id,
    }


@app.post("/usersignin")
async def user_signin(email: str = Form(...), password: str = Form(...)):
    """
    Endpoint to handle user sign-in. Verifies email and password (SHA-256 hash).
    """
    # Hash the password for comparison
    hashed_password = hash_password_sha256(password)

    # Find the user in the database
    user = get_user_by_email(email)

    if user and user["password"] == hashed_password:
        # Convert ObjectId to string for serialization
        user["_id"] = str(user["_id"])
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



@app.get("/deliveries")
def fetch_all_deliveries():
    """
    Endpoint to fetch all deliveries.
    """
    deliveries = get_all_deliveries()

    if not deliveries:
        raise HTTPException(status_code=404, detail="No deliveries found")

    return {"status": "success", "deliveries": deliveries}


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
        "vehicletype": request.vehicletype.lower(),
        "transactiontype": request.transactiontype.lower(),
        "packagesize": request.packagesize,
        "deliveryspeed": request.deliveryspeed.lower(),
        "status": request.status.dict()
    }
    
    # Insert the delivery data into the database
    delivery_id = insert_delivery(delivery_data)
    
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
    
    # Prepare the delivery data
    delivery_data = {
        "user_id": request.user_id,
        "price": request.price,
        "distance": request.distance,
        "startpoint": request.startpoint,
        "endpoint": request.endpoint,
        "vehicletype": request.vehicletype.lower(),
        "transactiontype": request.transactiontype.lower(),
        "status": request.status.dict()
    }
    
    # Insert the delivery data into the database
    delivery_id = insert_delivery(delivery_data)
    
    return {
        "status": "success",
        "message": "Car delivery created successfully!",
        "delivery_id": delivery_id
    }


@app.get("/files/{file_id}")
async def get_file(file_id: str):
    """
    Endpoint to retrieve files stored in GridFS.
    """
    file_data = get_file_by_id(file_id)
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    return StreamingResponse(file_data, media_type="image/*")