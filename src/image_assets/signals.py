from typing import Type

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from image_assets import models


# noinspection PyUnusedLocal
@receiver(pre_delete, sender=models.get_asset_model())
def move_asset_file_to_deleted_asset(
        sender, *, instance: models.Asset, **kwargs):
    """ When asset is deleted, it's file is moved to deleted asset instance."""
    models.get_deleted_asset_model().objects.create(
        image=instance.image,
        content_type_id=instance.content_type_id,
        object_id=instance.object_id,
        asset_type_id=instance.asset_type_id)


# noinspection PyUnusedLocal
@receiver(pre_delete, sender=models.get_deleted_asset_model())
def delete_asset_file_for_deleted_asset(
        sender, *, instance: models.DeletedAsset, **kwargs):
    """
    When deleted asset is deleted from db, it's file is purged from storage.
    """
    instance.image.delete(save=False)
