import re

from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect

from gamedata.models import Patch, Champion, Tag, PatchChampion, Ability, PatchItem
from .models import Player, MatchPlayer
from .riot_api import get_account


STAT_NAMES = {
    "FlatPhysicalDamageMod": ("Attack damage", False),
    "FlatMagicDamageMod": ("Ability power", False),
    "FlatHPPoolMod": ("Health", False),
    "FlatMPPoolMod": ("Mana", False),
    "FlatArmorMod": ("Armor", False),
    "FlatSpellBlockMod": ("Magic resist", False),
    "PercentAttackSpeedMod": ("Attack speed", True),
    "FlatCritChanceMod": ("Crit chance", True),
    "PercentLifeStealMod": ("Life steal", True),
    "FlatMovementSpeedMod": ("Move speed", False),
    "PercentMovementSpeedMod": ("Move speed", True),
    "FlatHPRegenMod": ("Health regen", False),
}

STAT_CHIPS = [
    ("FlatPhysicalDamageMod", "Attack damage"),
    ("FlatMagicDamageMod", "Ability power"),
    ("FlatHPPoolMod", "Health"),
    ("FlatArmorMod", "Armor"),
    ("FlatSpellBlockMod", "Magic resist"),
    ("PercentAttackSpeedMod", "Attack speed"),
    ("FlatCritChanceMod", "Crit"),
]

def home(request):
    riot_id = request.GET.get("riot_id", "").strip()
    server = request.GET.get("server", "eun1")
    if "#" in riot_id:
        name, tag = riot_id.split("#", 1)
        return redirect("player_games", server=server, name=name, tag=tag)

    latest = Patch.objects.order_by("-patch_order").first()
    version = latest.patch_id
    patch_name = ".".join(version.split(".")[:2])
    map_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/map/map11.png"
    featured = []

    return render(request, "matches/home.html", {
        "patch_name": patch_name,
        "map_url": map_url,
        "featured": featured,
    })

def player_games(request, server, name, tag):
    account = get_account(name, tag, server)
    if account is None:
        raise Http404("Riot ID not found")
    player = get_object_or_404(Player, player_id=account["puuid"])
    games = (MatchPlayer.objects
             .filter(matchplayer_player=player)
             .select_related("matchplayer_match", "matchplayer_champion")
             .order_by("-matchplayer_match__match_start"))
    return render(request, "matches/player_games.html", {"player": player, "games": games})

def champions(request):
    tag = request.GET.get("tag", "")
    q = request.GET.get("q", "")

    champions = Champion.objects.order_by("champion_name").prefetch_related("champion_tags")

    if tag:
        champions = champions.filter(champion_tags__tag_name=tag)

    if q:
        champions = champions.filter(champion_name__icontains=q)
    latest = Patch.objects.order_by("-patch_order").first()
    patch_name = ".".join(latest.patch_id.split(".")[:2])

    return render(request, "matches/champions.html", {
        "champions": champions,
        "tags": Tag.objects.order_by("tag_name"),
        "active_tag": tag,
        "q": q,
        "patch_name": patch_name,
    })

def champion_detail(request, name):
    champ = get_object_or_404(Champion, champion_internal_name=name)
    latest = Patch.objects.order_by("-patch_order").first()

    stats = PatchChampion.objects.get(
        patchchampion_patch=latest,
        patchchampion_champion=champ,
    )

    abilities = Ability.objects.filter(ability_champion=champ)

    order = "PQWER"
    abilities = sorted(abilities, key=lambda ab: order.index(ab.ability_type))

    return render(request, "matches/champion_detail.html", {
        "champ": champ,
        "stats": stats,
        "abilities": abilities,
        "version": latest.patch_id,
        "skins": champ.skins.all(),
    })

# Data Dragon's stat names -> what we show on the page.
# True = the value is a fraction (0.25) that we show as a percent (25%).
STAT_NAMES = {
    "FlatPhysicalDamageMod": ("Attack damage", False),
    "FlatMagicDamageMod": ("Ability power", False),
    "FlatHPPoolMod": ("Health", False),
    "FlatMPPoolMod": ("Mana", False),
    "FlatArmorMod": ("Armor", False),
    "FlatSpellBlockMod": ("Magic resist", False),
    "PercentAttackSpeedMod": ("Attack speed", True),
    "FlatCritChanceMod": ("Crit chance", True),
    "PercentLifeStealMod": ("Life steal", True),
    "FlatMovementSpeedMod": ("Move speed", False),
    "PercentMovementSpeedMod": ("Move speed", True),
    "FlatHPRegenMod": ("Health regen", False),
}

# the filter chips: (Data Dragon stat key, label)
STAT_CHIPS = [
    ("FlatPhysicalDamageMod", "Attack damage"),
    ("FlatMagicDamageMod", "Ability power"),
    ("FlatHPPoolMod", "Health"),
    ("FlatArmorMod", "Armor"),
    ("FlatSpellBlockMod", "Magic resist"),
    ("PercentAttackSpeedMod", "Attack speed"),
    ("FlatCritChanceMod", "Crit"),
]


def items(request):
    latest = Patch.objects.order_by("-patch_order").first()
    q = request.GET.get("q", "")
    stat = request.GET.get("stat", "")

    items = (PatchItem.objects
             .filter(patchitem_patch=latest)
             .select_related("patchitem_item")
             .order_by("patchitem_item__item_name"))

    if q:
        items = items.filter(patchitem_item__item_name__icontains=q)
    if stat:
        items = items.filter(stats__has_key=stat)

    for pi in items:
        pi.stat_list = []
        for key, value in pi.stats.items():
            label, percent = STAT_NAMES.get(key, (key, False))
            if percent:
                pi.stat_list.append((label, f"{round(value * 100)}%"))
            else:
                pi.stat_list.append((label, f"{value:g}"))

        pi.clean_description = " ".join(re.sub(r"<[^>]+>", " ", pi.description).split())

    return render(request, "matches/items.html", {
        "items": items,
        "patch_name": latest.patch_id,
        "version": latest.patch_id,
        "q": q,
        "active_stat": stat,
        "stat_chips": STAT_CHIPS,
    })