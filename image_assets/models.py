from typing import Type

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.apps import apps
from django.db.models.base import ModelBase
from django.db.models.fields.files import ImageFieldFile
from django.utils.translation import gettext_lazy as _
from PIL import Image
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
        if instance.pk is None or isinstance(instance, ModelBase):
            return required
        existing = get_asset_model().objects.filter(
            active=True, content_type=ct, object_id=instance.pk).values(
            'asset_type')
        return required.exclude(pk__in=existing)


class AssetType(models.Model):
    JPEG = 'jpeg'
    PNG = 'png'
    FORMAT_CHOICES = (
        (JPEG, 'JPEG'),
        (PNG, 'PNG')
    )

    slug = models.SlugField(verbose_name=_("Slug"), unique=True)
    format = models.CharField(
        verbose_name=_('Image Format'), max_length=4, choices=FORMAT_CHOICES)
    min_width = models.IntegerField(
        verbose_name=_('Min Width'), default=0)
    min_height = models.IntegerField(
        verbose_name=_('Min Height'), default=0)
    aspect = models.FloatField(
        verbose_name=_('Aspect'), default=0)
    accuracy = models.FloatField(
        verbose_name=_('Aspect accuracy'), default=0.01)
    max_size = models.IntegerField(
        verbose_name=_('Max file size'), default=0)

    required_for = models.ManyToManyField(
        ContentType, blank=True, verbose_name=_('Required for'),
        related_name='required_asset_types',
        related_query_name='required_asset_types')
    allowed_for = models.ManyToManyField(
        ContentType, blank=True, verbose_name=_('Allowed for'),
        related_name='allowed_asset_types',
        related_query_name='allowed_asset_types')

    class Meta:
        abstract = defaults.ASSET_TYPE_MODEL != 'image_assets.AssetType'
        verbose_name = _('Asset Type')
        verbose_name_plural = _('Asset Types')

    objects = AssetTypeManager()

    def __str__(self):
        return self.slug

    @classmethod
    def validate_asset(cls, value: ImageFieldFile):
        asset = value.instance
        if asset.asset_type_id is None:
            # asset type not filled, no data to validate
            return
        errors = []
        asset_type: AssetType = asset.asset_type

        # validate file size
        if (asset_type.max_size and value.size and
                asset_type.max_size < value.size):
            msg = _('File size must be not greater than %s')
            errors.append(msg % asset_type.max_size)

        # open image and validate it's content
        with Image.open(value.file) as image:  # type: Image.Image
            # internal image format
            if image.format.lower() != asset_type.format:
                msg = _('Image format must be %s')
                errors.append(msg % asset_type.format)
            # image width
            if image.width and asset_type.min_width > image.width:
                msg = _('Image width must be not less than %s')
                errors.append(msg % asset_type.min_width)
            # image height
            if image.height and asset_type.min_height > image.height:
                msg = _('Image height must be not less than %s')
                errors.append(msg % asset_type.min_height)
            if image.width and image.height and asset_type.aspect:
                image_aspect = image.width / image.height
                delta = image_aspect - asset_type.aspect
                if asset_type.accuracy == 0:
                    if image_aspect != asset_type.aspect:
                        msg = _('Image aspect must be %s')
                        errors.append(msg % asset_type.aspect)
                elif round(delta / asset_type.accuracy) > 1:
                    # round at scale of accuracy
                    msg = _('Image aspect must be %(aspect)s ± %(accuracy)s')
                    args = {
                        'aspect': asset_type.aspect,
                        'accuracy': asset_type.accuracy}
                    errors.append(msg % args)

        if errors:
            raise ValidationError(errors)


def get_asset_type_model() -> Type[AssetType]:
    app_label, model_name = defaults.ASSET_TYPE_MODEL.split('.')
    return apps.get_registered_model(app_label, model_name)


class Asset(models.Model):
    class Meta:
        abstract = defaults.ASSET_MODEL != 'image_assets.Asset'
        verbose_name = _('Asset')
        verbose_name_plural = _('Assets')

    image = models.ImageField(
        verbose_name=_('Image'), validators=[AssetType.validate_asset])
    asset_type = models.ForeignKey(
        AssetType, models.CASCADE, verbose_name=_('Asset Type'))
    active = models.BooleanField(verbose_name=_('Active'), default=True)

    content_type = models.ForeignKey(
        ContentType, models.CASCADE, verbose_name=_('Content Type'))
    object_id = models.IntegerField(verbose_name=_('Object ID'))
    related = GenericForeignKey()


def get_asset_model() -> Type[Asset]:
    app_label, model_name = defaults.ASSET_MODEL.split('.')
    return apps.get_registered_model(app_label, model_name)


class DeletedAsset(models.Model):
    image = models.ImageField()
    asset_type = models.ForeignKey(defaults.ASSET_TYPE_MODEL, models.CASCADE)

    content_type = models.ForeignKey(ContentType, models.CASCADE)
    object_id = models.IntegerField()
    related = GenericForeignKey()

    class Meta:
        abstract = defaults.DELETED_ASSET_MODEL != 'image_assets.DeletedAsset'
        unique_together = ('content_type', 'object_id')
        verbose_name = _('Deleted Asset')
        verbose_name_plural = _('Deleted Assets')


def get_deleted_asset_model() -> Type[DeletedAsset]:
    app_label, model_name = defaults.DELETED_ASSET_MODEL.split('.')
    return apps.get_registered_model(app_label, model_name)
