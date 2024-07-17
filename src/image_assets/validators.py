from contextlib import contextmanager

from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db.models.fields.files import ImageFieldFile, FieldFile
from django.utils.deconstruct import deconstructible

from image_assets import models


@deconstructible
class AssetValidator:
    """ Asset image file validator."""

    def __call__(self, value: FieldFile):
        asset = value.instance
        if asset.asset_type_id is None:
            # asset type not filled, no data to validate
            return
        asset_type: models.AssetType = asset.asset_type

        errors = asset_type.validate_max_size(value)

        # open image and validate it's content
        with self.open_file(value.file) as file:
            for validator in asset_type.get_validators(file):
                errors.extend(validator(file))

        if errors:
            raise ValidationError(errors)

    @contextmanager
    def open_file(self, file: File) -> Image.Image:
        with Image.open(file) as file_content:
            yield file_content
