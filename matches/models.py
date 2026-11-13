"""Models for players, their matches and champion mastery."""

from django.db import models

from gamedata.models import Patch, Champion, Item


class Player(models.Model):
    """A Riot account, keyed by puuid.

    Name and tag are stored for display only, because Riot IDs can change. Rank and
    level are copied from the API on every load.
    """
    player_id = models.CharField(max_length=78, primary_key=True)
    player_username = models.CharField(max_length=16)
    player_tag = models.CharField(max_length=5)
    player_region = models.CharField(max_length=10)
    player_last_updated = models.DateTimeField(null=True, blank=True)

    player_icon = models.IntegerField(null=True, blank=True)
    player_level = models.IntegerField(null=True, blank=True)
    player_top_champion = models.ForeignKey(Champion, on_delete=models.SET_NULL,
                                            null=True, blank=True, related_name="+")
    player_background = models.ForeignKey("gamedata.Skin", on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name="+")

    player_tier = models.CharField(max_length=20, blank=True)
    player_division = models.CharField(max_length=5, blank=True)
    player_lp = models.IntegerField(null=True, blank=True)
    player_ranked_wins = models.IntegerField(null=True, blank=True)
    player_ranked_losses = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.player_username}#{self.player_tag}"


class Queue(models.Model):
    """Queue lookup (ranked solo, ARAM, ...), loaded from Riot's static queues.json."""
    queue_id = models.IntegerField(primary_key=True)
    queue_map = models.CharField(max_length=50)
    queue_description = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.queue_id} ; {self.queue_description}"


class Match(models.Model):
    """One game. Linked to the patch it was played on when that patch is loaded."""
    match_id = models.CharField(max_length=30, primary_key=True)
    match_patch = models.ForeignKey(Patch, on_delete=models.SET_NULL, null=True, blank=True, related_name="matches")
    match_queue = models.ForeignKey(Queue, on_delete=models.SET_NULL, related_name="matches", null=True, blank=True)
    match_duration = models.IntegerField()
    match_start = models.DateTimeField()

    def __str__(self):
        return f"{self.match_id}"


class MatchPlayerQuerySet(models.QuerySet):
    """Query helpers for MatchPlayer."""
    def counted(self):
        """Games that count for statistics. Remakes (early surrender) are left out.

        Games without the field in `raw` are kept.
        """
        return self.filter(models.Q(raw__gameEndedInEarlySurrender=False)
                           | models.Q(raw__gameEndedInEarlySurrender__isnull=True))


class MatchPlayerItemQuerySet(models.QuerySet):
    """Query helpers for MatchPlayerItem."""
    def counted(self):
        """Items from games that count for statistics. Items from remakes are left out."""
        return self.filter(models.Q(matchplayeritem_matchplayer__raw__gameEndedInEarlySurrender=False)
                           | models.Q(matchplayeritem_matchplayer__raw__gameEndedInEarlySurrender__isnull=True))


class MatchPlayer(models.Model):
    """A tracked player's row in one match.

    The columns are the stats the site queries; the full participant payload from
    match-v5 (140+ fields) is kept in `raw`.
    """
    matchplayer_match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="match_players")
    matchplayer_player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="match_players")
    matchplayer_champion = models.ForeignKey(Champion, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.CharField(max_length=10, blank=True)
    win = models.BooleanField()
    kills = models.PositiveSmallIntegerField(default=0)
    deaths = models.PositiveSmallIntegerField(default=0)
    assists = models.PositiveSmallIntegerField(default=0)
    cs = models.IntegerField(default=0)
    gold_earned = models.IntegerField(default=0)
    damage_to_champions = models.IntegerField(default=0)
    vision_score = models.IntegerField(default=0)
    raw = models.JSONField(default=dict)

    objects = MatchPlayerQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["matchplayer_match", "matchplayer_player"],
                                    name="unique_match_player")]

    def __str__(self):
        return f"{self.matchplayer_match} ; {self.matchplayer_player}"

    @property
    def is_remake(self):
        """True when the game ended in an early surrender vote (a remake)."""
        return bool(self.raw.get("gameEndedInEarlySurrender"))


class MatchPlayerItem(models.Model):
    """Item in one inventory slot at the end of a game (slot 6 is the trinket)."""
    matchplayeritem_matchplayer = models.ForeignKey(MatchPlayer, on_delete=models.CASCADE, related_name="items")
    matchplayeritem_item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    slot = models.PositiveSmallIntegerField()

    objects = MatchPlayerItemQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["matchplayeritem_matchplayer", "slot"],
                                    name="unique_matchplayer_slot")]

    def __str__(self):
        return f"{self.matchplayeritem_matchplayer} ; {self.matchplayeritem_item} ; {self.slot}"


class PlayerMastery(models.Model):
    """Champion mastery level and points for a player."""
    mastery_player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="masteries")
    mastery_champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name="+")
    mastery_level = models.IntegerField()
    mastery_points = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["mastery_player", "mastery_champion"],
                                    name="unique_player_champion_mastery")]

    def __str__(self):
        return f"{self.mastery_player} ; {self.mastery_champion} ; {self.mastery_level}"
