import asyncio
import os

from svc_infra.cache import init_cache, resource
from svc_infra.cache.ttl import TTL_LONG

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
    if uid not in _USERS:
        raise KeyError(f"User {uid} not found")
    await asyncio.sleep(0.02)
    return dict(_USERS[uid])


async def save_user(uid: int, data: dict):
    _ensure_user(uid)
    await asyncio.sleep(0.02)
    _USERS[uid].update(data)
    return dict(_USERS[uid])


async def delete_user(uid: int):
    await asyncio.sleep(0.02)
    if uid in _USERS:
        del _USERS[uid]
        return True
    return False


# Resource sugar: automatically uses keys like "user:profile:{user_id}" and tag "user:{user_id}"
user = resource("user", "user_id")


@user.cache_read(suffix="profile", ttl=TTL_LONG)
async def get_user_profile(*, user_id: int):
    return await fetch_user(user_id)


@user.cache_write()  # no recache; built-in invalidation handles it
async def update_user_profile(*, user_id: int, data: dict):
    return await save_user(user_id, data)


@user.cache_write()  # invalidates cache when user is deleted
async def delete_user_profile(*, user_id: int):
    return await delete_user(user_id)


async def main():
    uid = 123

    # First, ensure the user exists for the demo
    _ensure_user(uid)

    p1 = await get_user_profile(user_id=uid)
    print("Fetched profile:", p1)

    p2 = await update_user_profile(user_id=uid, data={"name": "New Name"})
    print("Updated profile:", p2)

    p3 = await get_user_profile(user_id=uid)
    print("Fetched profile after update:", p3)

    assert p3["name"] == "New Name"

    # Delete example
    deleted = await delete_user_profile(user_id=uid)
    print("Deleted user:", deleted)

    # Try to fetch deleted user - should hit DB and get KeyError
    try:
        p4 = await get_user_profile(user_id=uid)
        print("❌ ERROR: Fetched profile after delete:", p4)
        print("This shouldn't happen - user should be deleted!")
    except KeyError as e:
        print(f"✅ User successfully deleted - {e}")
        print("Cache invalidation and deletion worked perfectly!")


if __name__ == "__main__":
    asyncio.run(main())
