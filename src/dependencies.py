from fastapi import Depends
from .config import settings

def get_settings():
    return settings