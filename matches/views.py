"""Views for the champion list and the champion detail page."""
from django.shortcuts import render, get_object_or_404

from gamedata.models import Ability, Champion, PatchChampion, Tag
from matches.player_views import newest_two_patches, champion_changes


def champions(request):
    """Render the champion list.

    URL: /champions/
    Query params:
        tag: class tag to filter by, e.g. "Mage".
        q: part of a champion name.
    Template: matches/champions.html

    Each champion gets a `status` ("buff", "nerf" or "") from the diff between the two
    newest patches. The diff is done for the whole list at once, not per champion.
    """
    tag = request.GET.get("tag", "")
    q = request.GET.get("q", "")

    champions = Champion.objects.order_by("champion_name").prefetch_related("champion_tags")
    if tag:
        champions = champions.filter(champion_tags__tag_name=tag)
    if q:
        champions = champions.filter(champion_name__icontains=q)

    new, old = newest_two_patches()

    champions = list(champions)
    changes = champion_changes([c.champion_id for c in champions], new, old)
    for champ in champions:
        champ.status = changes.get(champ.champion_id, {}).get("status", "")

    return render(request, "matches/champions.html", {
        "champions": champions,
        "tags": Tag.objects.order_by("tag_name"),
        "active_tag": tag,
        "q": q,
        "patch_name": ".".join(new.patch_id.split(".")[:2]),
    })


def champion_detail(request, name):
    """Render the page of one champion.

    URL: /champions/<name>/  (name is the Data Dragon internal name, e.g. "MonkeyKing")
    Template: matches/champion_detail.html

    Shows lore, abilities in in-game order (P, Q, W, E, R), base stats for the newest
    patch, skins and the stat change since the previous patch.

    Raises:
        Http404: no champion with that internal name.
    """
    champ = get_object_or_404(Champion, champion_internal_name=name)
    new, old = newest_two_patches()

    stats = PatchChampion.objects.filter(patchchampion_patch=new, patchchampion_champion=champ).first()

    order = "PQWER"
    abilities = sorted(Ability.objects.filter(ability_champion=champ),
                       key=lambda ab: order.index(ab.ability_type))

    change = champion_changes([champ.champion_id], new, old).get(champ.champion_id)

    return render(request, "matches/champion_detail.html", {
        "champ": champ,
        "stats": stats,
        "abilities": abilities,
        "skins": champ.skins.order_by("skin_num"),
        "change": change,
        "version": new.patch_id,
    })
