from django.conf import settings


__all__ = [
    'ASSET_TYPE_MODEL',
    'ASSET_MODEL',
    'DELETED_ASSET_MODEL',
]

_default_settings = {
    'ASSET_TYPE_MODEL': 'image_assets.AssetType',
    'ASSET_MODEL': 'image_assets.Asset',
    'DELETED_ASSET_MODEL': 'image_assets.DeletedAsset'
}


assets_config = dict(_default_settings)
local_config = getattr(settings, 'IMAGE_ASSETS_CONFIG', {})
for k, v in local_config.items():
    if k not in _default_settings:
        raise KeyError(k)
    assets_config[k] = v


ASSET_TYPE_MODEL = assets_config['ASSET_TYPE_MODEL']
ASSET_MODEL = assets_config['ASSET_MODEL']
DELETED_ASSET_MODEL = assets_config['DELETED_ASSET_MODEL']