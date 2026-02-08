from jose import jwt
import base64
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TEST_ACCESS_TOKEN")
SECRET = os.getenv("JWT_SECRET")

if not TOKEN:
    raise SystemExit("Missing TEST_ACCESS_TOKEN in environment")
if not SECRET:
    raise SystemExit("Missing JWT_SECRET in environment")

print("Secret loaded:", "yes" if SECRET else "no")

try:
    print("\n--- Try Literal ---")
    jwt.decode(TOKEN, SECRET, algorithms=["HS256"], options={"verify_exp": False, "verify_aud": False})
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")

try:
    print("\n--- Try b64decode ---")
    decoded_secret = base64.b64decode(SECRET)
    jwt.decode(TOKEN, decoded_secret, algorithms=["HS256"], options={"verify_exp": False, "verify_aud": False})
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
