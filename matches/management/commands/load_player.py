"""Management command that loads a player's recent matches, rank and masteries from the Riot API.

Usage:
    python manage.py load_player "Name#TAG" eun1 [--count 100]
"""
from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from gamedata.models import Patch, Champion, Item
from matches.models import Player, Queue, Match, MatchPlayer, MatchPlayerItem, PlayerMastery
from matches.riot_api import get_account, get_match_ids, get_match, get_summoner, get_masteries, get_solo_rank


def find_patch(game_version):
    """Find the stored Patch for a match's game version.

    Match versions look like '15.21.723.1234'; only major.minor is reliable, so the
    patch is matched on the '15.21.' prefix.

    Returns:
        Patch, or None when that patch is not loaded.
    """
    major, minor = game_version.split(".")[:2]
    return Patch.objects.filter(patch_id__startswith=f"{major}.{minor}.").first()


def to_datetime(milliseconds):
    """Convert a Riot timestamp in milliseconds to a timezone-aware UTC datetime."""
    return datetime.fromtimestamp(milliseconds / 1000, tz=dt_timezone.utc)


class Command(BaseCommand):
    """Load or update one player.

    Updates the account, rank, level and masteries, then stores every new match.
    Matches already stored for this player are skipped, so the command can run again
    safely (the profile's Refresh button uses it).
    """
    help = "Load a player's latest matches, rank and masteries from the Riot API."

    def add_arguments(self, parser):
        """Arguments: riot_id ("Name#TAG"), server (platform id) and --count (default 100)."""
        parser.add_argument("riot_id")
        parser.add_argument("server")
        parser.add_argument("--count", type=int, default=100)

    def handle(self, *args, **options):
        """Run the import.

        Raises:
            CommandError: the Riot ID is malformed or does not exist.
        """
        if "#" not in options["riot_id"]:
            raise CommandError('Riot ID must look like "Name#TAG"')
        game_name, tag_line = options["riot_id"].split("#")
        server = options["server"].lower()

        account = get_account(game_name, tag_line, server)
        if account is None:
            raise CommandError(f"Riot ID {game_name}#{tag_line} not found")
        puuid = account["puuid"]

        summoner = get_summoner(puuid, server)
        rank = get_solo_rank(puuid, server)
        masteries = get_masteries(puuid, server)

        champions = {c.champion_id: c for c in Champion.objects.all()}
        top_champion = champions.get(masteries[0]["championId"]) if masteries else None

        player, _ = Player.objects.update_or_create(
            player_id=puuid,
            defaults={
                "player_username": account["gameName"],
                "player_tag": account["tagLine"],
                "player_region": server,
                "player_icon": summoner["profileIconId"] if summoner else None,
                "player_level": summoner["summonerLevel"] if summoner else None,
                "player_top_champion": top_champion,
                "player_tier": rank["tier"] if rank else "",
                "player_division": rank["rank"] if rank else "",
                "player_lp": rank["leaguePoints"] if rank else None,
                "player_ranked_wins": rank["wins"] if rank else None,
                "player_ranked_losses": rank["losses"] if rank else None,
            },
        )

        PlayerMastery.objects.filter(mastery_player=player).delete()
        PlayerMastery.objects.bulk_create([
            PlayerMastery(
                mastery_player=player,
                mastery_champion=champions[m["championId"]],
                mastery_level=m["championLevel"],
                mastery_points=m["championPoints"],
            )
            for m in masteries
            if m["championId"] in champions
        ])

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
                    "matchplayer_champion": champions.get(p["championId"]),
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
