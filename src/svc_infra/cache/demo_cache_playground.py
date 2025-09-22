import asyncio
import os

from svc_infra.cache import TTL_LONG, init_cache, resource

init_cache(
    url="redis://default:BXytVfHOZOiWwAZXbThkxrZIqtxqETyR@shinkansen.proxy.rlwy.net:28540",
    prefix=os.getenv("CACHE_PREFIX", "svc"),
    version=os.getenv("CACHE_VERSION", "v1"),
)

# in-memory “DB”
_USERS: dict[int, dict] = {}


def _ensure_user(uid: int):
    _USERS.setdefault(uid, {"user_id": uid, "name": "John Doe"})


async def fetch_user(uid: int):
    _ensure_user(uid)
    await asyncio.sleep(0.02)
    return dict(_USERS[uid])


async def save_user(uid: int, data: dict):
    _ensure_user(uid)
    await asyncio.sleep(0.02)
    _USERS[uid].update(data)
    return dict(_USERS[uid])


# Resource sugar: automatically uses keys like "user:profile:{user_id}" and tag "user:{user_id}"
user = resource("user", "user_id")


@user.cache_read(suffix="profile", ttl=TTL_LONG)
async def get_user_profile(*, user_id: int):
    return await fetch_user(user_id)


@user.cache_write()  # no recache; built-in invalidation handles it
async def update_user_profile(*, user_id: int, data: dict):
    return await save_user(user_id, data)


async def main():
    uid = 123
    p1 = await get_user_profile(user_id=uid)
    print("Fetched profile:", p1)

    p2 = await update_user_profile(user_id=uid, data={"name": "New Name"})
    print("Updated profile:", p2)

    p3 = await get_user_profile(user_id=uid)
    print("Fetched profile after update:", p3)

    assert p3["name"] == "New Name"


if __name__ == "__main__":
    asyncio.run(main())
