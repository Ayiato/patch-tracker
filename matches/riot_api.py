
import time
from urllib.parse import quote

import requests
from django.conf import settings


SERVER_TO_REGION = {
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe", "me1": "europe",
    "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas",
    "kr": "asia", "jp1": "asia",
    "oc1": "sea", "ph2": "sea", "sg2": "sea", "th2": "sea", "tw2": "sea", "vn2": "sea",
}

session = requests.Session()


class RiotAPIError(Exception):
    """Raised when Riot answers with an error which can't be fixed by waiting."""


def get_region(server):
    return SERVER_TO_REGION[server.lower()]


def riot_get(url, params=None, retries=3):
    """
    - 200: returns the data
    - 404: returns None (no such player / match)
    - 429 (too many requests) or 5xx (Riot hiccup): waits, then tries again
    - anything else (401/403 = key problem): raises RiotAPIError
    """
    headers = {"X-Riot-Token": settings.RIOT_API_KEY}

    for attempt in range(retries + 1):
        try:
            response = session.get(url, headers=headers, params=params, timeout=10)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries:
                raise
            time.sleep(2)
            continue

        if response.status_code == 200:
            return response.json()

        if response.status_code == 404:
            return None

        if response.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            # Riot will tell us how many seconds to wait in the Retry-After header.
            wait = int(response.headers.get("Retry-After", 5))
            print(f"Riot said {response.status_code}, waiting {wait}s and retrying...")
            time.sleep(wait)
            continue

        raise RiotAPIError(f"Riot returned {response.status_code} for {url}: {response.text[:200]}")


def get_account(playergame_name, player_tag, server="euw1"):
    region = get_region(server)
    if region == "sea":
        region = "asia"  # the account API has no "sea" data center
    url = (f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
           f"{quote(playergame_name)}/{quote(player_tag)}")
    return riot_get(url)


def get_match_ids(puuid, server="euw1", count=20, queue_id=None, start=0):

    url = f"https://{get_region(server)}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": start, "count": count}
    if queue_id is not None:
        params["queue"] = queue_id
    return riot_get(url, params=params) or []


def get_match(match_id):
    server = match_id.split("_")[0]  # 'EUW1_7123456789' -> 'EUW1'
    url = f"https://{get_region(server)}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return riot_get(url)
