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
)
import hashlib

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
    email: str = Form(...),
    password: str = Form(...),
    emergency_contact_name: str = Form(...),
    emergency_contact_phone: str = Form(...),
    accountbank: str = Form(...),
    accountname: str = Form(...),
    accountnumber: str = Form(...),
    bvn: str = Form(...),
    homeaddressdetails: str = Form(...),
    nationalid: UploadFile = File(...),
    recent_facial_picture: UploadFile = File(...),
    recent_utility_bill: UploadFile = File(...),
    bike_registration_papers: UploadFile = File(...),
    riders_license: UploadFile = File(...),
):
    """
    Endpoint to handle rider signup with required details and multiple file uploads.
    """

    # Hash the password using SHA-256
    hashed_password = hash_password_sha256(password)

    # Prepare the rider data
    rider_data = {
        "firstname": firstname,
        "lastname": lastname,
        "gender": gender,
        "email": email,
        "password": hashed_password,
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_phone": emergency_contact_phone,
        "accountbank": accountbank,
        "accountname": accountname,
        "accountnumber": accountnumber,
        "bvn": bvn,
        "homeaddressdetails": homeaddressdetails,
        "status": "inactive"
    }

    # Read the uploaded files
    nationalid_file = await nationalid.read()
    facial_picture = await recent_facial_picture.read()
    utility_bill = await recent_utility_bill.read()
    bike_papers = await bike_registration_papers.read()
    riders_license_file = await riders_license.read()

    # Insert rider data into MongoDB and save the uploaded files in GridFS
    rider_id, file_ids = insert_rider(
        rider_data,
        nationalid_file,
        facial_picture,
        utility_bill,
        bike_papers,
        riders_license_file,
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


@app.post("/createdelivery")
async def create_delivery(request: CreateDeliveryRequest):
    """
    Endpoint to create a new delivery request.
    The status will be an object with default empty data (can be updated later).
    """
    # Validate deliverytype and transactiontype
    if request.deliverytype not in ["express", "standard"]:
        raise HTTPException(status_code=400, detail="Invalid delivery type. Choose 'express' or 'standard'.")
    
    if request.transactiontype not in ["cash", "online"]:
        raise HTTPException(status_code=400, detail="Invalid transaction type. Choose 'cash' or 'online'.")
    
    # Prepare the delivery data to insert into the database
    delivery_data = {
        "user_id": request.user_id,
        "price": request.price,
        "distance": request.distance,
        "startpoint": request.startpoint,
        "endpoint": request.endpoint,
        "deliverytype": request.deliverytype,
        "transactiontype": request.transactiontype,
        "packagesize": request.packagesize,
        "status": request.status.dict()  # Store status as a dictionary
    }
    
    # Insert the delivery data into the database
    delivery_id = insert_delivery(delivery_data)
    
    return {
        "status": "success",
        "message": "Delivery created successfully!",
        "delivery_id": delivery_id
    }

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