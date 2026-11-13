"""Views and query helpers for player profiles, per-champion stats and the item list."""
import re
from urllib.parse import quote

from django.core.management import call_command
from django.db.models import Count, Sum, Avg, Q
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from gamedata.models import Patch, Champion, PatchChampion, PatchItem, Skin
from matches.models import Player, MatchPlayer, MatchPlayerItem, PlayerMastery
from matches.riot_api import get_account

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


LOAD_COMMAND = "load_player"
TOP_CHAMPIONS = 4
RECENT_GAMES = 15

CHAMP_STATS = [
    ("hp", "Health"),
    ("hp_per_level", "Health per level"),
    ("attack_damage", "Attack damage"),
    ("attack_damage_per_level", "AD per level"),
    ("attack_speed", "Attack speed"),
    ("armor", "Armor"),
    ("armor_per_level", "Armor per level"),
    ("spell_block", "Magic resist"),
    ("move_speed", "Move speed"),
    ("attack_range", "Attack range"),
    ("mp", "Mana"),
    ("hp_regen", "Health regen"),
]


def kda(kills, deaths, assists):
    """KDA ratio, (kills + assists) / deaths, with zero deaths counted as one.

    Returns:
        Float rounded to one decimal.
    """
    return round((kills + assists) / max(deaths, 1), 1)


def find_player(server, name, tag):
    """Resolve a Riot ID to a stored Player.

    The puuid is looked up through the Riot API on every call, because a Riot ID can
    be renamed or reused. On the first visit, the player's matches are loaded with the
    load_player command.

    Args:
        server: Platform id, e.g. "eun1".
        name: Riot ID game name.
        tag: Riot ID tag line.

    Returns:
        Player.

    Raises:
        Http404: the Riot ID does not exist.
    """
    account = get_account(name, tag, server)
    if account is None:
        raise Http404("Riot ID not found")
    player = (Player.objects
              .select_related("player_top_champion", "player_background__skin_champion")
              .filter(player_id=account["puuid"]).first())
    if player is None:
        call_command(LOAD_COMMAND, f"{name}#{tag}", server)
        player = get_object_or_404(Player, player_id=account["puuid"])
    return player


SPLASH = "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{}_{}.jpg"


def background_url(player, main):
    """Splash art URL for the profile header.

    Priority: the skin the player chose, then the highest-mastery champion, then the
    most played champion in the stored games.

    Args:
        player: Player.
        main: Most played champion dict from player_games, or None.

    Returns:
        Image URL, or an empty string when nothing is known.
    """
    if player.player_background:
        skin = player.player_background
        return SPLASH.format(skin.skin_champion.champion_internal_name, skin.skin_num)
    if player.player_top_champion:
        return SPLASH.format(player.player_top_champion.champion_internal_name, 0)
    if main:
        return SPLASH.format(main["internal"], 0)
    return ""


def summarize(games):
    """Totals and averages over a set of games in one aggregate query.

    Wins use a filtered COUNT, so no second query is needed.

    Args:
        games: MatchPlayer queryset.

    Returns:
        Dict with "games", "wins", "win_rate", "kda" and "cs_min", or None when
        the queryset is empty.
    """
    t = games.aggregate(
        n=Count("id"),
        wins=Count("id", filter=Q(win=True)),
        k=Sum("kills"), d=Sum("deaths"), a=Sum("assists"),
        cs=Sum("cs"),
        seconds=Sum("matchplayer_match__match_duration"),
    )
    if not t["n"]:
        return None
    return {
        "games": t["n"],
        "wins": t["wins"],
        "win_rate": round(100 * t["wins"] / t["n"]),
        "kda": kda(t["k"], t["d"], t["a"]),
        "cs_min": round(t["cs"] / (t["seconds"] / 60), 1),
    }


def recent_games(games, how_many):
    """Latest games prepared for the match list.

    select_related joins match, queue and champion. prefetch_related loads the items of
    all games in one extra query instead of one per game (no N+1 problem).

    Args:
        games: MatchPlayer queryset.
        how_many: Number of games to return.

    Returns:
        List of MatchPlayer objects with extra attributes: kda, duration ("m:ss"),
        queue (description) and slots (7 item ids, None for an empty slot).
    """
    recent = list(
        games.select_related("matchplayer_match__match_queue", "matchplayer_champion")
        .prefetch_related("items")
        .order_by("-matchplayer_match__match_start")[:how_many]
    )
    for g in recent:
        g.kda = kda(g.kills, g.deaths, g.assists)
        minutes, seconds = divmod(g.matchplayer_match.match_duration, 60)
        g.duration = f"{minutes}:{seconds:02d}"
        queue = g.matchplayer_match.match_queue
        g.queue = queue.queue_description if queue else ""
        g.slots = [None] * 7
        for it in g.items.all():
            if it.slot < 7:
                g.slots[it.slot] = it.matchplayeritem_item_id
    return recent


def newest_two_patches():
    """Return the newest patch and the one before it.

    The loader gives the newest patch the highest patch_order.

    Returns:
        Tuple (newest, previous). previous is None when only one patch is loaded.
    """
    patches = list(Patch.objects.order_by("-patch_order")[:2])
    return patches[0], (patches[1] if len(patches) > 1 else None)


def champion_changes(champion_ids, new, old):
    """Base stat changes between two patches.

    Args:
        champion_ids: Champions to check.
        new: Newer Patch.
        old: Older Patch, or None.

    Returns:
        {champion_id: {"status": "buff" | "nerf", "lines": [str], "score": float}}
        for changed champions only. The score is the sum of the percentage change of
        every changed stat; above zero is a buff.
    """
    if old is None:
        return {}
    rows = PatchChampion.objects.filter(
        patchchampion_champion_id__in=champion_ids,
        patchchampion_patch__in=[new, old],
    )
    by_champ = {}
    for r in rows:
        by_champ.setdefault(r.patchchampion_champion_id, {})[r.patchchampion_patch_id] = r

    changes = {}
    for champ_id, patches in by_champ.items():
        if new.patch_id not in patches or old.patch_id not in patches:
            continue
        n, o = patches[new.patch_id], patches[old.patch_id]
        score, lines = 0, []
        for field, label in CHAMP_STATS:
            before, after = getattr(o, field), getattr(n, field)
            if before != after:
                lines.append(f"{label} {before:g} → {after:g}")
                if before:
                    score += (after - before) / abs(before) * 100
        if lines:
            changes[champ_id] = {"status": "buff" if score > 0 else "nerf", "lines": lines, "score": score}
    return changes


def item_changes(item_ids, new, old):
    """Stat and price changes between two patches.

    More of a stat counts as a buff, a higher price as a nerf.

    Args:
        item_ids: Items to check.
        new: Newer Patch.
        old: Older Patch, or None.

    Returns:
        Same shape as champion_changes, plus "name" for each item.
    """
    if old is None:
        return {}
    rows = PatchItem.objects.filter(
        patchitem_item_id__in=item_ids,
        patchitem_patch__in=[new, old],
    ).select_related("patchitem_item")
    by_item = {}
    for r in rows:
        by_item.setdefault(r.patchitem_item_id, {})[r.patchitem_patch_id] = r

    changes = {}
    for item_id, patches in by_item.items():
        if new.patch_id not in patches or old.patch_id not in patches:
            continue
        n, o = patches[new.patch_id], patches[old.patch_id]
        score, lines = 0, []
        if n.gold_total != o.gold_total:
            lines.append(f"Price {o.gold_total} → {n.gold_total}")
            if o.gold_total:
                score -= (n.gold_total - o.gold_total) / o.gold_total * 100
        for key in set(o.stats) | set(n.stats):
            before, after = o.stats.get(key, 0), n.stats.get(key, 0)
            if before != after:
                label, percent = STAT_NAMES.get(key, (key, False))
                if percent:
                    lines.append(f"{label} {round(before * 100)}% → {round(after * 100)}%")
                else:
                    lines.append(f"{label} {before:g} → {after:g}")
                score += (after - before) / abs(before) * 100 if before else 100
        if lines:
            changes[item_id] = {
                "status": "buff" if score > 0 else "nerf",
                "lines": lines,
                "name": n.patchitem_item.item_name,
                "score": score,
            }
    return changes


def patch_marks(player, champ_ids, new, old):
    """Patch notes that matter to one player, per champion.

    A champion is marked when its own stats changed, or when one of the three items
    the player builds most on it changed.

    Args:
        player: Player.
        champ_ids: Champions to check (usually the player's top champions).
        new: Newer Patch.
        old: Older Patch, or None.

    Returns:
        {champion_id: (status, note)}, e.g. ("nerf", "Nerfed this patch").
    """
    top_items = {}
    rows = (MatchPlayerItem.objects.counted()
            .filter(matchplayeritem_matchplayer__matchplayer_player=player,
                    matchplayeritem_matchplayer__matchplayer_champion_id__in=champ_ids,
                    slot__lt=6)
            .exclude(matchplayeritem_item=None)
            .values("matchplayeritem_matchplayer__matchplayer_champion_id", "matchplayeritem_item_id")
            .annotate(n=Count("id"))
            .order_by("-n"))
    for r in rows:
        items = top_items.setdefault(r["matchplayeritem_matchplayer__matchplayer_champion_id"], [])
        if len(items) < 3:
            items.append(r["matchplayeritem_item_id"])

    champ_ch = champion_changes(champ_ids, new, old)
    item_ch = item_changes({i for ids in top_items.values() for i in ids}, new, old)

    marks = {}
    for cid in champ_ids:
        if cid in champ_ch:
            status = champ_ch[cid]["status"]
            marks[cid] = (status, ("Buffed" if status == "buff" else "Nerfed") + " this patch")
            continue
        for item_id in top_items.get(cid, []):
            if item_id in item_ch:
                status = item_ch[item_id]["status"]
                marks[cid] = (status, f"{item_ch[item_id]['name']} " + ("buffed" if status == "buff" else "nerfed"))
                break
    return marks


def short_number(n):
    """Short form of a large number, e.g. 123456 -> '123k', 1234567 -> '1.2M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{round(n / 1000)}k"
    return str(n)


def player_games(request, server, name, tag):
    """Render the player profile.

    URL: /player/<server>/<name>/<tag>/
    Query params:
        missing: champion name that the champion search did not find (shows a hint).
    Template: matches/player_games.html

    Statistics leave out remakes; the match history still shows them.
    """
    player = find_player(server, name, tag)
    all_games = MatchPlayer.objects.filter(matchplayer_player=player)
    games = all_games.counted()
    new, old = newest_two_patches()
    summary = summarize(games)

    played = list(
        games.exclude(matchplayer_champion=None)
        .values("matchplayer_champion_id",
                "matchplayer_champion__champion_name",
                "matchplayer_champion__champion_internal_name")
        .annotate(
            n=Count("id"),
            wins=Count("id", filter=Q(win=True)),
            k=Avg("kills"), d=Avg("deaths"), a=Avg("assists"),
        )
        .order_by("-n", "matchplayer_champion__champion_name")
    )
    top = played[:TOP_CHAMPIONS]
    top_ids = [c["matchplayer_champion_id"] for c in top]

    marks = patch_marks(player, set(top_ids), new, old)

    masteries = {m.mastery_champion_id: m
                 for m in PlayerMastery.objects.filter(mastery_player=player, mastery_champion_id__in=top_ids)}

    for c in top:
        cid = c["matchplayer_champion_id"]
        c["name"] = c["matchplayer_champion__champion_name"]
        c["internal"] = c["matchplayer_champion__champion_internal_name"]
        c["win_rate"] = round(100 * c["wins"] / c["n"])
        c["avg_k"], c["avg_d"], c["avg_a"] = round(c["k"], 1), round(c["d"], 1), round(c["a"], 1)
        c["status"], c["note"] = marks.get(cid, ("", ""))
        mastery = masteries.get(cid)
        c["mastery_level"] = mastery.mastery_level if mastery else None
        c["mastery_points"] = short_number(mastery.mastery_points) if mastery else ""

    impacts = [{**c, "share": round(100 * c["n"] / summary["games"])} for c in top if c["status"]]

    main = top[0] if top else None

    return render(request, "matches/player_games.html", {
        "player": player,
        "server": server,
        "summary": summary,
        "top": top,
        "played_count": len(played),
        "played_names": sorted(c["matchplayer_champion__champion_name"] for c in played),
        "missing": request.GET.get("missing", ""),
        "impacts": impacts,
        "recent": recent_games(all_games, RECENT_GAMES),
        "main": main,
        "bg_url": background_url(player, main),
        "version": new.patch_id,
        "patch_name": new.patch_id,
    })


def player_champion_search(request, server, name, tag):
    """Open the stats page of a champion typed in the profile search box.

    URL: /player/<server>/<name>/<tag>/champions/
    Query params:
        q: champion name (exact match first, then partial).

    Redirects to player_champion, or back to the profile with ?missing= when the
    player has no games on that champion.
    """
    player = find_player(server, name, tag)
    q = request.GET.get("q", "").strip()
    played = MatchPlayer.objects.filter(matchplayer_player=player).exclude(matchplayer_champion=None)

    row = (played.filter(matchplayer_champion__champion_name__iexact=q).first()
           or played.filter(matchplayer_champion__champion_name__icontains=q).first()) if q else None

    if row is None:
        url = reverse("player_games", args=[server, name, tag])
        return redirect(f"{url}?missing={quote(q)}")
    return redirect("player_champion", server=server, name=name, tag=tag,
                    champion=row.matchplayer_champion.champion_internal_name)


def per_game(t, field):
    """Total of one field divided by the number of games, rounded to one decimal."""
    return t[field] / t["n"]

FACTORS = [
    ("Deaths", lambda t: per_game(t, "d"), True, "You die a lot more in the games you lose. Play safer when you're behind."),
    ("Farming", lambda t: t["cs"] / (t["seconds"] / 60), False, "Your CS drops in losses. Keep farming even when the lane goes badly."),
    ("Damage", lambda t: per_game(t, "dmg"), False, "You deal much less damage to champions in losses. Look for fights where you can still hit."),
    ("Vision", lambda t: per_game(t, "vision"), False, "Your vision score drops in losses. Buy Control Wards and use your trinket."),
    ("Kills", lambda t: per_game(t, "k"), False, "You get far fewer kills in losses. Your games depend on getting ahead early."),
    ("Assists", lambda t: per_game(t, "a"), False, "You join fewer fights in losses. Group with your team more."),
]


NERF_TIPS = [
    (("Health", "Armor", "Magic resist", "Health regen"),
     "{name} is less tanky now. Trade less in lane and wait for your first item before fighting."),
    (("Attack damage", "AD per level", "Attack speed", "Mana"),
     "{name} hits softer early. Farm safely and look for fights after your first item, not before."),
    (("Move speed", "Attack range"),
     "{name} has less room for mistakes in positioning. Keep your distance and don't chase."),
]


def item_alternative(item_id, player, champ, new, avoid):
    """Suggest a replacement for a nerfed item.

    Candidates share the nerfed item's biggest stat, cost within 600 gold of it and are
    not in `avoid`. Items the player already won with on this champion (2+ games) come
    first, then the closest price.

    Args:
        item_id: The nerfed item.
        player: Player.
        champ: Champion the build is for.
        new: Newest Patch.
        avoid: Item ids to skip, e.g. the rest of the player's build.

    Returns:
        {"id": item_id, "name": str}, or None when nothing fits.
    """
    current = PatchItem.objects.filter(patchitem_patch=new, patchitem_item_id=item_id).first()
    if current is None or not current.stats:
        return None
    main_stat = max(current.stats, key=lambda k: abs(current.stats[k]))
    candidates = [
        pi for pi in PatchItem.objects.filter(patchitem_patch=new).select_related("patchitem_item")
        if pi.patchitem_item_id != item_id and pi.patchitem_item_id not in avoid
        and main_stat in pi.stats and abs(pi.gold_total - current.gold_total) <= 600
        and pi.gold_total >= 1000
    ]
    if not candidates:
        return None
    win_rates = {
        r["matchplayeritem_item_id"]: (r["wins"] / r["n"], r["n"])
        for r in MatchPlayerItem.objects.counted()
        .filter(matchplayeritem_matchplayer__matchplayer_player=player,
                matchplayeritem_matchplayer__matchplayer_champion=champ,
                matchplayeritem_item_id__in=[c.patchitem_item_id for c in candidates])
        .values("matchplayeritem_item_id")
        .annotate(n=Count("id"), wins=Count("id", filter=Q(matchplayeritem_matchplayer__win=True)))
    }
    best = min(candidates, key=lambda c: (
        -(win_rates.get(c.patchitem_item_id, (0, 0))[0] if win_rates.get(c.patchitem_item_id, (0, 0))[1] >= 2 else 0),
        abs(c.gold_total - current.gold_total)))
    return {"id": best.patchitem_item_id, "name": best.patchitem_item.item_name}


def patch_advice(player, server, champ, summary, build, champ_change, new, old):
    """Advice for this patch on one champion.

    Combines the player's win rate on the champion with what changed:
    - nerfed and under 48% win rate (5+ games): play the best non-nerfed champion instead;
    - nerfed and 55%+ win rate: keep playing it;
    - nerfed: a playstyle tip based on which stats went down;
    - buffed: a note that it is a good patch for it;
    - nerfed build item: a replacement from item_alternative.

    Args:
        player: Player.
        server: Platform id from the URL, used for links.
        champ: Champion.
        summary: Result of summarize() for these games.
        build: Most built items, each with an optional "change".
        champ_change: This champion's entry from champion_changes, or None.
        new: Newest Patch.
        old: Previous Patch, or None.

    Returns:
        List of dicts with "kind" (switch, keep, play, item), "title", "text" and,
        when relevant, "link", "item_id" and "alt".
    """
    advice = []
    name = champ.champion_name
    wr, games = summary["win_rate"], summary["games"]

    if champ_change and champ_change["status"] == "nerf":
        if games >= 5 and wr < 48:
            others = (MatchPlayer.objects.counted()
                      .filter(matchplayer_player=player)
                      .exclude(matchplayer_champion=champ).exclude(matchplayer_champion=None)
                      .values("matchplayer_champion_id", "matchplayer_champion__champion_name",
                              "matchplayer_champion__champion_internal_name")
                      .annotate(n=Count("id"), wins=Count("id", filter=Q(win=True)))
                      .filter(n__gte=5))
            nerfed = champion_changes([o["matchplayer_champion_id"] for o in others], new, old)
            others = [o for o in others if nerfed.get(o["matchplayer_champion_id"], {}).get("status") != "nerf"]
            best = max(others, key=lambda o: o["wins"] / o["n"], default=None)
            if best and best["wins"] / best["n"] * 100 > wr:
                advice.append({"kind": "switch",
                               "title": f"Play less {name} this patch",
                               "text": f"You win {wr}% of your {name} games and it just got weaker. "
                                       f"You do better on {best['matchplayer_champion__champion_name']} "
                                       f"({round(best['wins'] / best['n'] * 100)}% in {best['n']} games).",
                               "link": reverse("player_champion", args=[
                                   server, player.player_username, player.player_tag,
                                   best["matchplayer_champion__champion_internal_name"]])})
            else:
                advice.append({"kind": "switch", "title": f"Be careful on {name}",
                               "text": f"You win {wr}% of your {name} games and it just got weaker. "
                                       f"Keep it for games where you're confident in the matchup."})
        elif wr >= 55:
            advice.append({"kind": "keep", "title": f"Keep playing {name}",
                           "text": f"You win {wr}% of your games on it, so a small nerf shouldn't change much. "
                                   f"Expect lane to be a bit harder."})
        changed = " ".join(champ_change["lines"])
        for stats, tip in NERF_TIPS:
            if any(stat in changed for stat in stats):
                advice.append({"kind": "play", "title": "Adjust how you play", "text": tip.format(name=name)})
                break
    elif champ_change and champ_change["status"] == "buff":
        text = (f"{name} got stronger and you already win {wr}% on it. A good time to play it more."
                if wr >= 50 else
                f"{name} got stronger, which should help your {wr}% win rate on it. Worth giving it a few more games.")
        advice.append({"kind": "keep", "title": f"Good patch for {name}", "text": text})

    build_ids = {b["id"] for b in build}
    for b in build:
        change = b.get("change")
        if not change or change["status"] != "nerf":
            continue
        alt = item_alternative(b["id"], player, champ, new, avoid=build_ids)
        text = f"{b['name']} got worse ({', '.join(change['lines'])})."
        if alt:
            text += f" Try {alt['name']} instead, it gives the same main stat for a similar price."
        advice.append({"kind": "item", "title": f"Rethink {b['name']}", "text": text,
                       "item_id": b["id"], "alt": alt})
    return advice


def player_champion(request, server, name, tag, champion):
    """Render one player's results on one champion.

    URL: /player/<server>/<name>/<tag>/champion/<champion>/
    Template: matches/player_champion.html

    Shows the build with win rate per item, the stats that differ most between wins
    and losses, the patch changes and advice for this patch.

    Raises:
        Http404: unknown champion, or no games on it.
    """
    player = find_player(server, name, tag)
    champ = get_object_or_404(Champion, champion_internal_name=champion)
    all_games = MatchPlayer.objects.filter(matchplayer_player=player, matchplayer_champion=champ)
    games = all_games.counted()
    summary = summarize(games)
    if summary is None:
        raise Http404("No games on this champion")
    new, old = newest_two_patches()

    build = list(
        MatchPlayerItem.objects.counted()
        .filter(matchplayeritem_matchplayer__in=games, slot__lt=6)
        .exclude(matchplayeritem_item=None)
        .values("matchplayeritem_item_id", "matchplayeritem_item__item_name")
        .annotate(n=Count("id"), wins=Count("id", filter=Q(matchplayeritem_matchplayer__win=True)))
        .order_by("-n")[:6]
    )
    for b in build:
        b["id"] = b["matchplayeritem_item_id"]
        b["name"] = b["matchplayeritem_item__item_name"]
        b["pick_rate"] = round(100 * b["n"] / summary["games"])
        b["win_rate"] = round(100 * b["wins"] / b["n"])

    def totals(qs):
        """Sums for one group of games (wins or losses), used to compare the two."""
        return qs.aggregate(
            n=Count("id"), k=Sum("kills"), d=Sum("deaths"), a=Sum("assists"),
            cs=Sum("cs"), seconds=Sum("matchplayer_match__match_duration"),
            dmg=Sum("damage_to_champions"), gold=Sum("gold_earned"), vision=Sum("vision_score"),
        )
    w, l = totals(games.filter(win=True)), totals(games.filter(win=False))
    factors = []
    if w["n"] and l["n"]:
        for label, calc, lower_is_better, sentence in FACTORS:
            win_v, loss_v = calc(w), calc(l)
            if not win_v:
                continue
            diff = (loss_v - win_v) / win_v * 100
            worse_in_losses = diff > 0 if lower_is_better else diff < 0
            if worse_in_losses and abs(diff) >= 15:
                factors.append({"label": label,
                                "win": round(win_v) if win_v >= 100 else round(win_v, 1),
                                "loss": round(loss_v) if loss_v >= 100 else round(loss_v, 1),
                                "diff": round(abs(diff)), "sentence": sentence})
        factors.sort(key=lambda f: f["diff"], reverse=True)
        factors = factors[:3]

    champ_change = champion_changes([champ.champion_id], new, old).get(champ.champion_id)
    item_ch = item_changes([b["id"] for b in build], new, old)
    for b in build:
        b["change"] = item_ch.get(b["id"])
    advice = patch_advice(player, server, champ, summary, build, champ_change, new, old)

    return render(request, "matches/player_champion.html", {
        "player": player,
        "server": server,
        "champ": champ,
        "summary": summary,
        "build": build,
        "factors": factors,
        "has_both": bool(w["n"] and l["n"]),
        "champ_change": champ_change,
        "advice": advice,
        "recent": recent_games(all_games, RECENT_GAMES),
        "version": new.patch_id,
        "patch_name": new.patch_id,
    })


def choose_background(request, server, name, tag):
    """Pick the splash art shown behind the profile header.

    URL: /player/<server>/<name>/<tag>/background/
    GET: lists the skins of the champions the player has played (highest-mastery
    champion first, then most played).
    POST: saves the selected skin (skin_id) and redirects to the profile.
    """
    player = find_player(server, name, tag)

    if request.method == "POST":
        skin_id = request.POST.get("skin_id", "")
        player.player_background = Skin.objects.filter(skin_id=skin_id).first() if skin_id else None
        player.save()
        return redirect("player_games", server=server, name=name, tag=tag)

    played = (MatchPlayer.objects
              .filter(matchplayer_player=player)
              .exclude(matchplayer_champion=None)
              .values("matchplayer_champion_id")
              .annotate(n=Count("id"))
              .order_by("-n"))
    champ_ids = [row["matchplayer_champion_id"] for row in played]
    if player.player_top_champion_id:
        champ_ids = [player.player_top_champion_id] + [c for c in champ_ids if c != player.player_top_champion_id]

    champs_by_id = Champion.objects.prefetch_related("skins").in_bulk(champ_ids)
    champions = [champs_by_id[c] for c in champ_ids if c in champs_by_id]

    return render(request, "matches/choose_background.html", {
        "player": player,
        "server": server,
        "champions": champions,
        "current": player.player_background_id,
        "version": newest_two_patches()[0].patch_id,
    })


@require_POST
def refresh_player(request, server, name, tag):
    """Load new matches for the player, then redirect to the profile.

    URL: /player/<server>/<name>/<tag>/refresh/  (POST only)

    The loader skips games that are already stored, so this only downloads new ones.
    """
    call_command(LOAD_COMMAND, f"{name}#{tag}", server)
    return redirect("player_games", server=server, name=name, tag=tag)


def items(request):
    """Render the item list for the newest patch.

    URL: /items/
    Query params:
        q: part of an item name.
        stat: Data Dragon stat key, e.g. "FlatMagicDamageMod".
        item: item id to open in the side panel on load.
    Template: matches/items.html
    """
    new, old = newest_two_patches()
    q = request.GET.get("q", "")
    stat = request.GET.get("stat", "")

    items = (PatchItem.objects
             .filter(patchitem_patch=new)
             .select_related("patchitem_item")
             .order_by("patchitem_item__item_name"))

    if q:
        items = items.filter(patchitem_item__item_name__icontains=q)
    if stat:
        items = items.filter(stats__has_key=stat)

    changes = item_changes([pi.patchitem_item_id for pi in items], new, old)

    for pi in items:
        pi.stat_list = []
        for key, value in pi.stats.items():
            label, percent = STAT_NAMES.get(key, (key, False))
            if percent:
                pi.stat_list.append((label, f"{round(value * 100)}%"))
            else:
                pi.stat_list.append((label, f"{value:g}"))

        pi.clean_description = " ".join(re.sub(r"<[^>]+>", " ", pi.description).split())

        change = changes.get(pi.patchitem_item_id)
        pi.status = change["status"] if change else ""
        pi.change_lines = change["lines"] if change else []

    return render(request, "matches/items.html", {
        "items": items,
        "patch_name": new.patch_id,
        "version": new.patch_id,
        "q": q,
        "active_stat": stat,
        "stat_chips": STAT_CHIPS,
        "open_item": request.GET.get("item", ""),
    })
