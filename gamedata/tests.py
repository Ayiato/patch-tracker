"""Tests for the raw stat differences between two patches (buffs_nerfs_changes.py).

Run with: python manage.py test gamedata
Django creates an empty test database, so these tests never touch the real data.
"""

from django.test import TestCase

from gamedata.buffs_nerfs_changes import (
    buffs_nerfs_changes_champion,
    buffs_nerfs_changes_item,
    buffs_nerfs_changes_all,
)
from gamedata.models import Patch, Champion, PatchChampion, Item, PatchItem


# Base stats for a test champion. Each test changes only the stats it needs.
BASE_STATS = {
    "attack": 5, "defense": 5, "magic": 5, "difficulty": 5,
    "hp": 600, "hp_per_level": 100, "mp": 300, "mp_per_level": 40,
    "move_speed": 330, "armor": 30, "armor_per_level": 4.5,
    "spell_block": 30, "spell_block_per_level": 1.3, "attack_range": 550,
    "hp_regen": 3.5, "hp_regen_per_level": 0.55, "mp_regen": 8,
    "mp_regen_per_level": 0.8, "crit": 0, "crit_per_level": 0,
    "attack_damage": 60, "attack_damage_per_level": 3,
    "attack_speed": 0.625, "attack_speed_per_level": 2,
}


def make_champion(champion_id, name):
    """Create a champion with the minimum required fields."""
    return Champion.objects.create(
        champion_id=champion_id, champion_name=name, champion_internal_name=name,
        champion_title="", champion_blurb="", champion_partype="Mana", champion_icon="",
    )


def make_champion_stats(patch, champion, **changes):
    """Create one PatchChampion row: BASE_STATS with the given changes."""
    return PatchChampion.objects.create(
        patchchampion_patch=patch, patchchampion_champion=champion,
        **{**BASE_STATS, **changes},
    )


def make_item_stats(patch, item, gold_total=3000, stats=None, description="Item text"):
    """Create one PatchItem row."""
    return PatchItem.objects.create(
        patchitem_patch=patch, patchitem_item=item, gold_base=800,
        gold_total=gold_total, stats=stats or {}, description=description,
    )


class ChampionChangesTests(TestCase):
    """buffs_nerfs_changes_champion compares the base stats of each champion."""

    def setUp(self):
        self.old = Patch.objects.create(patch_id="16.21.1", patch_order=1)
        self.new = Patch.objects.create(patch_id="16.22.1", patch_order=2)
        self.ahri = make_champion(103, "Ahri")
        self.jinx = make_champion(222, "Jinx")

    def test_unchanged_champion_is_not_listed(self):
        make_champion_stats(self.old, self.ahri)
        make_champion_stats(self.new, self.ahri)

        changes, new_champions = buffs_nerfs_changes_champion("16.22.1", "16.21.1")

        self.assertEqual(changes, {})
        self.assertEqual(new_champions, [])

    def test_changed_stat_has_old_and_new_value(self):
        make_champion_stats(self.old, self.jinx, hp=630)
        make_champion_stats(self.new, self.jinx, hp=610)

        changes, _ = buffs_nerfs_changes_champion("16.22.1", "16.21.1")

        self.assertEqual(changes, {"Jinx": {"hp": {"new": 610, "old": 630}}})

    def test_only_changed_stats_are_listed(self):
        make_champion_stats(self.old, self.jinx, hp=630, armor=26)
        make_champion_stats(self.new, self.jinx, hp=610, armor=26)

        changes, _ = buffs_nerfs_changes_champion("16.22.1", "16.21.1")

        self.assertEqual(list(changes["Jinx"]), ["hp"])

    def test_champion_only_in_new_patch_is_a_new_champion(self):
        make_champion_stats(self.new, self.ahri)

        changes, new_champions = buffs_nerfs_changes_champion("16.22.1", "16.21.1")

        self.assertEqual(changes, {})
        self.assertEqual(new_champions, ["Ahri"])


class ItemChangesTests(TestCase):
    """buffs_nerfs_changes_item compares price, stats and description of each item."""

    def setUp(self):
        self.old = Patch.objects.create(patch_id="16.21.1", patch_order=1)
        self.new = Patch.objects.create(patch_id="16.22.1", patch_order=2)
        self.rabadon = Item.objects.create(item_id=3089, item_name="Rabadon's Deathcap")

    def test_price_change_is_listed(self):
        make_item_stats(self.old, self.rabadon, gold_total=3500)
        make_item_stats(self.new, self.rabadon, gold_total=3600)

        changes, _ = buffs_nerfs_changes_item("16.22.1", "16.21.1")

        self.assertEqual(changes["Rabadon's Deathcap"]["gold_total"], {"new": 3600, "old": 3500})

    def test_missing_stat_counts_as_zero(self):
        make_item_stats(self.old, self.rabadon, stats={})
        make_item_stats(self.new, self.rabadon, stats={"FlatMagicDamageMod": 130})

        changes, _ = buffs_nerfs_changes_item("16.22.1", "16.21.1")

        self.assertEqual(changes["Rabadon's Deathcap"]["FlatMagicDamageMod"], {"new": 130, "old": 0})

    def test_description_change_is_listed(self):
        make_item_stats(self.old, self.rabadon, description="+30% AP")
        make_item_stats(self.new, self.rabadon, description="+35% AP")

        changes, _ = buffs_nerfs_changes_item("16.22.1", "16.21.1")

        self.assertIn("description", changes["Rabadon's Deathcap"])

    def test_item_only_in_new_patch_is_a_new_item(self):
        make_item_stats(self.new, self.rabadon)

        changes, new_items = buffs_nerfs_changes_item("16.22.1", "16.21.1")

        self.assertEqual(changes, {})
        self.assertEqual(new_items, ["Rabadon's Deathcap"])


class AllChangesTests(TestCase):
    """buffs_nerfs_changes_all returns champions and items in one dict."""

    def test_result_has_all_four_keys(self):
        Patch.objects.create(patch_id="16.21.1", patch_order=1)
        Patch.objects.create(patch_id="16.22.1", patch_order=2)

        result = buffs_nerfs_changes_all("16.22.1", "16.21.1")

        self.assertEqual(set(result), {"champions", "new_champions", "items", "new_items"})
