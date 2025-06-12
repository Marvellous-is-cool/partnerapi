from typing import Dict, Optional
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


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
        orm_mode = True