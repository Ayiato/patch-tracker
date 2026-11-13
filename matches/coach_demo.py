"""Rule-based fallback for the coach when no API key is configured.

Picks a canned answer by keyword and fills it with the player's real numbers,
so the chat still works in a local demo.
"""
from django.db.models import Count, Avg, Q

from matches.models import MatchPlayer, MatchPlayerItem
from matches.player_views import summarize, newest_two_patches, champion_changes, item_changes

MIN_GAMES = 5


def champion_stats(games):
    """Games, wins and win rate per champion for a player, most played first."""
    rows = list(
        games.exclude(matchplayer_champion=None)
        .values("matchplayer_champion_id", "matchplayer_champion__champion_name")
        .annotate(n=Count("id"), wins=Count("id", filter=Q(win=True)))
        .order_by("-n")
    )
    for r in rows:
        r["name"] = r["matchplayer_champion__champion_name"]
        r["wr"] = round(100 * r["wins"] / r["n"])
    return rows


def answer_pick(player, games, champs):
    """Suggest a champion: best win rate with a minimum sample, plus this patch's changes."""
    enough = [c for c in champs if c["n"] >= MIN_GAMES]
    if not enough:
        return "You don't have 5 games on any champion yet. Play a few more and ask again."
    best = max(enough, key=lambda c: (c["wr"], c["n"]))
    worst = min(enough, key=lambda c: (c["wr"], -c["n"]))
    lines = [f"Go with {best['name']}: {best['wr']}% win rate in {best['n']} games, your best champion with at least {MIN_GAMES} games."]

    new, old = newest_two_patches()
    changes = champion_changes([c["matchplayer_champion_id"] for c in enough], new, old)
    names = {c["matchplayer_champion_id"]: c["name"] for c in enough}
    buffed = [names[cid] for cid, ch in changes.items() if ch["status"] == "buff"]
    nerfed = [names[cid] for cid, ch in changes.items() if ch["status"] == "nerf"]
    if buffed:
        lines.append(f"- Buffed this patch: {', '.join(buffed)}. Good time to play them.")
    if nerfed:
        lines.append(f"- Nerfed this patch: {', '.join(nerfed)}. Expect them to feel a bit weaker.")
    if worst["name"] != best["name"]:
        lines.append(f"- Careful with {worst['name']}: {worst['wr']}% in {worst['n']} games.")
    return "\n".join(lines)


def answer_losses(player, games, champs):
    """Compare average deaths, damage and vision between wins and losses."""
    def avg(win):
        """Average of one field over a queryset, rounded to one decimal."""
        return games.filter(win=win).aggregate(
            d=Avg("deaths"), dmg=Avg("damage_to_champions"), vision=Avg("vision_score"), cs=Avg("cs"))

    w, l = avg(True), avg(False)
    if w["d"] is None or l["d"] is None:
        return "I need at least one win and one loss to compare them."
    lines = ["Here's what changes between your wins and your losses:"]
    lines.append(f"- Deaths: {l['d']:.1f} in losses vs {w['d']:.1f} in wins.")
    lines.append(f"- Damage to champions: {l['dmg']:.0f} vs {w['dmg']:.0f}.")
    lines.append(f"- Vision score: {l['vision']:.0f} vs {w['vision']:.0f}.")
    lines.append(f"- CS: {l['cs']:.0f} vs {w['cs']:.0f}.")
    if l["d"] - w["d"] >= 1.5:
        lines.append("Biggest difference is deaths. Play safer when you're behind and don't fight without vision.")
    elif w["dmg"] and (w["dmg"] - l["dmg"]) / w["dmg"] > 0.25:
        lines.append("Biggest difference is damage. In losses you're not getting into fights, so group with your team for objectives.")
    else:
        lines.append("Your stats are close in wins and losses, so it's more about the team. Keep doing what you do and focus on objectives.")
    return "\n".join(lines)


def answer_patch(player, games, champs):
    """List patch changes that affect the player's champions and most built items."""
    new, old = newest_two_patches()
    if old is None:
        return "Only one patch is loaded, so there's nothing to compare yet."
    champ_ch = champion_changes([c["matchplayer_champion_id"] for c in champs], new, old)
    built = (MatchPlayerItem.objects.counted()
             .filter(matchplayeritem_matchplayer__matchplayer_player=player, slot__lt=6)
             .exclude(matchplayeritem_item=None)
             .values("matchplayeritem_item_id").annotate(n=Count("id")).order_by("-n")[:10])
    item_ch = item_changes([b["matchplayeritem_item_id"] for b in built], new, old)
    names = {c["matchplayer_champion_id"]: c["name"] for c in champs}

    if not champ_ch and not item_ch:
        return f"Nothing you play changed in patch {new.patch_id}. Your champions and items are the same as last patch."
    lines = [f"Patch {new.patch_id} for you:"]
    for cid, ch in champ_ch.items():
        lines.append(f"- {names[cid]} {'buffed' if ch['status'] == 'buff' else 'nerfed'}: {'; '.join(ch['lines'])}")
    for ch in item_ch.values():
        lines.append(f"- {ch['name']} {'buffed' if ch['status'] == 'buff' else 'nerfed'}: {'; '.join(ch['lines'])}")
    return "\n".join(lines)


def answer_build(player, games, champs):
    """Most built items on the player's main champion, with the win rate for each."""
    if not champs:
        return "No games loaded yet."
    main = champs[0]
    rows = (MatchPlayerItem.objects.counted()
            .filter(matchplayeritem_matchplayer__matchplayer_player=player,
                    matchplayeritem_matchplayer__matchplayer_champion_id=main["matchplayer_champion_id"],
                    slot__lt=6)
            .exclude(matchplayeritem_item=None)
            .values("matchplayeritem_item__item_name")
            .annotate(n=Count("id"), wins=Count("id", filter=Q(matchplayeritem_matchplayer__win=True)))
            .order_by("-n")[:5])
    if not rows:
        return f"I don't have item data for your {main['name']} games yet."
    lines = [f"Your {main['name']} build ({main['n']} games):"]
    for r in rows:
        lines.append(f"- {r['matchplayeritem_item__item_name']}: built {r['n']} times, {round(100 * r['wins'] / r['n'])}% win rate")
    best = max(rows, key=lambda r: r["wins"] / r["n"])
    lines.append(f"Your best result is with {best['matchplayeritem_item__item_name']}. Keep it in your core build.")
    return "\n".join(lines)


def answer_overview(player, games, champs):
    """General summary used when the question matches no keyword."""
    total = summarize(games)
    if total is None:
        return "No games loaded yet. Press Refresh on your profile first."
    main = champs[0]["name"] if champs else "?"
    return (f"You have {total['games']} games loaded: {total['win_rate']}% win rate, KDA {total['kda']}, "
            f"{total['cs_min']} CS per minute. Your main is {main}.\n"
            "Ask me what to play this patch, why you lose games, what changed for you, or what to build.")


TOPICS = [
    (("lose", "losing", "loss", "improve", "better", "wrong"), answer_losses),
    (("build", "item"), answer_build),
    (("play", "pick"), answer_pick),
    (("buff", "nerf", "patch", "change"), answer_patch),
]


def demo_answer(player, question):
    """Route a question to one of the canned answers by keyword."""
    games = MatchPlayer.objects.counted().filter(matchplayer_player=player)
    champs = champion_stats(games)
    q = question.lower()
    for keywords, answer in TOPICS:
        if any(word in q for word in keywords):
            return answer(player, games, champs)
    return answer_overview(player, games, champs)
