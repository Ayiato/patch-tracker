import requests
from django.core.management.base import BaseCommand
from gamedata.models import Patch, Tag, Champion, PatchChampion

DDRAGON = "https://ddragon.leagueoflegends.com"

class Command(BaseCommand):
    help = "Load patches, champions, tags and stats from Data Dragon"

    def handle(self, *args, **options):
        versions = self.load_patches(10)
        self.stdout.write(f"Loaded {len(versions)} patches")
        champions = self.load_champions(versions[0])
        self.stdout.write(f"Loaded {len(champions)} champions")
        self.load_patch_champion(versions)
        self.stdout.write(f"Loaded PatchChampions for {len(versions)}")


    def load_patches(self, how_many):
        all_versions = requests.get(f"{DDRAGON}/api/versions.json").json()
        for i, version in enumerate(all_versions[:how_many]):
            Patch.objects.update_or_create(
                patch_id = version,
                defaults = {"patch_order": len(all_versions) - i},
            )
        return all_versions[:how_many]

    def load_champions(self, latest_version):
        all_champions = requests.get(f"{DDRAGON}/cdn/{latest_version}/data/en_US/champion.json").json()
        for champion in all_champions["data"].values():
            if int(champion["key"]) >= 60000:
                continue
            lore_url = f"{DDRAGON}/cdn/{latest_version}/data/en_US/champion/{champion["id"]}.json"
            lore = requests.get(lore_url).json()["data"][champion["id"]]["lore"]
            champion_obj, _ = Champion.objects.update_or_create(
                champion_id = int(champion["key"]),
                defaults = {"champion_name": champion["name"],
                            "champion_internal_name": champion["id"],
                            "champion_title": champion["title"],
                            "champion_blurb": champion["blurb"],
                            "champion_partype": champion["partype"],
                            "champion_icon": champion["image"]["full"],
                            "champion_lore": lore}
            )
            for tag in champion["tags"]:
                tag_obj, _  = Tag.objects.get_or_create(tag_name = tag)
                champion_obj.champion_tags.add(tag_obj)
        return all_champions["data"].values()

    def load_patch_champion(self, versions):
        for version in versions:
            if PatchChampion.objects.filter(patchchampion_patch_id=version).exists():
                continue
            url = f"{DDRAGON}/cdn/{version}/data/en_US/champion.json"
            all_champions = requests.get(url).json()

            rows = []
            for champion in all_champions["data"].values():
                if int(champion["key"]) >= 60000:
                    continue
                info = champion["info"]
                stats = champion["stats"]
                rows.append(PatchChampion(
                    patchchampion_patch_id=version,
                    patchchampion_champion_id=int(champion["key"]),
                    attack=info["attack"],
                    defense=info["defense"],
                    magic=info["magic"],
                    difficulty=info["difficulty"],
                    hp=stats["hp"],
                    hp_per_level=stats["hpperlevel"],
                    mp=stats["mp"],
                    mp_per_level=stats["mpperlevel"],
                    move_speed=stats["movespeed"],
                    armor=stats["armor"],
                    armor_per_level=stats["armorperlevel"],
                    spell_block=stats["spellblock"],
                    spell_block_per_level=stats["spellblockperlevel"],
                    attack_range=stats["attackrange"],
                    hp_regen=stats["hpregen"],
                    hp_regen_per_level=stats["hpregenperlevel"],
                    mp_regen=stats["mpregen"],
                    mp_regen_per_level=stats["mpregenperlevel"],
                    crit=stats["crit"],
                    crit_per_level=stats["critperlevel"],
                    attack_damage=stats["attackdamage"],
                    attack_damage_per_level=stats["attackdamageperlevel"],
                    attack_speed=stats["attackspeed"],
                    attack_speed_per_level=stats["attackspeedperlevel"],
                ))
            PatchChampion.objects.bulk_create(rows, ignore_conflicts=True)


