import os
from sqlalchemy import create_engine
import sqlalchemy_libsql

TURSO_SYNC_URL = "libsql://test.turso.io"
TURSO_AUTH_TOKEN = "fake_token"

try:
    engine = create_engine("sqlite+libsql:///local_edge_test.db", connect_args={"sync_url": TURSO_SYNC_URL, "auth_token": TURSO_AUTH_TOKEN})
    engine.connect()
    print("Success")
except Exception as e:
    print(f"Error: {e}")
