"""Views for the home page, patch notes and the AI coach."""
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from gamedata.models import Champion, Item, Patch
from matches.models import Player
from matches.coach import ask_coach, DEMO_MODE
from matches.player_views import find_player, newest_two_patches, champion_changes, item_changes

MAX_TURNS = 20
SUGGESTIONS = [
    "What should I play this patch?",
    "Why do I lose games?",
    "Which of my champions got buffed or nerfed?",
    "What should I build on my main?",
]

DDRAGON = "https://ddragon.leagueoflegends.com/cdn"


def biggest_stat_change(lines):
    """Split a change line into the difference and the stat name.

    Args:
        lines: Change lines from champion_changes or item_changes.

    Returns:
        Tuple (difference, label), e.g. ('+3', 'Attack damage') for
        'Attack damage 53 → 56'. Non-numeric values return the new value as text.
    """
    label, values = lines[0].rsplit(" ", 3)[0], lines[0].rsplit(" ", 3)[1:]
    before, after = values[0], values[2]
    try:
        diff = float(after.rstrip("%")) - float(before.rstrip("%"))
        text = f"{diff:+g}" + ("%" if after.endswith("%") else "")
    except ValueError:
        text = after
    return text, label


def home(request):
    """Render the home page.

    URL: /
    Query params:
        riot_id: "Name#TAG". When present, redirects to that player's profile.
        server: platform id, e.g. "eun1" (default).
    Template: matches/home.html
    """
    riot_id = request.GET.get("riot_id", "").strip()
    server = request.GET.get("server", "eun1")
    if "#" in riot_id:
        name, tag = riot_id.split("#", 1)
        return redirect("player_games", server=server, name=name.strip(), tag=tag.strip())

    new, old = newest_two_patches()
    featured = []
    if old:
        version = new.patch_id
        champ_ch = champion_changes(Champion.objects.values_list("champion_id", flat=True), new, old)
        item_ch = item_changes(Item.objects.values_list("item_id", flat=True), new, old)
        champs = Champion.objects.in_bulk(champ_ch.keys())

        def champ_card(cid, kind, label):
            """Card data for one changed champion."""
            ch, champ = champ_ch[cid], champs[cid]
            stat, stat_label = biggest_stat_change(ch["lines"])
            return {"kind": kind, "label": label, "tag": f"Patch {new.patch_id}",
                    "name": champ.champion_name,
                    "subtitle": f"{len(ch['lines'])} stat{'s' if len(ch['lines']) > 1 else ''} changed",
                    "icon_url": f"{DDRAGON}/{version}/img/champion/{champ.champion_internal_name}.png",
                    "splash_url": f"{DDRAGON}/img/champion/splash/{champ.champion_internal_name}_0.jpg",
                    "stat": stat, "stat_label": stat_label,
                    "url": reverse("patch_notes") + f"#champ-{champ.champion_internal_name}"}

        def item_card(iid, label):
            """Card data for one changed item."""
            ch = item_ch[iid]
            stat, stat_label = biggest_stat_change(ch["lines"])
            return {"kind": "item", "label": label, "tag": f"Patch {new.patch_id}",
                    "name": ch["name"], "subtitle": ch["lines"][0],
                    "icon_url": f"{DDRAGON}/{version}/img/item/{iid}.png",
                    "splash_url": f"{DDRAGON}/{version}/img/item/{iid}.png",
                    "stat": stat, "stat_label": stat_label,
                    "url": reverse("patch_notes") + f"#item-{iid}"}

        buffs = sorted((c for c in champ_ch if champ_ch[c]["score"] > 0), key=lambda c: -champ_ch[c]["score"])
        nerfs = sorted((c for c in champ_ch if champ_ch[c]["score"] < 0), key=lambda c: champ_ch[c]["score"])
        item_buffs = sorted((i for i in item_ch if item_ch[i]["score"] > 0), key=lambda i: -item_ch[i]["score"])
        item_nerfs = sorted((i for i in item_ch if item_ch[i]["score"] < 0), key=lambda i: item_ch[i]["score"])

        if buffs:
            featured.append(champ_card(buffs[0], "buff", "Biggest buff"))
        if nerfs:
            featured.append(champ_card(nerfs[0], "nerf", "Biggest nerf"))
        if item_buffs:
            featured.append(item_card(item_buffs[0], "Item buff"))
        if item_nerfs:
            featured.append(item_card(item_nerfs[0], "Item nerf"))

    return render(request, "matches/home.html", {
        "patch_name": ".".join(new.patch_id.split(".")[:2]),
        "featured": featured,
    })


def coach_start(request):
    """Render the coach entry page.

    URL: /coach/
    Query params:
        riot_id, server: when a valid Riot ID is sent, redirects to that player's chat.
    Template: matches/coach_start.html

    Also lists the five most recently updated players as shortcuts.
    """
    riot_id = request.GET.get("riot_id", "").strip()
    server = request.GET.get("server", "eun1")
    if "#" in riot_id:
        name, tag = riot_id.split("#", 1)
        return redirect("coach_chat", server=server, name=name.strip(), tag=tag.strip())
    players = Player.objects.order_by("-player_last_updated")[:5]
    newest = Patch.objects.order_by("-patch_order").first()
    return render(request, "matches/coach_start.html", {
        "players": players,
        "version": newest.patch_id if newest else "",
        "error": "Write the Riot ID as Name#TAG." if riot_id else "",
    })


def coach_chat(request, server, name, tag):
    """Render the chat page for one player.

    URL: /player/<server>/<name>/<tag>/coach/
    Template: matches/coach_chat.html

    The conversation is kept in the Django session under "coach_<puuid>",
    so it survives a page reload.
    """
    player = find_player(server, name, tag)
    key = f"coach_{player.player_id}"
    return render(request, "matches/coach_chat.html", {
        "player": player,
        "server": server,
        "messages_list": request.session.get(key, []),
        "suggestions": SUGGESTIONS,
        "demo": DEMO_MODE,
    })


@require_POST
def coach_ask(request, server, name, tag):
    """Handle a chat question, then redirect back to the chat page.

    URL: /player/<server>/<name>/<tag>/coach/ask/  (POST only)
    Form fields:
        question: the user's question (cut to 1000 characters).
        reset: when present, clears the conversation instead.

    Uses POST/redirect/GET so refreshing the page does not send the question twice.
    Only the last MAX_TURNS messages are sent to the API.
    """
    player = find_player(server, name, tag)
    key = f"coach_{player.player_id}"

    if "reset" in request.POST:
        request.session.pop(key, None)
        return redirect("coach_chat", server=server, name=name, tag=tag)

    question = request.POST.get("question", "").strip()[:1000]
    if question:
        history = request.session.get(key, [])[-MAX_TURNS:]
        history.append({"role": "user", "content": question})
        answer = ask_coach(player, history)
        history.append({"role": "assistant", "content": answer})
        request.session[key] = history
    return redirect("coach_chat", server=server, name=name, tag=tag)


def patch_notes(request):
    """Render all champion and item changes between two patches.

    URL: /patch-notes/
    Query params:
        patch: older patch id to compare with, e.g. "16.18.1". Defaults to the
            previous patch, so picking an older one shows several patches combined.
    Template: matches/patch_notes.html
    """
    patches = list(Patch.objects.order_by("-patch_order"))
    new = patches[0]
    older = patches[1:]
    chosen = request.GET.get("patch")
    old = next((p for p in older if p.patch_id == chosen), older[0] if older else None)

    champ_ch = champion_changes(Champion.objects.values_list("champion_id", flat=True), new, old)
    item_ch = item_changes(Item.objects.values_list("item_id", flat=True), new, old)

    champs = Champion.objects.in_bulk(champ_ch.keys())
    champion_notes = sorted(
        ({"name": champs[cid].champion_name, "internal": champs[cid].champion_internal_name, **ch}
         for cid, ch in champ_ch.items()),
        key=lambda n: -n["score"])
    item_notes = sorted(({"id": iid, **ch} for iid, ch in item_ch.items()), key=lambda n: -n["score"])

    return render(request, "matches/patch_notes.html", {
        "patches": older,
        "new": new,
        "old": old,
        "patch_name": ".".join(new.patch_id.split(".")[:2]),
        "version": new.patch_id,
        "champion_notes": champion_notes,
        "item_notes": item_notes,
        "buffs": sum(n["status"] == "buff" for n in champion_notes + item_notes),
        "nerfs": sum(n["status"] == "nerf" for n in champion_notes + item_notes),
    })
