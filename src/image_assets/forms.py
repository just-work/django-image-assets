from django import forms
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from image_assets import models


class AssetForm(forms.ModelForm):
    """ Asset form with restricted asset_type choices."""
    asset_type = forms.ModelChoiceField(
        queryset=models.get_asset_type_model().objects.distinct('id'),
        label=_("Asset Type")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        related = self.instance.related
        qs = models.get_asset_type_model().objects.get_for_model(related)
        self.fields["asset_type"].queryset = qs


class AssetFormSet(BaseGenericInlineFormSet):
    model = models.get_asset_model()

    def __init__(self, data=None, files=None, instance=None, save_as_new=False,
                 prefix=None, queryset=None, **kwargs):
        if not kwargs.get('initial') and not (data or files):
            kwargs['initial'] = self.construct_initial(instance)
        super().__init__(data, files, instance, save_as_new, prefix, queryset,
                         **kwargs)

    @staticmethod
    def construct_initial(instance):
        asset_type_model = models.get_asset_type_model()
        initial = []
        for asset_type in asset_type_model.objects.get_required(instance):
            initial.append({'asset_type': asset_type.pk})
        return initial

    def add_fields(self, form, index):
        super().add_fields(form, index)
        qs = models.get_asset_type_model().objects.get_for_model(self.instance)
        form.fields['asset_type'].queryset = qs

    def clean(self):
        super().clean()
        if not self.is_valid():
            return
        duplicated_asset_types = set()
        added_asset_types = set()
        qs = models.get_asset_type_model().objects.get_required(self.instance)
        required_asset_types = set(qs.values_list('pk', flat=True))
        for asset_data in self.cleaned_data:
            active = asset_data.get('active')
            if not active:
                # We only perform extra validation for active assets
                continue
            asset_type = asset_data.get('asset_type')
            if not asset_type:
                # empty field value
                continue
            if asset_type.pk in added_asset_types:
                # there are more than one active assets of this type
                duplicated_asset_types.add(asset_type.pk)
            # track whether there are active assets for all required types
            added_asset_types.add(asset_type.pk)

        errors = []
        missing = required_asset_types - added_asset_types
        if missing:
            qs = models.get_asset_type_model().objects.filter(
                pk__in=missing).values_list('slug', flat=True)
            msg = _("Missing required asset types: %s")
            errors.append(ValidationError(msg % ', '.join(qs)))
        if duplicated_asset_types:
            qs = models.get_asset_type_model().objects.filter(
                pk__in=duplicated_asset_types).values_list('slug', flat=True)
            msg = _("Duplicate active assets for types: %s")
            errors.append(ValidationError(msg % ', '.join(qs)))
        if errors:
            raise ValidationError(errors)
