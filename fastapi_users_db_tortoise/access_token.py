from datetime import datetime
from typing import Generic, Optional, Type, cast

from fastapi_users.authentication.strategy.db import A, AccessTokenDatabase
from tortoise import fields, models
from tortoise.contrib.pydantic import PydanticModel


class TortoiseBaseAccessTokenModel(models.Model):
    token = fields.CharField(pk=True, max_length=43)
    created_at = fields.DatetimeField(
        null=False,
        auto_now_add=True,
    )


class TortoiseAccessTokenDatabase(AccessTokenDatabase, Generic[A]):
    """
    Access token database adapter for Tortoise ORM.

    :param access_token_model: Pydantic model of a DB representation of an access token.
    :param model: Tortoise ORM model.
    """

    def __init__(
        self, access_token_model: Type[A], model: Type[TortoiseBaseAccessTokenModel]
    ):
        self.access_token_model = access_token_model
        self.model = model

    async def get_by_token(
        self, token: str, max_age: Optional[datetime] = None
    ) -> Optional[A]:
        query = self.model.filter(token=token)
        if max_age is not None:
            query = query.filter(created_at__gte=max_age)

        access_token = await query.first()
        if access_token is not None:
            return await self._model_to_pydantic(access_token)
        return None

    async def create(self, access_token: A) -> A:
        model = self.model(**access_token.dict())
        await model.save()
        await model.refresh_from_db()
        return await self._model_to_pydantic(model)

    async def update(self, access_token: A) -> A:
        model = await self.model.get(token=access_token.token)
        for field, value in access_token.dict().items():
            setattr(model, field, value)
        await model.save()
        return await self._model_to_pydantic(model)

    async def delete(self, access_token: A) -> None:
        await self.model.filter(token=access_token.token).delete()

    async def _model_to_pydantic(self, model: TortoiseBaseAccessTokenModel) -> A:
        pydantic_access_token = await cast(
            PydanticModel, self.access_token_model
        ).from_tortoise_orm(model)
        return cast(A, pydantic_access_token)
