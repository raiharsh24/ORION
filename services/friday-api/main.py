import os
import json
from dotenv import load_dotenv

# Resolve and load .env file from the local root
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

from app.main import app

def export_schema():
    openapi_schema = app.openapi()
    with open("openapi.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)
    print("OpenAPI schema exported successfully to openapi.json")
