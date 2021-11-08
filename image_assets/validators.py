from contextlib import contextmanager
from typing import Optional

from django.core.exceptions import ValidationError
from django.core.files import File
from django.db.models.fields.files import FieldFile
from django.utils.deconstruct import deconstructible
from pymediainfo import MediaInfo

from image_assets import models


class MediaInfoFile:
    def __init__(self, info: MediaInfo):
        self.file = None
        self.video = None
        for track in info.tracks:
            if track.kind_of_stream in ('Video', 'Image'):
                self.video = track
            if track.kind_of_stream == 'General':
                self.file = track

    @property
    def duration(self) -> Optional[float]:
        """Returns the duration of the video in milliseconds."""
        return self.video and self.video.duration

    @property
    def format(self) -> str:
        return self.file and self.file.format

    @property
    def width(self):
        return self.video and self.video.width or 0

    @property
    def height(self):
        return self.video and self.video.height or 0


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
    def open_file(self, file: File) -> MediaInfoFile:
        info = MediaInfo.parse(file)
        yield MediaInfoFile(info)
