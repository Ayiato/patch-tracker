"""URL routes for every page of PatchTracker.

Player pages use the Riot ID in the path (server, name, tag) so links can be shared.
"""

from django.urls import path

from . import views, player_views, coach_views

urlpatterns = [
    path("", coach_views.home, name="home"),
    path("champions/", views.champions, name="champions"),
    path("champions/<str:name>/", views.champion_detail, name="champion_detail"),
    path("items/", player_views.items, name="items"),
    path("coach/", coach_views.coach_start, name="coach"),
    path("patch-notes/", coach_views.patch_notes, name="patch_notes"),
    path("player/<str:server>/<str:name>/<str:tag>/", player_views.player_games, name="player_games"),
    path("player/<str:server>/<str:name>/<str:tag>/refresh/", player_views.refresh_player, name="refresh_player"),
    path("player/<str:server>/<str:name>/<str:tag>/background/", player_views.choose_background, name="choose_background"),
    path("player/<str:server>/<str:name>/<str:tag>/champions/", player_views.player_champion_search, name="player_champion_search"),
    path("player/<str:server>/<str:name>/<str:tag>/champion/<str:champion>/", player_views.player_champion, name="player_champion"),
    path("player/<str:server>/<str:name>/<str:tag>/coach/", coach_views.coach_chat, name="coach_chat"),
    path("player/<str:server>/<str:name>/<str:tag>/coach/ask/", coach_views.coach_ask, name="coach_ask"),
]
