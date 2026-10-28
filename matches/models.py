from django.db import models

from gamedata.models import Patch, Champion, Item


# Create your models here.

class Player(models.Model):
    player_id = models.CharField(max_length=78, primary_key=True)
    player_username = models.CharField(max_length=16)
    player_tag = models.CharField(max_length=5)
    player_region = models.CharField(max_length=10)
    player_last_updated = models.DateTimeField(null = True, blank = True)

    def __str__(self):
        return f"{self.player_username}#{self.player_tag}"

class Queue(models.Model):
    queue_id = models.IntegerField(primary_key=True)
    queue_map = models.CharField(max_length=50)
    queue_description = models.CharField(max_length=100, blank = True, null = True)

    def __str__(self):
        return f"{self.queue_id} ; {self.queue_description}"

class Match(models.Model):
    match_id = models.CharField(max_length=30, primary_key=True)
    match_patch = models.ForeignKey(Patch, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches')
    match_queue = models.ForeignKey(Queue, on_delete = models.SET_NULL, related_name='matches', null = True, blank = True)
    match_duration = models.IntegerField()
    match_start = models.DateTimeField()

    def __str__(self):
        return f"{self.match_id}"

class MatchPlayer(models.Model):
    matchplayer_match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="match_players")
    matchplayer_player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="match_players")
    matchplayer_champion = models.ForeignKey(Champion, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.CharField(max_length=10, blank=True)
    win = models.BooleanField()
    kills = models.PositiveSmallIntegerField(default = 0)
    deaths = models.PositiveSmallIntegerField(default = 0)
    assists = models.PositiveSmallIntegerField(default = 0)
    cs = models.IntegerField(default = 0)
    gold_earned = models.IntegerField(default = 0)
    damage_to_champions = models.IntegerField(default = 0)
    vision_score = models.IntegerField(default = 0)
    raw = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["matchplayer_match", "matchplayer_player"],
                                    name="unique_match_player")]

    def __str__(self):
        return f"{self.matchplayer_match} ; {self.matchplayer_player}"


class MatchPlayerItem(models.Model):
    matchplayeritem_matchplayer = models.ForeignKey(MatchPlayer, on_delete=models.CASCADE, related_name="items")
    matchplayeritem_item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    slot = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["matchplayeritem_matchplayer", "slot"],
                                    name="unique_matchplayer_slot")]

    def __str__(self):
        return f"{self.matchplayeritem_matchplayer} ; {self.matchplayeritem_item} ; {self.slot}"