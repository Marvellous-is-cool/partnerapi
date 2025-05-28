from typing import Dict
from bson import ObjectId
# from gridfs import GridFS
import gridfs
from pymongo import MongoClient
from datetime import datetime

MONGO_URI = (
    "mongodb+srv://primidac:teststring123###@micodelivery.mqfic.mongodb.net/"
    "?retryWrites=true&w=majority&appName=micodelivery"
)  

DATABASE_NAME = "delivery_app_db"

client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
riders_collection = db["riders"]
users_collection = db["users"]
admins_collection = db["admins"]
delivery_collection = db['deliveries']
chat_collection = db['chats']
archived_deliveries_collection = db['archived_deliveries']


fs = gridfs.GridFS(db)



def insert_rider(rider_data, nationalid_file, facial_picture, utility_bill, bike_papers, riders_license_file):
    """
    """
    nationalid_id = fs.put(nationalid_file, filename="nationalid", content_type="image/jpeg")
    facial_picture_id = fs.put(facial_picture, filename="facial_picture", content_type="image/jpeg")
    utility_bill_id = None
    if utility_bill:
        utility_bill_id = fs.put(utility_bill, filename="utility_bill", content_type="image/jpeg")
    bike_papers_id = fs.put(bike_papers, filename="bike_registration_papers", content_type="image/jpeg")
    riders_license_id = fs.put(riders_license_file, filename="riders_license", content_type="image/jpeg")

    rider_data["file_ids"] = {
        "nationalid": str(nationalid_id),
        "facial_picture": str(facial_picture_id),
        "utility_bill": str(utility_bill_id) if utility_bill_id else None,
        "bike_papers": str(bike_papers_id),
        "riders_license": str(riders_license_id),
    }
 
    rider_data["facial_picture_url"] = f"https://deliveryapi-ten.vercel.app/files/{str(facial_picture_id)}"

    rider_id = riders_collection.insert_one(rider_data).inserted_id

    return str(rider_id), rider_data["file_ids"]


def get_rider_by_email(email: str):
    """
    """
    return riders_collection.find_one({"email": email})

def get_rider_by_phone(phone: str):
    """
    """
    return riders_collection.find_one({"phone": phone})


def get_rider_by_id(rider_id: str):
    """
    """
    try:
        rider = riders_collection.find_one({"_id": ObjectId(rider_id)})
        
        if rider:
            # Ensure online status fields exist
            if "is_online" not in rider:
                rider["is_online"] = False
            if "last_online" not in rider:
                rider["last_online"] = None
            if "last_offline" not in rider:
                rider["last_offline"] = datetime.utcnow()
            if "last_activity" not in rider:
                rider["last_activity"] = datetime.utcnow()
                
        return rider
    except Exception as e:
        print(f"Error retrieving rider: {str(e)}")
        return None


def get_all_riders():
    """
    """
    riders = list(riders_collection.find())
    for rider in riders:
        rider["_id"] = str(rider["_id"])
    return riders


def delete_rider_by_id(rider_id: str) -> bool:
    """
    Delete a rider by ID.
    """
    try:
        result = riders_collection.delete_one({"_id": ObjectId(rider_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting rider: {e}")
        return False


def delete_selected_riders(rider_ids: list) -> int:
    """
    Delete multiple riders by their IDs.
    """
    try:
        object_ids = [ObjectId(rider_id) for rider_id in rider_ids]
        result = riders_collection.delete_many({"_id": {"$in": object_ids}})
        return result.deleted_count
    except Exception as e:
        print(f"Error deleting riders: {e}")
        return 0    
    
    
# ================= Users Functions =================

def insert_user(user_data: dict):
    """
    """
    user_id = users_collection.insert_one(user_data).inserted_id
    return str(user_id)


def get_user_by_email(email: str):
    """
    """
    return users_collection.find_one({"email": email})

def get_user_by_phone(phone: str):
    """
    """
    return users_collection.find_one({"phone": phone})


def get_user_by_id(user_id: str):
    """
    """
    return users_collection.find_one({"_id": ObjectId(user_id)})


def get_all_users():
    """
    """
    users = list(users_collection.find())
    for user in users:
        user["_id"] = str(user["_id"])
    return users


def delete_user_by_id(user_id: str) -> bool:
    """
    Delete a user by ID.
    """
    try:
        result = users_collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False


def delete_selected_users(user_ids: list) -> int:
    """
    Delete multiple users by their IDs.
    """
    try:
        object_ids = [ObjectId(user_id) for user_id in user_ids]
        result = users_collection.delete_many({"_id": {"$in": object_ids}})
        return result.deleted_count
    except Exception as e:
        print(f"Error deleting users: {e}")
        return 0    
    
# ================= Utility Functions =================


def ping_database():
    """
    """
    try:
        client.admin.command("ping")
        return True
    except Exception as e:
        print(f"Error pinging database: {e}")
        return False
    
def insert_delivery(delivery_data: Dict) -> str:
    """
    """
    result = delivery_collection.insert_one(delivery_data)
    return str(result.inserted_id)

def get_all_deliveries():
    """
    """
    deliveries = list(delivery_collection.find())  
    
    for delivery in deliveries:
        delivery["_id"] = str(delivery["_id"])
        
        if "status" in delivery and isinstance(delivery["status"], dict) and "timestamp" in delivery["status"]:
            if isinstance(delivery["status"]["timestamp"], datetime):
                delivery["status"]["timestamp"] = delivery["status"]["timestamp"].isoformat()
                
        if "last_updated" in delivery and isinstance(delivery["last_updated"], datetime):
            delivery["last_updated"] = delivery["last_updated"].isoformat()
            
    return deliveries

def get_delivery_by_id(delivery_id: str):
    """
    """
    delivery = delivery_collection.find_one({"_id": ObjectId(delivery_id)})

    if delivery:
        delivery["_id"] = str(delivery["_id"])  
    return delivery


def update_rider_status(rider_id: str, new_status: str) -> bool:
    """
 
    """
    try:
        result = riders_collection.update_one(
            {"_id": ObjectId(rider_id)},
            {"$set": {"status": new_status}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating rider status: {e}")
        return False


def update_rider_details_db(rider_id: str, update_data: dict) -> bool:
    """
   
    """
    try:
        result = riders_collection.update_one(
            {"_id": ObjectId(rider_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating rider details: {e}")
        return False

def update_user_details_db(user_id: str, update_data: dict) -> bool:
    """
    
    """
    try:
        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating user details: {e}")
        return False

def update_delivery(delivery_id, update_data):
    """
    """
    try:
        from bson import ObjectId
        
        delivery_id_obj = ObjectId(delivery_id)
        
        if "status" in update_data:
            if "rider_id" in update_data:
                result = delivery_collection.update_one(
                    {"_id": delivery_id_obj},
                    {
                        "$set": {
                            "rider_id": update_data["rider_id"],
                            "status": update_data["status"],
                            "last_updated": datetime.utcnow()
                        }
                    }
                )
            else:
                result = delivery_collection.update_one(
                    {"_id": delivery_id_obj},
                    {
                        "$set": {
                            "status": update_data["status"],
                            "last_updated": datetime.utcnow()
                        }
                    }
                )
        else:
            result = delivery_collection.update_one(
                {"_id": delivery_id_obj},
                {"$set": update_data}
            )
        
        print(f"Update result: {result.modified_count}")  
        return result.modified_count > 0
        
    except Exception as e:
        print(f"Error in update_delivery: {str(e)}")  
        return False


def get_file_by_id(file_id):
    """
    """
    try:
        file_id_obj = ObjectId(file_id)
        
        chunks = list(db.fs.chunks.find({'files_id': file_id_obj}).sort('n', 1))
        if not chunks:
            return None
            
        binary_data = b''.join(chunk['data'] for chunk in chunks)
        return binary_data
        
    except Exception as e:
        print(f"Error retrieving file: {e}")
        return None

def save_file_to_gridfs(file_data, filename, content_type="image/jpeg"):
    """
    """
    try:
        file_id = fs.put(file_data, filename=filename, content_type=content_type)
        return str(file_id)
    except Exception as e:
        print(f"Error saving file to GridFS: {e}")
        return None

def create_chat(sender_id, receiver_id, message, delivery_id, timestamp=None):
    """
    Create a new chat message between a sender and receiver for a specific delivery.
    """
    try:
        # Use provided timestamp or current time
        message_time = timestamp if timestamp else datetime.utcnow().isoformat()
        
        chat_data = {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "message": message,
            "delivery_id": delivery_id,
            "timestamp": message_time,
            "read": False
        }
        
        result = db.chats.insert_one(chat_data)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error creating chat: {str(e)}")
        return None

def get_chat_history(delivery_id: str):
    """
    Get chat history for a specific delivery.
    """
    chats = list(chat_collection.find({"delivery_id": delivery_id}).sort("timestamp", 1))
    for chat in chats:
        chat["_id"] = str(chat["_id"])
        if "timestamp" in chat:
            if isinstance(chat["timestamp"], datetime):
                chat["timestamp"] = chat["timestamp"].isoformat()
    return chats

def mark_messages_as_read(receiver_id: str, delivery_id: str):
    """
    """
    result = chat_collection.update_many(
        {
            "receiver_id": receiver_id,
            "delivery_id": delivery_id,
            "read": False
        },
        {"$set": {"read": True}}
    )
    return result.modified_count > 0


rider_ratings_collection = db['rider_ratings']
user_ratings_collection = db['user_ratings']

def rate_rider(rating_data):
    """
    """
    try:
        existing_rating = rider_ratings_collection.find_one({
            "user_id": rating_data["user_id"],
            "rider_id": rating_data["rider_id"],
            "delivery_id": rating_data["delivery_id"]
        })
        
        if existing_rating:
            result = rider_ratings_collection.update_one(
                {"_id": existing_rating["_id"]},
                {"$set": {
                    "rating": rating_data["rating"],
                    "comment": rating_data["comment"],
                    "timestamp": rating_data["timestamp"]
                }}
            )
            return str(existing_rating["_id"]) if result.modified_count > 0 else None
        else:
            result = rider_ratings_collection.insert_one(rating_data)
            return str(result.inserted_id)
    except Exception as e:
        print(f"Error saving rider rating: {e}")
        return None

def rate_user(rating_data):
    """
    """
    try:
        existing_rating = user_ratings_collection.find_one({
            "user_id": rating_data["user_id"],
            "rider_id": rating_data["rider_id"],
            "delivery_id": rating_data["delivery_id"]
        })
        
        if existing_rating:
            result = user_ratings_collection.update_one(
                {"_id": existing_rating["_id"]},
                {"$set": {
                    "rating": rating_data["rating"],
                    "comment": rating_data["comment"],
                    "timestamp": rating_data["timestamp"]
                }}
            )
            return str(existing_rating["_id"]) if result.modified_count > 0 else None
        else:
            result = user_ratings_collection.insert_one(rating_data)
            return str(result.inserted_id)
    except Exception as e:
        print(f"Error saving user rating: {e}")
        return None

def get_rider_ratings(rider_id):
    """
    """
    try:
        ratings = list(rider_ratings_collection.find({"rider_id": rider_id}))
        
        for rating in ratings:
            rating["_id"] = str(rating["_id"])
            if "timestamp" in rating and isinstance(rating["timestamp"], datetime):
                rating["timestamp"] = rating["timestamp"].isoformat()
        
        return ratings
    except Exception as e:
        print(f"Error getting rider ratings: {e}")
        return []

def get_user_ratings(user_id):
    """
    """
    try:
        ratings = list(user_ratings_collection.find({"user_id": user_id}))
        
        for rating in ratings:
            rating["_id"] = str(rating["_id"])
            if "timestamp" in rating and isinstance(rating["timestamp"], datetime):
                rating["timestamp"] = rating["timestamp"].isoformat()
        
        return ratings
    except Exception as e:
        print(f"Error getting user ratings: {e}")
        return []


def delete_account(user_id: str, account_type: str) -> bool:
    """
    Delete a user or rider account from the database based on their ID and account type.
    Returns True if the deletion was successful, False otherwise.
    """
    try:
        if account_type == "user":
            result = users_collection.delete_one({"_id": ObjectId(user_id)})
        elif account_type == "rider":
            result = riders_collection.delete_one({"_id": ObjectId(user_id)})
        else:
            raise ValueError("Invalid account type. Must be 'user' or 'rider'.")

        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting account: {e}")
        return False
    

def delete_delivery_by_id(delivery_id: str) -> bool:
    """
    Delete a delivery by ID.
    """
    try:
        result = delivery_collection.delete_one({"_id": ObjectId(delivery_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting delivery: {e}")
        return False
    
    
def delete_all_deliveries() -> int:
    """
    Delete all deliveries from the database.
    Returns the count of deleted deliveries.
    """
    try:
        result = delivery_collection.delete_many({})
        return result.deleted_count
    except Exception as e:
        print(f"Error deleting deliveries: {e}")
        return 0



    
# ================= Admins Functions =================

def insert_admin(admin_data: dict):
    """
    Insert admin data into MongoDB with hashed password.
    """
    # Hash the password before storing
    admin_id = admins_collection.insert_one(admin_data).inserted_id
    return str(admin_id)


def get_all_admins():
    """
    Fetch all admins' data.
    """
    admins = list(admins_collection.find())
    for admin in admins:
        admin["_id"] = str(admin["_id"])
    return admins


def get_admin_by_email(email: str):
    """
    Get admin data by email.
    """
    return admins_collection.find_one({"email": email})


def get_admin_by_username(username: str):
    """
    Get admin data by username.
    """
    return admins_collection.find_one({"username": username})


def get_admin_by_id(admin_id: str):
    """
    Get admin data by ID.
    """
    return admins_collection.find_one({"_id": ObjectId(admin_id)})


def delete_admin_by_id(admin_id: str) -> bool:
    """
    Delete a admin by ID.
    """
    try:
        result = admins_collection.delete_one({"_id": ObjectId(admin_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting admin: {e}")
        return False

def update_admin_role(admin_id: str, new_role: str) -> bool:
    """
    Update admin's role in the database.
    Returns True if update was successful, False otherwise.
    """
    try:
        result = admins_collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": {"role": new_role}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating admin role: {e}")
        return False


def update_admin_details_db(admin_id: str, update_data: dict) -> bool:
    """
    Update admin's details in the database.
    Returns True if update was successful, False otherwise.
    """
    try:
        result = admins_collection.update_one(
            {"_id": ObjectId(admin_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating admin details: {e}")
        return False
    
# archived deliveries
def archive_delivery(delivery_id: str) -> bool:
    """
    Move a delivery to archive instead of deleting it
    """
    try:
        # Get the delivery document
        delivery = delivery_collection.find_one({"_id": ObjectId(delivery_id)})
        if not delivery:
            return False
            
        # Add archive metadata
        delivery['archived_at'] = datetime.utcnow()
        delivery['archived_from_id'] = str(delivery['_id'])
        
        # Remove the old _id to get a new one in archive
        del delivery['_id']
        
        # Insert into archive
        result = archived_deliveries_collection.insert_one(delivery)
        if result.inserted_id:
            # Only delete from main collection if archive was successful
            delivery_collection.delete_one({"_id": ObjectId(delivery_id)})
            return True
            
        return False
        
    except Exception as e:
        print(f"Error archiving delivery: {str(e)}")
        return False



def permanently_delete_delivery(delivery_id: str, archive: bool = True) -> bool:
    """
    Permanently delete a delivery from either main or archive collection
    """
    try:
        collection = archived_deliveries_collection if archive else delivery_collection
        result = collection.delete_one({"archived_from_id": delivery_id} if archive else {"_id": ObjectId(delivery_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error permanently deleting delivery: {e}")
        return False

def restore_delivery(archived_id: str) -> bool:
    """
    Restore a delivery from archive to main collection
    """
    try:
        # Get the archived delivery
        archived = archived_deliveries_collection.find_one({"archived_from_id": archived_id})
        if not archived:
            return False
            
        # Remove archive metadata
        del archived['archived_at']
        original_id = archived['archived_from_id']
        del archived['archived_from_id']
        del archived['_id']  # Remove archive _id
        
        # Restore to main collection with original ID
        delivery_collection.insert_one({**archived, "_id": ObjectId(original_id)})
        
        # Remove from archive
        archived_deliveries_collection.delete_one({"archived_from_id": archived_id})
        
        return True
    except Exception as e:
        print(f"Error restoring delivery: {e}")
        return False

def get_archived_deliveries():
    """
    Get all archived deliveries with proper ObjectId handling
    """
    try:
        # Use empty filter to get all documents
        cursor = archived_deliveries_collection.find({})
        archived_list = []

        for delivery in cursor:
            try:
                # Convert ObjectIds to strings
                if "_id" in delivery:
                    delivery["_id"] = str(delivery["_id"])
                if "user_id" in delivery:
                    delivery["user_id"] = str(delivery["user_id"])
                if "rider_id" in delivery:
                    delivery["rider_id"] = str(delivery["rider_id"])
                if "archived_from_id" in delivery:
                    delivery["archived_from_id"] = str(delivery["archived_from_id"])

                # Convert datetime objects
                datetime_fields = ["archived_at", "created_at", "updated_at"]
                for field in datetime_fields:
                    if field in delivery and isinstance(delivery[field], datetime):
                        delivery[field] = delivery[field].isoformat()

                # Handle nested status timestamp
                if "status" in delivery and isinstance(delivery["status"], dict):
                    if "timestamp" in delivery["status"] and isinstance(delivery["status"]["timestamp"], datetime):
                        delivery["status"]["timestamp"] = delivery["status"]["timestamp"].isoformat()

                archived_list.append(delivery)
            except Exception as doc_error:
                print(f"Error processing document: {str(doc_error)}")
                continue

        return archived_list

    except Exception as e:
        print(f"Error in get_archived_deliveries: {str(e)}")
        return []    
