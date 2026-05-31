import os
from sqlalchemy import create_engine
import sqlalchemy_libsql

try:
    engine = create_engine("sqlite+libsql:///local_edge_test2.db")
    engine.connect()
    print("Success")
except Exception as e:
    print(f"Error: {e}")
