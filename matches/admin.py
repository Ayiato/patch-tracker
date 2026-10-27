from django.contrib import admin
from .models import Player, Queue, Match, MatchPlayer, MatchPlayerItem

admin.site.register(Player)
admin.site.register(Queue)
admin.site.register(Match)
admin.site.register(MatchPlayer)
admin.site.register(MatchPlayerItem)