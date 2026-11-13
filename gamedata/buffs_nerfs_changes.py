"""Raw stat differences between two patches, for champions and items.

These functions return every changed value with its old and new number. The web
pages use the scored version in matches/player_views.py (champion_changes and
item_changes), which also decides whether a change is a buff or a nerf.

"""

from gamedata.models import PatchChampion, PatchItem

CHAMPION_STATS = [
    "hp", "hp_per_level", "mp", "mp_per_level", "move_speed",
    "armor", "armor_per_level", "spell_block", "spell_block_per_level",
    "attack_range", "hp_regen", "hp_regen_per_level", "mp_regen",
    "mp_regen_per_level", "attack_damage", "attack_damage_per_level",
    "attack_speed", "attack_speed_per_level",
]


def buffs_nerfs_changes_champion(new_patch_id, old_patch_id, champion_id_list=None):
    """Compare the base stats of champions between two patches.

    Args:
        new_patch_id: Newer patch id, e.g. "16.21.1".
        old_patch_id: Older patch id.
        champion_id_list: Champions to check. Defaults to every champion in the newer patch.

    Returns:
        Tuple (changes, new_champions):
        changes: {internal_name: {stat: {"new": value, "old": value}}} for changed champions only.
        new_champions: internal names of champions that exist only in the newer patch.
    """
    new_champs = []
    current_champs = {}

    if champion_id_list is None:
        champion_id_list = PatchChampion.objects.filter(
            patchchampion_patch=new_patch_id
        ).values_list("patchchampion_champion_id", flat=True)

    for champion_id in champion_id_list:
        patchchampion_obj_new = PatchChampion.objects.filter(patchchampion_patch=new_patch_id, patchchampion_champion=champion_id).first()
        patchchampion_obj_old = PatchChampion.objects.filter(patchchampion_patch=old_patch_id, patchchampion_champion=champion_id).first()

        if patchchampion_obj_new is None:
            continue
        if patchchampion_obj_old is None:
            new_champs.append(patchchampion_obj_new.patchchampion_champion.champion_internal_name)
            continue

        champ_dict = {}
        for stat in CHAMPION_STATS:
            new_value = getattr(patchchampion_obj_new, stat)
            old_value = getattr(patchchampion_obj_old, stat)
            if new_value != old_value:
                champ_dict[stat] = {}
                champ_dict[stat]["new"] = new_value
                champ_dict[stat]["old"] = old_value

        if champ_dict:
            current_champs[patchchampion_obj_new.patchchampion_champion.champion_internal_name] = champ_dict

    return current_champs, new_champs


ITEM_GOLD_FIELDS = ["gold_total", "gold_base"]


def buffs_nerfs_changes_item(new_patch_id, old_patch_id, item_id_list=None):
    """Compare price, stats and description of items between two patches.

    Stats are compared key by key; a stat missing in one patch counts as 0.

    Args:
        new_patch_id: Newer patch id.
        old_patch_id: Older patch id.
        item_id_list: Items to check. Defaults to every item in the newer patch.

    Returns:
        Tuple (changes, new_items):
        changes: {item_name: {field_or_stat: {"new": value, "old": value}}} for changed items only.
        new_items: names of items that exist only in the newer patch.
    """
    new_items = []
    current_items = {}

    if item_id_list is None:
        item_id_list = PatchItem.objects.filter(
            patchitem_patch=new_patch_id
        ).values_list("patchitem_item_id", flat=True)

    for item_id in item_id_list:
        patchitem_obj_new = PatchItem.objects.filter(patchitem_patch=new_patch_id, patchitem_item=item_id).first()
        patchitem_obj_old = PatchItem.objects.filter(patchitem_patch=old_patch_id, patchitem_item=item_id).first()

        if patchitem_obj_new is None:
            continue
        if patchitem_obj_old is None:
            new_items.append(patchitem_obj_new.patchitem_item.item_name)
            continue

        item_dict = {}

        for field in ITEM_GOLD_FIELDS:
            new_value = getattr(patchitem_obj_new, field)
            old_value = getattr(patchitem_obj_old, field)
            if new_value != old_value:
                item_dict[field] = {"new": new_value, "old": old_value}

        new_stats = patchitem_obj_new.stats
        old_stats = patchitem_obj_old.stats
        for stat in set(new_stats) | set(old_stats):
            new_value = new_stats.get(stat, 0)
            old_value = old_stats.get(stat, 0)
            if new_value != old_value:
                item_dict[stat] = {"new": new_value, "old": old_value}

        if patchitem_obj_new.description != patchitem_obj_old.description:
            item_dict["description"] = {"new": patchitem_obj_new.description,
                                        "old": patchitem_obj_old.description}

        if item_dict:
            current_items[patchitem_obj_new.patchitem_item.item_name] = item_dict

    return current_items, new_items



def buffs_nerfs_changes_all(new_patch_id, old_patch_id, champion_id_list=None, item_id_list=None):
    """Champion and item differences between two patches in one call.

    Args:
        new_patch_id: Newer patch id.
        old_patch_id: Older patch id.
        champion_id_list: Optional champions to check (default: all).
        item_id_list: Optional items to check (default: all).

    Returns:
        Dict with "champions", "new_champions", "items" and "new_items", as returned
        by buffs_nerfs_changes_champion and buffs_nerfs_changes_item.
    """
    champion_changes, new_champs = buffs_nerfs_changes_champion(new_patch_id, old_patch_id, champion_id_list)
    item_changes, new_items = buffs_nerfs_changes_item(new_patch_id, old_patch_id, item_id_list)
    return {
        "champions": champion_changes,
        "new_champions": new_champs,
        "items": item_changes,
        "new_items": new_items,
    }
