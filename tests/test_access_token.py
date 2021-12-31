import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from fastapi_users.authentication.strategy.db.models import BaseAccessToken
from pydantic import UUID4
from tortoise import Tortoise, fields
from tortoise.contrib.pydantic import PydanticModel
from tortoise.exceptions import IntegrityError

from fastapi_users_db_tortoise import TortoiseBaseUserModel
from fastapi_users_db_tortoise.access_token import (
    TortoiseAccessTokenDatabase,
    TortoiseBaseAccessTokenModel,
)
from tests.conftest import UserDB as BaseUserDB


class UserModel(TortoiseBaseUserModel):
    pass


class UserDB(BaseUserDB, PydanticModel):
    class Config:
        orm_mode = True
        orig_model = UserModel


class AccessTokenModel(TortoiseBaseAccessTokenModel):
    user = fields.ForeignKeyField("models.UserModel", related_name="access_tokens")


class AccessToken(BaseAccessToken, PydanticModel):
    class Config:
        orm_mode = True
        orig_model = AccessTokenModel


@pytest.fixture
def user_id() -> UUID4:
    return uuid.uuid4()


@pytest.fixture
async def tortoise_access_token_db(
    user_id: UUID4,
) -> AsyncGenerator[TortoiseAccessTokenDatabase, None]:
    DATABASE_URL = "sqlite://./test-tortoise-access-token.db"

    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["tests.test_access_token"]},
    )
    await Tortoise.generate_schemas()

    user = UserModel(
        id=user_id,
        email="lancelot@camelot.bt",
        hashed_password="guinevere",
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    await user.save()

    yield TortoiseAccessTokenDatabase(AccessToken, AccessTokenModel)

    await AccessTokenModel.all().delete()
    await UserModel.all().delete()
    await Tortoise.close_connections()


@pytest.mark.asyncio
@pytest.mark.db
async def test_queries(
    tortoise_access_token_db: TortoiseAccessTokenDatabase[AccessToken],
    user_id: UUID4,
):
    access_token = AccessToken(token="TOKEN", user_id=user_id)

    # Create
    access_token_db = await tortoise_access_token_db.create(access_token)
    assert access_token_db.token == "TOKEN"
    assert access_token_db.user_id == user_id

    # Update
    access_token_db.created_at = datetime.now(timezone.utc)
    await tortoise_access_token_db.update(access_token_db)

    # Get by token
    access_token_by_token = await tortoise_access_token_db.get_by_token(
        access_token_db.token
    )
    assert access_token_by_token is not None

    # Get by token expired
    access_token_by_token = await tortoise_access_token_db.get_by_token(
        access_token_db.token, max_age=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    assert access_token_by_token is None

    # Get by token not expired
    access_token_by_token = await tortoise_access_token_db.get_by_token(
        access_token_db.token, max_age=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    assert access_token_by_token is not None

    # Get by token unknown
    access_token_by_token = await tortoise_access_token_db.get_by_token(
        "NOT_EXISTING_TOKEN"
    )
    assert access_token_by_token is None

    # Exception when inserting existing token
    with pytest.raises(IntegrityError):
        await tortoise_access_token_db.create(access_token_db)

    # Delete token
    await tortoise_access_token_db.delete(access_token_db)
    deleted_access_token = await tortoise_access_token_db.get_by_token(
        access_token_db.token
    )
    assert deleted_access_token is None
