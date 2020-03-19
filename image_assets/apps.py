from django.apps import AppConfig


class ImageAssetsConfig(AppConfig):
    name = 'image_assets'

    def ready(self):
        __import__('image_assets.signals')
