from django.urls import path
from . import views

urlpatterns = [
    path("player/<str:server>/<str:name>/<str:tag>/", views.player_games, name="player_games"),
    path("", views.home, name="home"),
    path("champions/", views.champions, name="champions"),
    path("champions/<str:name>/", views.champion_detail, name="champion_detail"),
    path("items/", views.items, name="items"),
]

