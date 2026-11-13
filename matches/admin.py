"""Registers the matches models in the Django admin site."""

from django.contrib import admin

from .models import Player, Queue, Match, MatchPlayer, MatchPlayerItem, PlayerMastery

admin.site.register(Player)
admin.site.register(Queue)
admin.site.register(Match)
admin.site.register(MatchPlayer)
admin.site.register(MatchPlayerItem)
admin.site.register(PlayerMastery)
