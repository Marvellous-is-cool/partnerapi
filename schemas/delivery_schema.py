from typing import Dict, Optional
from pydantic import BaseModel

class RiderSignup(BaseModel):
    firstname: str
    lastname: str
    gender: str
    email: str
    phone: str
    password: str
    gurantorname: str
    gurantorphonenumber: str
    accountbank: str
    accountname: str
    accountnumber: int
    bvn: int
    homeaddressdetails: str
    branding: str
    status: str


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
    riderid: Optional[str] = None
    accepted: bool = False
    rejected: bool = False
    additional_data: Optional[Dict] = None

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

    class Config:
        orm_mode = True