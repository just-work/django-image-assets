from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ImageAssetsConfig(AppConfig):
    name = 'image_assets'
    verbose_name = _("Image assets")

    def ready(self):
        __import__('image_assets.signals')
