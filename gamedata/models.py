"""Models for static game data from Data Dragon.

Things that stay the same (a champion, an item) are separate from their values in
one patch (PatchChampion, PatchItem), so any two patches can be compared.

"""

from django.db import models
from django.forms import IntegerField


class Patch(models.Model):
    """A game version, e.g. "16.21.1". The newest patch has the highest patch_order."""
    patch_id = models.CharField(max_length=30, primary_key=True)
    patch_order = models.IntegerField(unique=True )

    def __str__(self):
        return f"{self.patch_id} ; {self.patch_order}"

class Tag(models.Model):
    """Champion class, e.g. "Mage" or "Tank"."""
    tag_name = models.CharField(max_length=20, primary_key=True)

    def __str__(self):
        return f"{self.tag_name}"

class Champion(models.Model):
    """A champion, keyed by Riot's numeric champion key.

    champion_internal_name is the Data Dragon id (e.g. "MonkeyKing" for Wukong),
    which image URLs and the per-champion data files use.
    """
    champion_id = models.IntegerField(primary_key=True)
    champion_name = models.CharField(max_length=50, unique=True )
    champion_internal_name = models.CharField(max_length=50, unique=True)
    champion_title = models.CharField(max_length=100 )
    champion_blurb = models.TextField()
    champion_partype = models.CharField(max_length=20 )
    champion_icon = models.CharField(max_length=100 )
    champion_tags = models.ManyToManyField(Tag, related_name="champions")
    champion_lore = models.TextField(blank=True)

    def splash_url(self):
        """URL of the default splash art."""
        return f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{self.champion_internal_name}_0.jpg"

    def __str__(self):
        return (f"{self.champion_name}")


class PatchChampion(models.Model):
    """Base stats of one champion in one patch. One row per (patch, champion)."""
    patchchampion_patch = models.ForeignKey(Patch, on_delete=models.CASCADE, related_name="champion_stats")
    patchchampion_champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name="patch_stats")

    attack = models.PositiveSmallIntegerField()
    defense = models.PositiveSmallIntegerField()
    magic = models.PositiveSmallIntegerField()
    difficulty = models.PositiveSmallIntegerField()

    hp = models.FloatField()
    hp_per_level = models.FloatField()
    mp = models.FloatField()
    mp_per_level = models.FloatField()
    move_speed = models.FloatField()
    armor = models.FloatField()
    armor_per_level = models.FloatField()
    spell_block = models.FloatField()
    spell_block_per_level = models.FloatField()
    attack_range = models.FloatField()
    hp_regen = models.FloatField()
    hp_regen_per_level = models.FloatField()
    mp_regen = models.FloatField()
    mp_regen_per_level = models.FloatField()
    crit = models.FloatField()
    crit_per_level = models.FloatField()
    attack_damage = models.FloatField()
    attack_damage_per_level = models.FloatField()
    attack_speed = models.FloatField()
    attack_speed_per_level = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["patchchampion_patch", "patchchampion_champion"], name="unique_patch_champion")
        ]

    def __str__(self):
        return f"{self.patchchampion_patch_id} ; {self.patchchampion_champion}"


class Item(models.Model):
    """A Summoner's Rift item that can be bought, keyed by Riot's item id."""
    item_id = models.IntegerField(primary_key=True)
    item_name = models.CharField(max_length=100)
    item_plaintext = models.TextField(blank=True)

    def __str__(self):
        return f"{self.item_name}"

class PatchItem(models.Model):
    """Price, stats and description of one item in one patch.

    stats is the raw Data Dragon dict, e.g. {"FlatMagicDamageMod": 30}. Some effects
    (lethality, ability haste, passives) only appear in the description.
    """
    patchitem_item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="patch_stats")
    patchitem_patch = models.ForeignKey(Patch, on_delete=models.CASCADE, related_name="item_stats")

    gold_base = models.IntegerField()
    gold_total = models.IntegerField()
    description = models.TextField(blank=True)
    stats = models.JSONField(default=dict)


    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["patchitem_patch", "patchitem_item"], name="unique_patch_item")]

    def icon_url(self):
        """URL of the item icon for this patch."""
        return f"https://ddragon.leagueoflegends.com/cdn/{self.patchitem_patch_id}/img/item/{self.patchitem_item_id}.png"

    def __str__(self):
        return f"{self.patchitem_patch_id} ; {self.patchitem_item}"


class Ability(models.Model):
    """A champion's passive (P) or spell (Q, W, E, R).

    ability_id is Riot's spell id; the passive has none, so it uses "<internal name>P".
    Cooldown, cost and range are text per rank, e.g. "9/8/7/6/5".
    """
    ability_id = models.CharField(max_length=50, primary_key=True)
    ability_champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name="abilities")
    ability_type = models.CharField(max_length=1)
    ability_name = models.CharField(max_length=100)
    ability_description = models.TextField()
    ability_cooldown = models.CharField(max_length=100)
    ability_cost = models.CharField(max_length=100)
    ability_range = models.CharField(max_length=100)
    ability_image = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ability_type", "ability_champion"], name="unique_ability_champion")
        ]
    def __str__(self):
        return f"{self.ability_id}"

class Skin(models.Model):
    """A champion skin. skin_num is the number used in splash and loading art URLs."""
    skin_id = models.CharField(max_length=20, primary_key=True)
    skin_champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name="skins")
    skin_num = models.IntegerField(default=1)
    skin_name = models.CharField(max_length=100)
    skin_chromas = models.BooleanField()

    class Meta:
        ordering = ["skin_num"]

    def __str__(self):
        return f"{self.skin_name}"
