import os
import json
from datetime import datetime, timezone
import boto3
from supabase import create_client, Client

# --- Load Supabase secrets from AWS Secrets Manager ---
SECRET_NAME = "supabase_keys"
REGION_NAME = "ap-southeast-1"

client = boto3.client("secretsmanager", region_name=REGION_NAME)
response = client.get_secret_value(SecretId=SECRET_NAME)
secrets = json.loads(response["SecretString"])

SUPABASE_URL = secrets["SUPABASE_URL"]
SUPABASE_KEY = secrets["SUPABASE_KEY"]

# --- Initialize Supabase client ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

now = datetime.now(timezone.utc).isoformat()

# --- Upsert dummy row into directors ---
director_data = {
    "torn_user_id": 123456,
    "director_name": "Test Director",
    "company_id": 1111,
    "api_key": "DUMMY_KEY",
    "equity": 0,
    "voting_pct": 0,
    "updated_at": now
}

director_response = supabase.table("directors").upsert(
    director_data, on_conflict="torn_user_id"
).execute()
print("Directors upsert:", director_response)

# --- Upsert dummy row into education ---
education_data = {
    "torn_user_id": 123456,
    "course_name": "BUS2130",
    "completed": False,
    "updated_at": now
}

education_response = supabase.table("director_education").upsert(
    education_data, on_conflict="torn_user_id,course_name"
).execute()
print("Education upsert:", education_response)

# --- Upsert dummy row into stock_blocks ---
stock_data = {
    "torn_user_id": 123456,
    "block_name": "SYM",
    "has_block": False,
    "updated_at": now
}

stock_response = supabase.table("director_stock_blocks").upsert(
    stock_data, on_conflict="torn_user_id,block_name"
).execute()
print("Stock blocks upsert:", stock_response)


# Get the data

# --- Fetch all courses and stock blocks for the director ---
director_id = 123456

# Fetch courses
courses_response = supabase.table("director_education").select(
    "course_name, completed, created_at, updated_at"
).eq("torn_user_id", director_id).execute()

courses = courses_response.data
print(f"\nCourses:\n{courses}")
# for c in courses:
#     print(f"- {c['course_name']}: {'Completed' if c['completed'] else 'In Progress'}")

# Fetch stock blocks (only those they have)
stocks_response = supabase.table("director_stock_blocks").select(
    "block_name"
).eq("torn_user_id", director_id).eq("has_block", True).execute()

stocks = stocks_response.data
print("\nStock Blocks:")
for s in stocks:
    print(f"- {s['block_name']}")