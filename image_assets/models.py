from typing import Type

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.apps import apps
from image_assets import defaults


class AssetTypeManager(models.Manager):
    def get_for_model(self, model):
        if model is None:
            return self.all()
        ct = ContentType.objects.get_for_model(model)
        return self.filter(
            models.Q(required_for=ct) | models.Q(allowed_for=ct)).distinct()

    def get_required(self, instance):
        if instance is None:
            return self.all()
        ct = ContentType.objects.get_for_model(instance)
        required = self.filter(required_for=ct)
        if instance.pk is None:
            return required
        existing = get_asset_model().objects.filter(
            active=True, content_type=ct, object_id=instance.pk).values(
            'asset_type')
        return required.exclude(pk__in=existing)


class AssetType(models.Model):
    class Meta:
        abstract = defaults.ASSET_TYPE_MODEL != 'image_assets.AssetType'

    objects = AssetTypeManager()

    slug = models.SlugField(unique=True)

    required_for = models.ManyToManyField(
        ContentType, blank=True, related_name='required_asset_types',
        related_query_name='required_asset_types')
    allowed_for = models.ManyToManyField(
        ContentType, blank=True, related_name='allowed_asset_types',
        related_query_name='allowed_asset_types')

    def __str__(self):
        return self.slug


def get_asset_type_model() -> Type[AssetType]:
    app_label, model_name = defaults.ASSET_TYPE_MODEL.split('.')
    return apps.get_registered_model(app_label, model_name)


class Asset(models.Model):
    class Meta:
        abstract = defaults.ASSET_MODEL != 'image_assets.Asset'
    image = models.ImageField()
    asset_type = models.ForeignKey(AssetType, models.CASCADE)
    active = models.BooleanField(default=True)

    content_type = models.ForeignKey(ContentType, models.CASCADE)
    object_id = models.IntegerField()
    related = GenericForeignKey()


def get_asset_model() -> Type[Asset]:
    app_label, model_name = defaults.ASSET_MODEL.split('.')
    return apps.get_registered_model(app_label, model_name)


class DeletedAsset(models.Model):
    content_type = models.ForeignKey(ContentType, models.CASCADE)
    object_id = models.IntegerField()
    asset = GenericForeignKey()  # To Asset and subclasses

    class Meta:
        abstract = defaults.DELETED_ASSET_MODEL != 'image_asset.DeletedAsset'
        unique_together = ('content_type', 'object_id')
