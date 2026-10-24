import requests
from django.core.management.base import BaseCommand
from gamedata.models import Patch, Tag, Champion, PatchChampion

DDRAGON = "https://ddragon.leagueoflegends.com"

class Command(BaseCommand):
    help = "Load patches, champions, tags and stats from Data Dragon"

    def handle(self, *args, **options):
        versions = self.load_patches(10)
        self.stdout.write(f"Loaded {len(versions)} patches")


    def load_patches(self, how_many):
        all_versions = requests.get(f"{DDRAGON}/api/versions.json").json()
        for i, version in enumerate(all_versions[:how_many]):
            Patch.objects.update_or_create(
                patch_id=version,
                defaults={"patch_order": len(all_versions) - i},
            )
        return all_versions[:how_many]