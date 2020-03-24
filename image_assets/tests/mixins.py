import io
from typing import Tuple, Optional, Iterable

from PIL import Image
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.base import ModelBase, Model

from image_assets import models

AssetType = models.get_asset_type_model()
Asset = models.get_asset_model()

try:
    from image_assets.tests.factories import *
except ImportError:  # pragma: no cover
    # factory-boy not installed, no default fuzzy attributes will be available
    AssetTypeFactory = AssetType.objects
    AssetFactory = Asset.objects

__all__ = ["ImageAssetsMixin"]


class ImageAssetsMixin:

    @classmethod
    def create_image(cls,
                     dimensions: Tuple[int, int] = (60, 30),
                     color: str = "red") -> Image.Image:
        """ Creates valid image."""
        return Image.new('RGB', dimensions, color=color)

    @classmethod
    def create_uploaded_image(cls,
                              image: Optional[Image.Image] = None,
                              dimensions: Tuple[int, int] = (60, 30),
                              image_format: str = 'png',
                              filename: str = "asset.png",
                              color: str = "red") -> SimpleUploadedFile:
        """ Create valid image for processing in forms."""
        if image is None:
            image = cls.create_image(dimensions, color)
        buffer = io.BytesIO()
        image.save(buffer, format=image_format)
        content_type = f"image/{image_format}"
        return SimpleUploadedFile(filename, buffer.getvalue(),
                                  content_type=content_type)

    @classmethod
    def create_asset_type(cls,
                          required_for: Iterable[ModelBase] = (),
                          allowed_for: Iterable[ModelBase] = (),
                          **kwargs) -> AssetType:
        """ Creates asset type and sets required/allowed models for it."""
        asset_type: AssetType = AssetTypeFactory.create(**kwargs)
        cls.set_required_for(asset_type, *required_for)
        cls.set_allowed_for(asset_type, *allowed_for)
        return asset_type

    @classmethod
    def create_asset(cls,
                     asset_type: AssetType,
                     related: Model,
                     image: Optional[Image.Image] = None,
                     image_kwargs: Optional[dict] = None,
                     **kwargs) -> Asset:
        """ Creates an asset of given asset type with an image."""
        file = cls.create_uploaded_image(image, **(image_kwargs or {}))
        return AssetFactory.create(asset_type=asset_type, image=file,
                                   related=related, **kwargs)

    @classmethod
    def set_allowed_for(cls, asset_type: AssetType, *allowed_for: ModelBase):
        """ Add given models to allowed list for asset type, or clear it."""
        if allowed_for:
            content_types = map(ContentType.objects.get_for_model, allowed_for)
            asset_type.allowed_for.set(content_types, clear=True)
        else:
            asset_type.allowed_for.clear()

    @classmethod
    def set_required_for(cls, asset_type: AssetType, *required_for: ModelBase):
        """ Add given models to required list for asset type, or clear it."""
        if required_for:
            content_types = map(ContentType.objects.get_for_model, required_for)
            asset_type.required_for.set(content_types, clear=True)
        else:
            asset_type.required_for.clear()
