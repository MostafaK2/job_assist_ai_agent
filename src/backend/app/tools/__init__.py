from app.tools.profile import get_user_profile, get_preferences, get_work_history, get_username
from app.tools.jobs import search_jobs

# Tools get added here later, e.g. ALL_TOOLS = [get_user_profile, search_jobs, ...]
ALL_TOOLS = [get_user_profile, get_preferences, get_work_history, get_username, \
            search_jobs]