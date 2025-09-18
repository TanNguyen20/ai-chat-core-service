import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("API_KEY", "")
MODEL_NAME= os.environ.get("MODEL_NAME", "")
BASE_URL = os.environ.get("BASE_URL", "")