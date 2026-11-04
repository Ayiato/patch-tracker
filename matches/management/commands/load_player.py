"""Load a player's latest matches from the Riot API into the database.

Put this file at matches/management/commands/load_player.py
(create the packages matches/management and matches/management/commands first, like in gamedata).

Run it like:
    python manage.py load_player "Ayiato#EUNE" eun1
    python manage.py load_player "Ayiato#EUNE" eun1 --count 10
"""
from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from gamedata.models import Patch, Champion, Item
from matches.models import Player, Queue, Match, MatchPlayer, MatchPlayerItem
from matches.riot_api import get_account, get_match_ids, get_match


def find_patch(game_version):
    """'15.21.723.1234' (from a match) -> the Patch '15.21.1', or None if we don't have that patch.

    Matches only say the first two numbers reliably, so we look for a patch_id starting with '15.21.'.
    """
    major, minor = game_version.split(".")[:2]
    return Patch.objects.filter(patch_id__startswith=f"{major}.{minor}.").first()


def to_datetime(milliseconds):
    """Riot gives times as milliseconds since 1970 (e.g. 1761580800000) -> a real date with timezone."""
    return datetime.fromtimestamp(milliseconds / 1000, tz=dt_timezone.utc)


class Command(BaseCommand):
    help = "Load a player's latest matches from the Riot API."

    def add_arguments(self, parser):
        # These are the words you type after "python manage.py load_player".
        parser.add_argument("riot_id")  # "Ayiato#EUNE"
        parser.add_argument("server")  # "eun1"
        parser.add_argument("--count", type=int, default=50)  # optional, how many games

    def handle(self, *args, **options):
        if "#" not in options["riot_id"]:
            raise CommandError('Riot ID must look like "Name#TAG"')
        game_name, tag_line = options["riot_id"].split("#")
        server = options["server"].lower()

        account = get_account(game_name, tag_line, server)
        # Match.objects.all().delete()
        # MatchPlayerItem.objects.all().delete()
        # MatchPlayerItem.objects.all().delete()
        if account is None:
            raise CommandError(f"Riot ID {game_name}#{tag_line} not found")

        player, _ = Player.objects.update_or_create(
            player_id=account["puuid"],
            defaults={"player_username": account["gameName"],
                      "player_tag": account["tagLine"],
                      "player_region": server},
        )

        match_ids = get_match_ids(player.player_id, player.player_region, options["count"])
        matches_added_new = 0
        for match_id in match_ids:
            if MatchPlayer.objects.filter(matchplayer_match_id=match_id, matchplayer_player=player).exists():
                continue
            data = get_match(match_id)
            if data is None:
                continue
            info = data["info"]
            matches_added_new += 1
            match, _ = Match.objects.update_or_create(
                match_id=match_id,
                defaults={
                    "match_patch": find_patch(info["gameVersion"]),
                    "match_queue": Queue.objects.filter(queue_id=info["queueId"]).first(),
                    "match_duration": info["gameDuration"],
                    "match_start": to_datetime(info["gameStartTimestamp"]),
                },
            )

            p = None
            for participant in info["participants"]:
                if participant["puuid"] == player.player_id:
                    p = participant
                    break
            if p is None:
                continue

            mp, _ = MatchPlayer.objects.update_or_create(
                matchplayer_match=match,
                matchplayer_player=player,
                defaults={
                    "matchplayer_champion": Champion.objects.filter(champion_id=p["championId"]).first(),
                    "position": p["teamPosition"],
                    "win": p["win"],
                    "kills": p["kills"],
                    "deaths": p["deaths"],
                    "assists": p["assists"],
                    "cs": p["totalMinionsKilled"] + p["neutralMinionsKilled"],
                    "gold_earned": p["goldEarned"],
                    "damage_to_champions": p["totalDamageDealtToChampions"],
                    "vision_score": p["visionScore"],
                    "raw": p,
                },
            )

            for slot in range(7):
                item_id = p[f"item{slot}"]
                if item_id == 0:
                    continue
                MatchPlayerItem.objects.update_or_create(
                    matchplayeritem_matchplayer=mp,
                    slot=slot,
                    defaults={"matchplayeritem_item": Item.objects.filter(item_id=item_id).first()},
                )

            role_item = p.get("roleBoundItem", 0)
            if role_item:
                MatchPlayerItem.objects.update_or_create(
                    matchplayeritem_matchplayer=mp,
                    slot=7,
                    defaults={"matchplayeritem_item": Item.objects.filter(item_id=role_item).first()},
                )

            self.stdout.write(f"Saved {match_id}")

        player.player_last_updated = timezone.now()
        player.save()
        self.stdout.write(f"Done: {matches_added_new} new matches for "
                          f"{player.player_username}#{player.player_tag}")