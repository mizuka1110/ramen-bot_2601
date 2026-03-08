import os

GOOGLE_PLACES_API_KEY = os.getenv("PLACES_API_KEY")
GOOGLE_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")