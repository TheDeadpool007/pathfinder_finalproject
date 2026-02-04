"""
OpenRouteService API wrapper for route distance calculations.

API Documentation: https://openrouteservice.org/dev/#/api-docs
"""

import os
import logging
import requests
from typing import Tuple
from math import radians, sin, cos, sqrt, atan2

logger = logging.getLogger(__name__)


class OpenRouteServiceAPI:
    """Wrapper for OpenRouteService API to calculate distances."""
    
    BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
    
    def __init__(self):
        """Initialize with API key from environment."""
        self.api_key = os.getenv("OPENROUTESERVICE_API_KEY", "")
        if not self.api_key:
            logger.warning("OPENROUTESERVICE_API_KEY not set - using haversine fallback")
    
    def get_distance(self, start: Tuple[float, float], end: Tuple[float, float]) -> float:
        """
        Calculate distance between two points.
        
        Args:
            start: (longitude, latitude) tuple
            end: (longitude, latitude) tuple
        
        Returns:
            Distance in kilometers
        """
        if not self.api_key:
            return self._haversine_distance(start, end)
        
        try:
            url = self.BASE_URL
            headers = {
                'Authorization': self.api_key,
                'Content-Type': 'application/json'
            }
            
            body = {
                "coordinates": [
                    [start[0], start[1]],
                    [end[0], end[1]]
                ]
            }
            
            response = requests.post(url, json=body, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            distance_meters = data['routes'][0]['summary']['distance']
            distance_km = distance_meters / 1000
            
            return round(distance_km, 2)
            
        except Exception as e:
            logger.warning(f"API error, using haversine: {e}")
            return self._haversine_distance(start, end)
    
    def _haversine_distance(self, start: Tuple[float, float], end: Tuple[float, float]) -> float:
        """
        Calculate great-circle distance using Haversine formula.
        
        Args:
            start: (longitude, latitude) tuple
            end: (longitude, latitude) tuple
        
        Returns:
            Distance in kilometers
        """
        lon1, lat1 = start
        lon2, lat2 = end
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        # Earth radius in km
        radius = 6371.0
        distance = radius * c
        
        return round(distance, 2)
