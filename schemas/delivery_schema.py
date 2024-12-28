from pydantic import BaseModel

class RiderSignup(BaseModel):
    firstname: str
    lastname: str
    gender: str
    email: str
    password: str
    gurantorname: str
    gurantorphonenumber: str
    accountbank: str
    accountname: str
    bvn: str
    homeaddressdetails: str


# Schema for Rider Sign-In
class RiderSignIn(BaseModel):
    email: str
    password: str  # Assuming a simple password field