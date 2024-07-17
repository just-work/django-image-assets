from bitfield import BitField
from bitfield.forms import BitFieldCheckboxSelectMultiple
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from image_assets import models, forms


@admin.register(models.get_asset_type_model())
class AssetTypeAdmin(admin.ModelAdmin):
    formfield_overrides = {
        BitField: {'widget': BitFieldCheckboxSelectMultiple},
    }


class AssetsInline(GenericTabularInline):
    model = models.get_asset_model()
    formset = forms.AssetFormSet
