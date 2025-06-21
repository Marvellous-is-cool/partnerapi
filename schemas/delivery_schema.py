from typing import Dict, Optional, Union
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, date, time


class RiderSignup(BaseModel):
    firstname: str
    lastname: str
    gender: str
    email: str
    phone: str
    password: str
    emergency_contact_name: str
    emergency_contact_phone: str
    accountbank: str
    accountname: str
    accountnumber: str
    # bvn: str
    homeaddressdetails: str
    branding: str
    vehicle_type: str
    email_notification: bool = True
    push_notification: bool = True
    earnings: int = 0
    status: str = "inactive"


class RiderSignIn(BaseModel):
    email: str
    password: str  


class UserSignup(BaseModel):
    firstname: str
    lastname: str
    email: str
    password: str
    phone: str

class DeliveryStatus(BaseModel):
    deliverystatus: str = "pending"  
    orderstatus: str = "pending"     
    riderid: Optional[str] = None
    transactioninfo: Dict[str, Any] = {
        "status": "pending",         
        "payment_method": None,
        "payment_id": None,
        "payment_date": None
    }

class BikeDeliveryRequest(BaseModel):
    user_id: str
    price: float
    distance: str
    startpoint: str
    endpoint: str
    stops: list
    vehicletype: str
    transactiontype: str
    packagesize: str
    deliveryspeed: str
    status: DeliveryStatus = DeliveryStatus()

class CarDeliveryRequest(BaseModel):
    user_id: str
    price: float
    distance: str
    startpoint: str
    endpoint: str
    stops: list
    vehicletype: str
    transactiontype: str
    status: DeliveryStatus = DeliveryStatus()
    deliveryspeed: str
class CarDeliveryRequest(BaseModel):
    user_id: str
    price: float
    distance: str
    startpoint: str
    endpoint: str
    stops: list
    vehicletype: str
    transactiontype: str
    status: DeliveryStatus = DeliveryStatus()
    deliveryspeed: str

class CreateDeliveryRequest(BaseModel):
    user_id: str
    price: int
    distance: str
    startpoint: str
    endpoint: str
    deliverytype: str  
    transactiontype: str  
    packagesize: str
    status: Dict[str, bool] = {"accepted": False, "rejected": False}


class TransactionUpdateRequest(BaseModel):
    transaction_type: Optional[str] = None  
    payment_status: Optional[str] = None  
    payment_reference: Optional[str] = None  
    payment_date: Optional[datetime] = None
    amount_paid: Optional[float] = None


class RiderLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    eta_minutes: Optional[int] = None


    class Config:
        from_attributes = True  # Instead of orm_mode = True
        
class LocationObject(BaseModel):
    address: str
    latitude: float
    longitude: float
        
class ScheduledDeliveryRequest(BaseModel):
    user_id: str
    price: float
    distance: str
    startpoint: Union[str, LocationObject]
    endpoint: Union[str, LocationObject]  
    stops: list
    vehicletype: str
    transactiontype: str
    packagesize: str
    deliveryspeed: str
    scheduled_date: date
    scheduled_time: time
    notes: Optional[str] = None
    status: DeliveryStatus = DeliveryStatus()
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "67d369e9823c6fb71a3b8676",
                "price": 2500.0,
                "distance": "5.3 km",
                "startpoint": {"address": "24b Omorinre Johnson Street, Lagos", "latitude": 6.4550, "longitude": 3.3920},
                "endpoint": {"address": "7 Oluwadare Street, Lagos", "latitude": 6.5100, "longitude": 3.3540},
                "stops": [],
                "vehicletype": "bike",
                "transactiontype": "card",
                "packagesize": "medium",
                "deliveryspeed": "standard",
                "scheduled_date": "2025-06-25",
                "scheduled_time": "14:30:00",
                "notes": "Call recipient before delivery"
            }
        }
        
class OfflineDeliveryRequest(BaseModel):
    user_id: str
    rider_id: str
    price: float
    distance: str
    startpoint: Union[str, LocationObject]
    endpoint: Union[str, LocationObject]
    vehicle_type: str
    transaction_type: str
    package_size: str
    delivery_speed: str
    completion_date: str  # Format: YYYY-MM-DD HH:MM
    payment_status: str
    payment_reference: Optional[str] = None
    admin_notes: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "67d369e9823c6fb71a3b8676",
                "rider_id": "67d369e9823c6fb71a3b8677",
                "price": 2500.0,
                "distance": "5.3 km",
                "startpoint": {"address": "24b Omorinre Johnson Street, Lagos", "latitude": 6.4550, "longitude": 3.3920},
                "endpoint": {"address": "7 Oluwadare Street, Lagos", "latitude": 6.5100, "longitude": 3.3540},
                "vehicle_type": "bike",
                "transaction_type": "cash",
                "package_size": "medium",
                "delivery_speed": "standard",
                "completion_date": "2025-06-20 15:30",
                "payment_status": "paid",
                "payment_reference": "CASH-PAYMENT-123",
                "admin_notes": "Customer called to verify delivery completed"
            }
        }