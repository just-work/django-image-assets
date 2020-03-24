# noinspection PyPackageRequirements
import factory

from image_assets import models

AssetType = models.get_asset_type_model()
Asset = models.get_asset_model()

__all__ = ['AssetFactory', 'AssetTypeFactory']


class AssetTypeFactory(factory.DjangoModelFactory):
    class Meta:
        model = AssetType


class AssetFactory(factory.DjangoModelFactory):
    class Meta:
        model = Asset
