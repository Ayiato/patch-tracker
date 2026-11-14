"""Tests for the buff/nerf scoring and the player statistics (player_views.py).

Run with: python manage.py test matches
Django creates an empty test database, so these tests never touch the real data
and never call the Riot API.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from django.core.management import CommandError
from django.http import Http404
from django.test import SimpleTestCase, TestCase

from gamedata.models import Patch, Item
from gamedata.tests import make_champion, make_champion_stats, make_item_stats
from matches.models import Player, Match, MatchPlayer
from matches.player_views import (
    kda, short_number, champion_changes, item_changes, summarize, newest_two_patches, find_player,
)


class KdaTests(SimpleTestCase):
    """kda() = (kills + assists) / deaths, with zero deaths counted as one."""

    def test_normal_kda(self):
        self.assertEqual(kda(kills=5, deaths=2, assists=7), 6.0)

    def test_zero_deaths_counts_as_one(self):
        self.assertEqual(kda(kills=4, deaths=0, assists=6), 10.0)

    def test_result_is_rounded_to_one_decimal(self):
        self.assertEqual(kda(kills=1, deaths=3, assists=1), 0.7)


class ShortNumberTests(SimpleTestCase):
    """short_number() shortens mastery points for the profile page."""

    def test_small_number_stays_the_same(self):
        self.assertEqual(short_number(950), "950")

    def test_thousands(self):
        self.assertEqual(short_number(123456), "123k")

    def test_millions(self):
        self.assertEqual(short_number(1234567), "1.2M")


class ChampionScoreTests(TestCase):
    """champion_changes() decides if a champion was buffed or nerfed.

    The score is the sum of the percentage change of every changed stat.
    """

    def setUp(self):
        self.old = Patch.objects.create(patch_id="16.21.1", patch_order=1)
        self.new = Patch.objects.create(patch_id="16.22.1", patch_order=2)
        self.champ = make_champion(112, "Viktor")

    def score_for(self, old_stats, new_stats):
        make_champion_stats(self.old, self.champ, **old_stats)
        make_champion_stats(self.new, self.champ, **new_stats)
        return champion_changes([112], self.new, self.old)

    def test_more_health_is_a_buff(self):
        changes = self.score_for({"hp": 600}, {"hp": 660})

        self.assertEqual(changes[112]["status"], "buff")
        self.assertAlmostEqual(changes[112]["score"], 10.0)

    def test_less_attack_damage_is_a_nerf(self):
        changes = self.score_for({"attack_damage": 60}, {"attack_damage": 57})

        self.assertEqual(changes[112]["status"], "nerf")
        self.assertAlmostEqual(changes[112]["score"], -5.0)

    def test_mixed_changes_add_up(self):
        # +10% health and -5% armor = +5 in total, so the champion is buffed.
        changes = self.score_for({"hp": 600, "armor": 30}, {"hp": 660, "armor": 28.5})

        self.assertEqual(changes[112]["status"], "buff")
        self.assertAlmostEqual(changes[112]["score"], 5.0)
        self.assertEqual(len(changes[112]["lines"]), 2)

    def test_line_shows_old_and_new_value(self):
        changes = self.score_for({"hp": 600}, {"hp": 660})

        self.assertEqual(changes[112]["lines"], ["Health 600 → 660"])

    def test_unchanged_champion_is_not_listed(self):
        self.assertEqual(self.score_for({}, {}), {})

    def test_no_older_patch_gives_no_changes(self):
        make_champion_stats(self.new, self.champ)

        self.assertEqual(champion_changes([112], self.new, None), {})


class ItemScoreTests(TestCase):
    """item_changes(): more of a stat is a buff, a higher price is a nerf."""

    def setUp(self):
        self.old = Patch.objects.create(patch_id="16.21.1", patch_order=1)
        self.new = Patch.objects.create(patch_id="16.22.1", patch_order=2)
        self.item = Item.objects.create(item_id=3089, item_name="Rabadon's Deathcap")

    def test_higher_price_is_a_nerf(self):
        make_item_stats(self.old, self.item, gold_total=3500)
        make_item_stats(self.new, self.item, gold_total=3600)

        changes = item_changes([3089], self.new, self.old)

        self.assertEqual(changes[3089]["status"], "nerf")
        self.assertEqual(changes[3089]["lines"], ["Price 3500 → 3600"])

    def test_more_ability_power_is_a_buff(self):
        make_item_stats(self.old, self.item, stats={"FlatMagicDamageMod": 120})
        make_item_stats(self.new, self.item, stats={"FlatMagicDamageMod": 130})

        changes = item_changes([3089], self.new, self.old)

        self.assertEqual(changes[3089]["status"], "buff")
        self.assertEqual(changes[3089]["name"], "Rabadon's Deathcap")

    def test_percent_stats_are_shown_as_percent(self):
        make_item_stats(self.old, self.item, stats={"PercentAttackSpeedMod": 0.25})
        make_item_stats(self.new, self.item, stats={"PercentAttackSpeedMod": 0.30})

        changes = item_changes([3089], self.new, self.old)

        self.assertEqual(changes[3089]["lines"], ["Attack speed 25% → 30%"])


class SummarizeTests(TestCase):
    """summarize() calculates the profile numbers in one query."""

    def setUp(self):
        self.player = Player.objects.create(
            player_id="test-puuid", player_username="Tester", player_tag="EUNE", player_region="eun1",
        )
        self.number = 0

    def add_game(self, win, kills, deaths, assists, cs, seconds, remake=False):
        self.number += 1
        match = Match.objects.create(
            match_id=f"EUN1_{self.number}", match_duration=seconds,
            match_start=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )
        MatchPlayer.objects.create(
            matchplayer_match=match, matchplayer_player=self.player, win=win,
            kills=kills, deaths=deaths, assists=assists, cs=cs,
            raw={"gameEndedInEarlySurrender": remake},
        )

    def test_win_rate_kda_and_cs_per_minute(self):
        self.add_game(win=True, kills=10, deaths=2, assists=5, cs=200, seconds=1200)
        self.add_game(win=False, kills=2, deaths=6, assists=3, cs=160, seconds=1200)

        result = summarize(MatchPlayer.objects.counted())

        self.assertEqual(result["games"], 2)
        self.assertEqual(result["wins"], 1)
        self.assertEqual(result["win_rate"], 50)
        self.assertEqual(result["kda"], 2.5)       # (12 + 8) / 8
        self.assertEqual(result["cs_min"], 9.0)    # 360 cs / 40 minutes

    def test_remakes_are_not_counted(self):
        self.add_game(win=True, kills=5, deaths=1, assists=5, cs=150, seconds=1500)
        self.add_game(win=False, kills=0, deaths=0, assists=0, cs=10, seconds=200, remake=True)

        result = summarize(MatchPlayer.objects.counted())

        self.assertEqual(result["games"], 1)
        self.assertEqual(result["win_rate"], 100)

    def test_no_games_gives_none(self):
        self.assertIsNone(summarize(MatchPlayer.objects.counted()))


class NewestPatchTests(TestCase):
    """The newest patch has the highest patch_order."""

    def test_newest_and_previous_patch(self):
        Patch.objects.create(patch_id="16.20.1", patch_order=1)
        Patch.objects.create(patch_id="16.22.1", patch_order=3)
        Patch.objects.create(patch_id="16.21.1", patch_order=2)

        newest, previous = newest_two_patches()

        self.assertEqual(newest.patch_id, "16.22.1")
        self.assertEqual(previous.patch_id, "16.21.1")

    def test_only_one_patch_has_no_previous(self):
        Patch.objects.create(patch_id="16.22.1", patch_order=1)

        newest, previous = newest_two_patches()

        self.assertEqual(newest.patch_id, "16.22.1")
        self.assertIsNone(previous)


ACCOUNT = {"puuid": "test-puuid", "gameName": "Tester", "tagLine": "KR1"}


@patch("matches.player_views.get_account", return_value=ACCOUNT)
class ServerTests(TestCase):
    """find_player() must respect the server. A Riot ID is global, but a League
    account belongs to one server. The Riot API is replaced by a mock here."""

    def test_stored_player_on_the_same_server_is_found(self, mock_account):
        Player.objects.create(player_id="test-puuid", player_username="Tester", player_tag="KR1",
                              player_region="kr", player_last_updated=datetime(2026, 11, 1, tzinfo=timezone.utc))

        self.assertEqual(find_player("kr", "Tester", "KR1").player_id, "test-puuid")

    def test_stored_player_on_a_different_server_gives_404(self, mock_account):
        Player.objects.create(player_id="test-puuid", player_username="Tester", player_tag="KR1",
                              player_region="kr", player_last_updated=datetime(2026, 11, 1, tzinfo=timezone.utc))

        with self.assertRaises(Http404):
            find_player("eun1", "Tester", "KR1")

    @patch("matches.player_views.call_command", side_effect=CommandError("no League account on EUN1"))
    def test_new_player_without_account_on_server_gives_404(self, mock_command, mock_account):
        with self.assertRaises(Http404):
            find_player("eun1", "Tester", "KR1")
        self.assertFalse(Player.objects.exists())
