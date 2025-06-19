import json
import os
import googlemaps
from functools import lru_cache
from typing import Dict, Optional, Tuple
from fastapi import BackgroundTasks, Depends, HTTPException

# 1. Set up Google Maps client
class GoogleMapsService:
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "AIzaSyC_Op-lSfNmmGPzKvsdImneVuL1jzYfNoM")
        self.gmaps_client = googlemaps.Client(key=self.api_key)
        self.cache = {}  # Simple in-memory cache
    
    @lru_cache(maxsize=1000)  # Cache up to 1000 addresses
    def geocode(self, address: str) -> Tuple[Optional[float], Optional[float]]:
        """Convert address to coordinates using Google Maps"""
        if not address:
            return None, None
            
        # Check cache first
        if address in self.cache:
            return self.cache[address]
            
        try:
            # Call Google Maps Geocoding API
            results = self.gmaps_client.geocode(address)
            
            if results:
                location = results[0]['geometry']['location']
                lat = location['lat']
                lng = location['lng']
                
                # Save to cache
                self.cache[address] = (lat, lng)
                return lat, lng
                
            return None, None
        except Exception as e:
            print(f"Google Maps geocoding error: {str(e)}")
            return None, None
        
# Create a singleton instance
gmaps_service = GoogleMapsService()

# 2. Add a function to get coordinates from a location object or string
def get_coordinates(location) -> Tuple[Optional[float], Optional[float]]:
    """Extract coordinates from location or geocode if needed"""
    if isinstance(location, dict):
        lat = location.get("latitude")
        lng = location.get("longitude")
        
        # If coordinates exist, return them
        if lat is not None and lng is not None:
            return lat, lng
        
        # If only address exists, geocode it
        address = location.get("address")
        if address:
            return gmaps_service.geocode(address)
    
    elif isinstance(location, str):
        # Try parsing as JSON first
        try:
            location_dict = json.loads(location)
            return get_coordinates(location_dict)
        except json.JSONDecodeError:
            # It's a plain text address, geocode it
            return gmaps_service.geocode(location)
    
    return None, None