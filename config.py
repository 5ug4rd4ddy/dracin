import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    GOOGLE_DISCOVERY_URL = os.getenv("GOOGLE_DISCOVERY_URL")

    # Trakteer Configuration
    TRAKTEER_CREATOR_USERNAME = os.getenv('TRAKTEER_CREATOR_USERNAME')
    TRAKTEER_CREATOR_ID = os.getenv('TRAKTEER_CREATOR_ID')
    TRAKTEER_UNIT_ID = os.getenv('TRAKTEER_UNIT_ID')
    TRAKTEER_UNIT_PRICE = os.getenv('TRAKTEER_UNIT_PRICE')
    TRAKTEER_WEBHOOK_TOKEN = os.getenv('TRAKTEER_WEBHOOK_TOKEN')

    # Cache Configuration
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 300
