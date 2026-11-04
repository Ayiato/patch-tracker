from django.contrib import admin

# Register your models here.

from .models import Patch, Tag, Champion, PatchChampion, Item, PatchItem, Ability, Skin

admin.site.register(Patch)
admin.site.register(Tag)
admin.site.register(Champion)
admin.site.register(PatchChampion)
admin.site.register(Item)
admin.site.register(PatchItem)
admin.site.register(Ability)
admin.site.register(Skin)
