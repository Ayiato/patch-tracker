"""Thin client for the Riot Games API (account-v1, match-v5, summoner-v4, league-v4, champion-mastery-v4).

The API key is read from settings.RIOT_API_KEY, which comes from the environment.
"""
import time
from urllib.parse import quote

import requests
from django.conf import settings

PLATFORM_TO_REGION = {
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe", "me1": "europe",
    "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas",
    "kr": "asia", "jp1": "asia",
    "oc1": "sea", "ph2": "sea", "sg2": "sea", "th2": "sea", "tw2": "sea", "vn2": "sea",
}

session = requests.Session()


class RiotAPIError(Exception):
    """Raised for Riot API errors that a retry will not fix, such as an invalid key."""


def get_region(platform):
    """Routing region for a platform id, e.g. 'euw1' -> 'europe'."""
    return PLATFORM_TO_REGION[platform.lower()]


def riot_get(url, params=None, retries=3):
    """GET a Riot endpoint and return the decoded JSON.

    Args:
        url: Full endpoint URL.
        params: Optional query parameters.
        retries: Extra attempts for rate limits, server errors and lost connections.

    Returns:
        The JSON body, or None on 404.

    Raises:
        RiotAPIError: any other error status, or 429/5xx after all retries.
    requests.ConnectionError, requests.Timeout: the connection still fails after all retries.

    On 429 and 5xx the client waits for the Retry-After header (5 s if missing).
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
            wait = int(response.headers.get("Retry-After", 5))
            print(f"Riot said {response.status_code}, waiting {wait}s and retrying...")
            time.sleep(wait)
            continue

        raise RiotAPIError(f"Riot returned {response.status_code} for {url}: {response.text[:200]}")


def get_account(game_name, tag_line, platform):
    """Look up a Riot ID.

    Returns:
        Dict with "puuid", "gameName" and "tagLine", or None if it does not exist.
    """
    region = get_region(platform)
    if region == "sea":
        region = "asia"
    url = (f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
           f"{quote(game_name)}/{quote(tag_line)}")
    return riot_get(url)


def get_match_ids(puuid, platform, count=20, queue=None, start=0):
    """Latest match ids for a player, newest first.

    Args:
        puuid: Player id.
        platform: Platform id, used to pick the routing region.
        count: Up to 100 per call.
        queue: Optional queue id filter, e.g. 420 for ranked solo.
        start: Offset for paging.

    Returns:
        List of match ids (empty if none).
    """
    url = f"https://{get_region(platform)}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"start": start, "count": count}
    if queue is not None:
        params["queue"] = queue
    return riot_get(url, params=params) or []


def get_match(match_id):
    """Full match data ("metadata" and "info") for one match id, or None."""
    platform = match_id.split("_")[0]
    url = f"https://{get_region(platform)}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return riot_get(url)


def get_summoner(puuid, platform):
    """Summoner data for a puuid (profile icon id, level), or None."""
    url = f"https://{platform.lower()}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    return riot_get(url)


def get_masteries(puuid, platform):
    """Champion masteries for a player, highest points first (empty list if none)."""
    url = (f"https://{platform.lower()}.api.riotgames.com/lol/champion-mastery/v4/"
           f"champion-masteries/by-puuid/{puuid}")
    return riot_get(url) or []


def get_solo_rank(puuid, platform):
    """Ranked Solo/Duo entry (tier, rank, LP, wins, losses), or None when unranked."""
    url = f"https://{platform.lower()}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    for entry in riot_get(url) or []:
        if entry["queueType"] == "RANKED_SOLO_5x5":
            return entry
    return None
