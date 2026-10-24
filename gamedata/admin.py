from django.contrib import admin

# Register your models here.

from .models import Patch, Tag, Champion, PatchChampion

admin.site.register(Patch)
admin.site.register(Tag)
admin.site.register(Champion)
admin.site.register(PatchChampion)