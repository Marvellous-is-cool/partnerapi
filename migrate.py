from database import riders_collection
from datetime import datetime

def migrate_rider_online_status():
    """Update all existing rider records with default online status fields."""
    
    # Set default values for all riders missing these fields
    default_values = {
        "is_online": False,
        "last_online": None,
        "last_offline": datetime.utcnow(),
        "last_activity": datetime.utcnow()
    }
    
    # Count total riders
    total_riders = riders_collection.count_documents({})
    
    # Count riders without online status fields
    missing_fields = riders_collection.count_documents({"is_online": {"$exists": False}})
    
    print(f"Found {total_riders} total riders, {missing_fields} without online status fields")
    
    # Only update riders that don't have these fields
    # Using update_many with $exists check to ensure we only modify riders missing the fields
    result = riders_collection.update_many(
        {"is_online": {"$exists": False}},
        {"$set": default_values}
    )
    
    print(f"Updated {result.modified_count} rider records with default online status")
    print(f"Skipped {total_riders - result.modified_count} riders that already had online status fields")
    
# Run the migration
if __name__ == "__main__":
    migrate_rider_online_status()