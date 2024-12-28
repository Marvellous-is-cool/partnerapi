from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from pydantic import BaseModel
from schemas.delivery_schema import RiderSignup
from database import get_rider_by_email, insert_rider, ping_database, get_rider_by_id, get_all_riders
import hashlib
import pymongo

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
    sha256_hash.update(password.encode('utf-8'))
    return sha256_hash.hexdigest()

@app.post("/ridersignup")
async def rider_signup(
    firstname: str = Form(...),
    lastname: str = Form(...),
    gender: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    gurantorname: str = Form(...),
    gurantorphonenumber: str = Form(...),
    accountbank: str = Form(...),
    accountname: str = Form(...),
    bvn: str = Form(...),
    homeaddressdetails: str = Form(...),
    nationalid: UploadFile = File(...)
):
    """
    Endpoint to handle rider signup with required details and image upload.
    Data (except image) is passed in the form fields, and image is passed as a file.
    """
    # Hash the password using SHA-256
    hashed_password = hash_password_sha256(password)

    # Prepare the rider data from form fields
    rider_data = {
        "firstname": firstname,
        "lastname": lastname,
        "gender": gender,
        "email": email,
        "password": hashed_password,  # Use the hashed password
        "gurantorname": gurantorname,
        "gurantorphonenumber": gurantorphonenumber,
        "accountbank": accountbank,
        "accountname": accountname,
        "bvn": bvn,
        "homeaddressdetails": homeaddressdetails,
    }

    # Read the uploaded National ID file as bytes
    nationalid_file = await nationalid.read()

    # Insert rider data into MongoDB and save the nationalid file in GridFS
    rider_id, nationalid_file_id = insert_rider(rider_data, nationalid_file)

    return {
        "status": "success",
        "message": "Rider signed up successfully!",
        "rider_id": rider_id,  # Return the MongoDB inserted ID
        "nationalid_file_id": nationalid_file_id  # Return the GridFS file ID
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
        return {
            "status": "success",
            "message": "Rider signed in successfully!",
            "rider_id": str(rider["_id"])  # Return the rider's ID
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
        return {
            "status": "success",
            "rider": rider
        }
    else:
        raise HTTPException(status_code=404, detail="Rider not found")

@app.get("/riders")
def fetch_all_riders():
    """
    Endpoint to fetch all riders' data.
    """
    riders = get_all_riders()
    
    # Convert all ObjectIds to strings
    for rider in riders:
        rider["_id"] = str(rider["_id"])
    
    return {
        "status": "success",
        "riders": riders
    }