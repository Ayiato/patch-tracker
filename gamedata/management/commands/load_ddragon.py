import time

import requests
from django.core.management.base import BaseCommand

from gamedata.models import Patch, Tag, Champion, PatchChampion, Item, PatchItem, Ability, Skin
from matches.models import Queue

DDRAGON = "https://ddragon.leagueoflegends.com"

session = requests.Session()

def get_json(url):
    for attempt in range(3):
        try:
            return session.get(url, timeout=10).json()
        except requests.exceptions.RequestException:
            if attempt == 2:
                raise
            time.sleep(2)

class Command(BaseCommand):
    help = "Load patches, champions, tags and stats from Data Dragon"

    def handle(self, *args, **options):



        versions = self.load_patches(10)
        self.stdout.write(f"Loaded {len(versions)} patches")
        if Patch.objects.filter(patch_id=versions[0]).exists():
            print("Already up to date, nothing else to load.")
            return

        champions = self.load_champions(versions[0])
        self.stdout.write(f"Loaded {len(champions)} champions")
        self.load_patch_champion(versions)
        self.stdout.write(f"Loaded PatchChampions for {len(versions)} versions")
        self.load_items(versions)
        self.stdout.write(f"Loaded items for {len(versions)} versions")
        self.load_patch_items(versions)
        self.stdout.write(f"Loaded PatchItems for {len(versions)} versions")
        queues = self.load_queues()
        self.stdout.write(f"Loaded {len(queues)} queues")
        self.load_abilities_skins(versions[0])


    def load_patches(self, how_many):
        all_versions = get_json(f"{DDRAGON}/api/versions.json")
        for i, version in enumerate(all_versions[:how_many]):
            Patch.objects.update_or_create(
                patch_id = version,
                defaults = {"patch_order": len(all_versions) - i},
            )
        return all_versions[:how_many]

    def load_champions(self, latest_version):
        all_champions = get_json(f"{DDRAGON}/cdn/{latest_version}/data/en_US/champion.json")
        for champion in all_champions["data"].values():
            if int(champion["key"]) >= 60000:
                continue
            lore_url = f"{DDRAGON}/cdn/{latest_version}/data/en_US/champion/{champion["id"]}.json"
            lore = get_json(lore_url)["data"][champion["id"]]["lore"]
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
            all_champions = get_json(url)

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

    def load_items(self, versions):
        for version in reversed(versions):
            url = f"{DDRAGON}/cdn/{version}/data/en_US/item.json"
            all_items = get_json(url)
            for key in all_items["data"]:
                if int(key) >= 10000:
                    continue
                values = all_items["data"][key]
                if not (values["maps"].get("11") and values["gold"]["purchasable"]):
                    continue
                Item.objects.update_or_create(
                    item_id=int(key),
                    defaults={"item_name": values["name"],
                              "item_plaintext": values.get("plaintext", "")}
                )

    def load_patch_items(self, versions):
        for version in versions:
            if PatchItem.objects.filter(patchitem_patch_id=version).exists():
                continue

            url = f"{DDRAGON}/cdn/{version}/data/en_US/item.json"
            all_items = get_json(url)

            rows = []
            for key in all_items["data"]:
                if int(key) >= 10000:
                    continue
                values = all_items["data"][key]
                if not (values["maps"].get("11") and values["gold"]["purchasable"]):
                    continue
                rows.append(PatchItem(
                    patchitem_patch_id=version,
                    patchitem_item_id=int(key),
                    gold_base=values["gold"]["base"],
                    gold_total=values["gold"]["total"],
                    description=values.get("description", ""),
                    stats=values.get("stats", {}),
                ))

            PatchItem.objects.bulk_create(rows, ignore_conflicts=True)

    def load_queues(self):
        response = get_json("https://static.developer.riotgames.com/docs/lol/queues.json")
        for queue in response:
            queue_obj, _ = Queue.objects.update_or_create(queue_id=int(queue["queueId"]),
                                                          defaults={"queue_map": queue["map"],
                                                                    "queue_description": queue["description"],})

        return(response)

    def load_abilities_skins(self, version):
        types = ["Q", "W", "E", "R"]
        for champ in Champion.objects.all():
            url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion/{champ.champion_internal_name}.json"
            data = get_json(url)["data"][champ.champion_internal_name]

            passive = data["passive"]
            Ability.objects.update_or_create(
                ability_id = f"{champ.champion_internal_name}P",
                defaults={
                    "ability_champion": champ,
                    "ability_type": "P",
                    "ability_name": passive["name"],
                    "ability_description": passive["description"],
                    "ability_image": passive["image"]["full"]
                }
            )

            for type, spell in zip(types, data["spells"]):
                Ability.objects.update_or_create(ability_id = spell["id"],
                                                 defaults={
                                                     "ability_champion": champ,
                                                     "ability_type": type,
                                                     "ability_name": spell["name"],
                                                     "ability_description": spell["description"],
                                                     "ability_image": spell["image"]["full"],
                                                     "ability_cooldown": spell["cooldownBurn"],
                                                     "ability_range": spell["rangeBurn"],
                                                     "ability_cost": spell["costBurn"]
                                                 })
            for skin in data["skins"]:
                Skin.objects.update_or_create(
                    skin_id=skin["id"],
                    defaults={"skin_champion": champ,
                              "skin_name": skin["name"],
                              "skin_num": int(skin["num"]),
                              "skin_chromas": skin["chromas"]
                              },
                )