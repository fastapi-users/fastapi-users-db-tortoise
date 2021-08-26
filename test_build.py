# flake8: noqa
import sys

try:
    from fastapi_users_db_tortoise import TortoiseUserDatabase
except:
    sys.exit(1)

sys.exit(0)
