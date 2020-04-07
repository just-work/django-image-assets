from typing import Type, List, Callable

from PIL import Image
from bitfield import BitField
from django.apps import apps
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.base import ModelBase
from django.db.models.fields.files import FieldFile
from django.utils.translation import gettext_lazy as _

from image_assets import defaults, validators


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
    formats = BitField(verbose_name=_('Formats'), flags=FORMAT_CHOICES,
                       default=0)
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

    # noinspection PyUnusedLocal
    def get_validators(self, file: Image.Image
                       ) -> List[Callable[[Image.Image], List[str]]]:
        """
        Returns list of checks to run against file.

        :param file: opened image file.
        :return: list of check methods.
        """
        return [
            self.validate_format,
            self.validate_dimensions,
            self.validate_aspect,
        ]

    def validate_max_size(self, value: FieldFile) -> List[str]:
        """ Validate max file size."""
        if (self.max_size and value.size and
                self.max_size < value.size):
            msg = _('File size must be not greater than %s')
            return [msg % self.max_size]
        return []

    def validate_format(self, file: Image.Image) -> List[str]:
        """ Validate allowed format list."""
        fmt = file.format.lower()
        set_flags = dict(self.formats.items())
        if self.formats and not set_flags.get(fmt):
            msg = _('Image format must be one of %s')
            formats = ','.join([self.formats.get_label(k)
                                for k, v in self.formats.items() if v])
            return [msg % formats]
        return []

    def validate_dimensions(self, file: Image.Image) -> List[str]:
        """ Validate minimum image width and height."""
        errors = []
        # image width
        if file.width and self.min_width > file.width:
            msg = _('Image width must be not less than %s')
            errors.append(msg % self.min_width)
        # image height
        if file.height and self.min_height > file.height:
            msg = _('Image height must be not less than %s')
            errors.append(msg % self.min_height)
        return errors

    def validate_aspect(self, file: Image.Image) -> List[str]:
        """ Validate image aspect ratio with accuracy."""
        if not (file.width and file.height and self.aspect):
            return []
        image_aspect = file.width / file.height
        delta = abs(image_aspect - self.aspect)
        if self.accuracy == 0:
            if image_aspect != self.aspect:
                msg = _('Image aspect must be %s')
                return [msg % self.aspect]
        elif round(delta / self.accuracy) > 1:
            # round at scale of accuracy
            msg = _('Image aspect must be %(aspect)s ± %(accuracy)s')
            args = {
                'aspect': self.aspect,
                'accuracy': self.accuracy
            }
            return [msg % args]
        return []


def get_asset_type_model() -> Type[AssetType]:
    app_label, model_name = defaults.ASSET_TYPE_MODEL.split('.')
    return apps.get_registered_model(app_label, model_name)


class Asset(models.Model):
    image = models.ImageField(
        verbose_name=_('Image'), validators=[validators.AssetValidator()])
    asset_type = models.ForeignKey(
        AssetType, models.CASCADE, verbose_name=_('Asset Type'))
    active = models.BooleanField(verbose_name=_('Active'), default=True)

    content_type = models.ForeignKey(
        ContentType, models.CASCADE, verbose_name=_('Content Type'))
    object_id = models.IntegerField(verbose_name=_('Object ID'))
    related = GenericForeignKey()

    class Meta:
        abstract = defaults.ASSET_MODEL != 'image_assets.Asset'
        verbose_name = _('Asset')
        verbose_name_plural = _('Assets')
        constraints = (
            models.UniqueConstraint(
                fields=('asset_type', 'content_type', 'object_id'),
                name='unique_active_asset',
                condition=models.Q(active=True)),
        )

    def __str__(self):
        if self.content_type_id is None:
            return str(self._meta.verbose_name)
        ct = ContentType.objects.get_for_id(self.content_type_id)
        model = ct.model_class()
        # noinspection PyProtectedMember
        return f'{model._meta.verbose_name} #{self.object_id}'


def get_asset_model() -> Type[Asset]:
    app_label, model_name = defaults.ASSET_MODEL.split('.')
    return apps.get_registered_model(app_label, model_name)


class DeletedAsset(models.Model):
    image = models.ImageField(verbose_name=_('Image'))
    asset_type = models.ForeignKey(
        defaults.ASSET_TYPE_MODEL, models.CASCADE, verbose_name=_('Asset Type'))

    content_type = models.ForeignKey(
        ContentType, models.CASCADE, verbose_name=_('Content Type'))
    object_id = models.IntegerField(verbose_name=_('Object ID'))
    related = GenericForeignKey()

    class Meta:
        abstract = defaults.DELETED_ASSET_MODEL != 'image_assets.DeletedAsset'
        verbose_name = _('Deleted Asset')
        verbose_name_plural = _('Deleted Assets')

    def __str__(self):
        if self.content_type_id is None:
            return str(self._meta.verbose_name)
        ct = ContentType.objects.get_for_id(self.content_type_id)
        model = ct.model_class()
        # noinspection PyProtectedMember
        return f'{model._meta.verbose_name} #{self.object_id}'

    def recover(self):
        """ Восстанавливает удаленный ассет."""
        asset = get_asset_model().objects.create(
            asset_type_id=self.asset_type_id,
            content_type_id=self.content_type_id,
            object_id=self.object_id,
            image=self.image,
            active=False)
        qs = get_deleted_asset_model().objects.filter(pk=self.pk)
        # skip sending pre_delete/post_delete signals to prevent file removal.
        # noinspection PyProtectedMember
        qs._raw_delete(qs.db)
        return asset


def get_deleted_asset_model() -> Type[DeletedAsset]:
    app_label, model_name = defaults.DELETED_ASSET_MODEL.split('.')
    return apps.get_registered_model(app_label, model_name)
