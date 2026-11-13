"""AI coach backed by the Claude API.

No model is trained. Every request sends a system prompt built from the player's stats in
PostgreSQL and the latest patch diff, so the answers stay tied to that player's data.
When ANTHROPIC_API_KEY is missing, questions go to the rule-based coach_demo module.
"""
import os

import anthropic
from django.db.models import Count, Avg, Q

from matches.models import MatchPlayer, MatchPlayerItem
from matches.coach_demo import demo_answer
from matches.player_views import (summarize, recent_games, newest_two_patches,
                                  champion_changes, item_changes, kda)

MODEL = "claude-opus-5-5"
CHAMPIONS_IN_PROMPT = 10
GAMES_IN_PROMPT = 20

ROLE_NAMES = {"TOP": "Top", "JUNGLE": "Jungle", "MIDDLE": "Mid", "BOTTOM": "ADC", "UTILITY": "Support"}

DEMO_MODE = not os.getenv("ANTHROPIC_API_KEY")
client = None if DEMO_MODE else anthropic.Anthropic()

RULES = """You are the PatchTracker coach, a friendly League of Legends coach.
You coach ONE player, using only the data below (their own games loaded from the Riot API
and the base-stat / item changes between the last two patches from Data Dragon).

How to answer:
- Short and concrete: a few sentences or a short list, no long essays.
- Plain text only: no markdown (no **, no #, no tables). For lists start lines with "- ".
- Always back advice with numbers from the data ("your Ahri win rate is 40% in 10 games").
- Small samples (under 5 games) are not reliable; say so instead of drawing big conclusions.
- Patch changes here are base stats and item stats/prices only. Ability changes are not in
  the data, so don't invent them; say the player should check the official patch notes.
- If the question isn't about League of Legends or this player, steer back politely.
"""


def player_context(player):
    """Build the text summary of a player that goes into the system prompt.

    Covers overall stats, roles, champions, most built items, recent games and the patch
    changes that touch the player's champions and items. Remakes are left out.

    Args:
        player: Player to describe.

    Returns:
        Multi-line plain text, or a short notice when the player has no games.
    """
    games = MatchPlayer.objects.counted().filter(matchplayer_player=player)
    total = summarize(games)
    if total is None:
        return "This player has no games loaded yet."
    new, old = newest_two_patches()

    lines = [f"PLAYER: {player.player_username}#{player.player_tag} ({player.player_region})"]
    if player.player_tier:
        lines.append(f"Solo/Duo rank: {player.player_tier.title()} {player.player_division} "
                     f"{player.player_lp} LP ({player.player_ranked_wins}W {player.player_ranked_losses}L)")
    lines.append(f"Loaded games: {total['games']}, win rate {total['win_rate']}%, "
                 f"KDA {total['kda']}, CS/min {total['cs_min']}")

    roles = (games.exclude(position="").values("position")
             .annotate(n=Count("id"), wins=Count("id", filter=Q(win=True))).order_by("-n"))
    if roles:
        lines.append("Roles: " + ", ".join(
            f"{ROLE_NAMES.get(r['position'], r['position'])} {r['n']} games ({round(100 * r['wins'] / r['n'])}% WR)" for r in roles))

    champs = list(
        games.exclude(matchplayer_champion=None)
        .values("matchplayer_champion_id", "matchplayer_champion__champion_name")
        .annotate(n=Count("id"), wins=Count("id", filter=Q(win=True)),
                  k=Avg("kills"), d=Avg("deaths"), a=Avg("assists"),
                  dmg=Avg("damage_to_champions"), vision=Avg("vision_score"))
        .order_by("-n")[:CHAMPIONS_IN_PROMPT]
    )
    lines.append("\nMOST PLAYED CHAMPIONS:")
    for c in champs:
        lines.append(
            f"- {c['matchplayer_champion__champion_name']}: {c['n']} games, "
            f"{round(100 * c['wins'] / c['n'])}% WR, KDA {kda(c['k'], c['d'], c['a'])} "
            f"({c['k']:.1f}/{c['d']:.1f}/{c['a']:.1f}), {c['dmg']:.0f} damage, {c['vision']:.0f} vision")

    built = (MatchPlayerItem.objects.counted()
             .filter(matchplayeritem_matchplayer__matchplayer_player=player, slot__lt=6)
             .exclude(matchplayeritem_item=None)
             .values("matchplayeritem_item_id", "matchplayeritem_item__item_name")
             .annotate(n=Count("id")).order_by("-n")[:12])
    if built:
        lines.append("\nMOST BUILT ITEMS: " + ", ".join(
            f"{b['matchplayeritem_item__item_name']} ({b['n']}x)" for b in built))

    if old:
        champ_ch = champion_changes([c["matchplayer_champion_id"] for c in champs], new, old)
        item_ch = item_changes([b["matchplayeritem_item_id"] for b in built], new, old)
        lines.append(f"\nPATCH {new.patch_id} vs {old.patch_id} (changes that affect this player):")
        names = {c["matchplayer_champion_id"]: c["matchplayer_champion__champion_name"] for c in champs}
        for cid, ch in champ_ch.items():
            lines.append(f"- {names[cid]} {ch['status'].upper()}: " + "; ".join(ch["lines"]))
        for ch in item_ch.values():
            lines.append(f"- Item {ch['name']} {ch['status'].upper()}: " + "; ".join(ch["lines"]))
        if not champ_ch and not item_ch:
            lines.append("- None of their champions or items changed base stats.")

    lines.append(f"\nLAST {GAMES_IN_PROMPT} GAMES (newest first):")
    for g in recent_games(games, GAMES_IN_PROMPT):
        champ = g.matchplayer_champion.champion_name if g.matchplayer_champion else "?"
        lines.append(
            f"- {'WIN' if g.win else 'LOSS'} {champ} {ROLE_NAMES.get(g.position, '')} "
            f"{g.kills}/{g.deaths}/{g.assists}, {g.cs} CS, {g.damage_to_champions} dmg, "
            f"{g.vision_score} vision, {g.duration}, {g.queue}")
    return "\n".join(lines)


def ask_coach(player, history):
    """Send the conversation to Claude and return the coach's reply.

    Args:
        player: Player the chat is about.
        history: List of {"role": "user" | "assistant", "content": str} dicts,
            ending with the new question.

    Returns:
        The reply text. API errors are turned into a readable message for the chat
        instead of raising, so the page never crashes on a network or key problem.
    """
    if DEMO_MODE:
        return demo_answer(player, history[-1]["content"])
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=RULES + "\n\n" + player_context(player),
            messages=history,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        return "The coach can't log in: check ANTHROPIC_API_KEY in your .env and restart the server."
    except anthropic.RateLimitError:
        return "Too many questions at once. Wait a few seconds and ask again."
    except anthropic.APIStatusError as e:
        return f"The AI service returned an error ({e.status_code}). Try again in a moment."
    except anthropic.APIConnectionError:
        return "Couldn't reach the AI service. Check your internet connection."

    if response.stop_reason == "refusal":
        return "The coach can't answer that one. Ask something about your games."
    return "".join(block.text for block in response.content if block.type == "text").strip()
