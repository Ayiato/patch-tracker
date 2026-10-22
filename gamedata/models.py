from django.db import models

class Patch(models.Model):
    patch_id = models.CharField(max_length=30, primary_key=True)
    patch_order = models.IntegerField(unique=True )

    def __str__(self):
        return f"{self.patch_id} ; {self.patch_order}"

class Tag(models.Model):
    tag_name = models.CharField(max_length=20, primary_key=True)

    def __str__(self):
        return f"{self.tag_name}"

class Champion(models.Model):
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
        return f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{self.champion_internal_name}_0.jpg"

    def __str__(self):
        return (f"{self.champion_name} ; "
                f"{self.champion_internal_name} ; "
                f"{self.champion_title} ; "
                f"{self.champion_blurb} ; "
                f"{self.champion_partype} ; "
                f"{self.champion_icon} ; ")


class PatchChampion(models.Model):
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
        return f"{self.patchchampion_patch} ; {self.patchchampion_champion}"