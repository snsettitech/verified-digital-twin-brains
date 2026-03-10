#!/usr/bin/env python3
"""Generate a test JWT token for API testing"""
import os
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv('backend/.env')

# Get JWT secret
jwt_secret = os.getenv("JWT_SECRET", os.getenv("SUPABASE_JWT_SECRET", ""))
if not jwt_secret:
    print("Error: JWT_SECRET not found in .env")
    exit(1)

# Create a test token
payload = {
    "sub": "test-user-123",
    "email": "test@example.com",
    "iat": datetime.utcnow(),
    "exp": datetime.utcnow() + timedelta(hours=24),
    "aud": "authenticated",
    "role": "authenticated"
}

token = jwt.encode(payload, jwt_secret, algorithm="HS256")
print("Test Token generated:")
print(token)
print()
print("Export this for testing:")
print(f'export TEST_TOKEN="{token}"')
