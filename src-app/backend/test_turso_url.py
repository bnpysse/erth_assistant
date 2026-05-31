import os
import sqlalchemy.engine.url as url
u = url.make_url("sqlite+libsql:///local.db?syncUrl=http://test&authToken=123")
print(u)
