"""Greenhouse public Job Board API. Fetching only: no database code here."""
import time

import requests

BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
TIMEOUT = 30


class BoardFetchError(Exception):
    pass


def fetch_board_jobs(board_token: str, retries: int = 2) -> list[dict]:
    """All jobs on a board, WITH full content, in ONE request (?content=true).

    Raises BoardFetchError if the request fails or the response looks incomplete.
    """
    url = f"{BASE_URL}/{board_token}/jobs"
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, params={"content": "true"}, timeout=TIMEOUT)
            if resp.status_code == 404:
                raise BoardFetchError(f"board '{board_token}' not found (404)")
            resp.raise_for_status()
            body = resp.json()
            jobs = body.get("jobs", [])
            total = (body.get("meta") or {}).get("total")
            if total is not None and total != len(jobs):
                raise BoardFetchError(f"got {len(jobs)} jobs but meta.total = {total}")
            return jobs
        except BoardFetchError:
            raise
        except (requests.RequestException, ValueError) as e:
            last_error = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise BoardFetchError(str(last_error))
