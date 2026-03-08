from pydantic import BaseModel
from typing import Dict

class PreferencesRequest(BaseModel):
    user_id: str
    weights: Dict[str, float]