from app.tools.profile import PROFILE_TOOLS
from app.tools.search_jobs import search_jobs
from .job_details import JOB_DETAILS_TOOLS
from .apply import APPLY_TOOLS
from .fill import FILL_TOOLS

# Tools get added here later, e.g. ALL_TOOLS = [get_user_profile, search_jobs, ...]
ALL_TOOLS = [*PROFILE_TOOLS, search_jobs, *JOB_DETAILS_TOOLS, *APPLY_TOOLS, *FILL_TOOLS]
