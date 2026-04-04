import os

GOOGLE_PLACES_API_KEY = os.getenv("PLACES_API_KEY")
GOOGLE_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
DATETIME_LIFF_URL = os.getenv("DATETIME_LIFF_URL", "")
DATETIME_LIFF_ID = os.getenv("DATETIME_LIFF_ID", "2009360861-udWtvLeU")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "")
