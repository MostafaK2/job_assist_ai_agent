"""get_user_profile: tells the agent who it's helping.

For now the profile comes from a local JSON file of FAKE data (data/profile.json).
Later this reads the signed-in user's profile from Postgres instead.
"""
import json
from functools import lru_cache
from pathlib import Path

from langchain.tools import tool

from app.config import PROFILE_PATH

# Until login exists, every chat belongs to this one development user.
DEV_USER_ID = "dev-user-1"

# Never sent to the model. Form-filling reads these straight from the file later, so the
# model doesn't need them, and they can't leak into a reply, a summary or a cover letter.
PRIVATE_IDENTITY_FIELDS = {"email", "phone", "dob"}
PRIVATE_ADDRESS_FIELDS = {"address_line_1", "address_line_2", "address_line_3", "zip_code"}


@lru_cache(maxsize=1)
def _load_profiles() -> dict[str, dict]:
    data = json.loads(Path(PROFILE_PATH).read_text(encoding="utf-8"))
    return {p["user_id"]: p for p in data["profiles"]}


def load_full_profile(user_id: str = DEV_USER_ID) -> dict:
    """The complete profile, for server-side code only (e.g. filling forms). Not a tool."""
    profile = _load_profiles().get(user_id)
    if profile is None:
        raise LookupError(f"No profile for user {user_id!r} in {PROFILE_PATH}")
    return profile


def profile_for_agent(profile: dict) -> dict:
    """The profile with private details removed or replaced by "on file" flags."""
    identity = {k: v for k, v in profile["identity"].items() if k not in PRIVATE_IDENTITY_FIELDS}
    address = {k: v for k, v in profile["address"].items() if k not in PRIVATE_ADDRESS_FIELDS}
    return {
        **{k: v for k, v in profile.items()
           if k not in {"user_id", "identity", "address", "voluntary_self_identification"}},
        "identity": identity,
        "location": address,  # city, state, country only
        "contact_details_on_file": {
            "email": bool(profile["identity"].get("email")),
            "phone": bool(profile["identity"].get("phone")),
            "street_address": bool(profile["address"].get("address_line_1")),
        },
        # Demographic answers stay private: the agent only learns whether an answer exists.
        "self_identification_answers_on_file": sorted(
            k for k, v in (profile.get("voluntary_self_identification") or {}).items() if v
        ),
    }

@tool
def get_preferences() -> dict:
    """Get the job preferences of the user you are helping."""
    try:
        profile = load_full_profile()
        return profile.get("preferences", {})
    except (OSError, LookupError, KeyError, json.JSONDecodeError) as error:
        print(f"get_preferences failed: {error!r}")
        return {"error": "The user's job preferences couldn't be loaded. Tell the user and don't guess."}


@tool
def get_username() -> str:
    """Get the name of the user. This would return the first name and last name of the user."""
    try:
        profile = load_full_profile()["identity"]
        return profile.get("first_name", "") + " " + profile.get("last_name", "")
    except (OSError, LookupError, KeyError, json.JSONDecodeError) as error:
        print(f"get_username failed: {error!r}")
        return ""

@tool
def get_work_history() -> list:
    """Get the work history of the user you are helping."""
    try:
        profile = load_full_profile()
        return profile.get("work_history", [])
    except (OSError, LookupError, KeyError, json.JSONDecodeError) as error:
        print(f"get_work_history failed: {error!r}")
        return {"error": "The user's work history couldn't be loaded. Tell the user and don't guess."}

@tool
def get_user_profile() -> dict:
    """Gets the entire profile of the user you are helping: name, location, work history, education,
    skills, work authorization, job preferences and standard application answers.
    """
    try:
        return profile_for_agent(load_full_profile())
    except (OSError, LookupError, KeyError, json.JSONDecodeError) as error:
        # Tell the model plainly instead of crashing the chat; the details go to the server log.
        print(f"get_user_profile failed: {error!r}")
        return {"error": "The user's profile couldn't be loaded. Tell the user and don't guess."}


PROFILE_TOOLS = [get_user_profile, get_preferences, get_work_history, get_username]