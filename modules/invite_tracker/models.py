import datetime
import time

from core.models.base import MongoModel


class Invite(MongoModel):
    guild_id: int
    code: str
    inviter_id: int
    uses : int



class InviteJoins(MongoModel):
    guild_id: int
    user_id: int
    inviter_id: int
    timestamp: datetime.datetime = datetime.datetime.now()