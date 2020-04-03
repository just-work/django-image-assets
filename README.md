django-image-assets
===================

Django application for image assets management.

[![Build Status](https://github.com/just-work/django-image-assets/workflows/build/badge.svg?branch=master&event=push)](https://github.com/just-work/django-image-assets/actions?query=event%3Apush+branch%3Amaster+workflow%3Abuild)
[![codecov](https://codecov.io/gh/just-work/django-image-assets/branch/master/graph/badge.svg)](https://codecov.io/gh/just-work/django-image-assets)
[![PyPI version](https://badge.fury.io/py/django-image-assets.svg)](https://badge.fury.io/py/django-image-assets)

Use case
--------

* There are several content types on a web site
* Each of them has a set of required or additional image assets
* Every asset of same asset type must satisfy custom constraints on dimensions, 
    format and file size.
* The most important thing: these constraints and required asset type sets are
    updated often, along with web design evolves and more platforms are added.

Installation
------------

```shell script
pip install django-image-assets
```

Working example is in `testproject.testapp`.

1. Add `image_assets` application to installed apps in django settings:
    ```python
    INSTALLED_APPS.append('image_assets')
    ```
2. Add generic relation to your content models:
    ```python
    from django.contrib.contenttypes.fields import GenericRelation
    from django.db import models
    
    from image_assets.models import Asset
    
    
    class Video(models.Model):
        assets = GenericRelation(Asset, blank=True)
    ```
   
3. Setup inlines for assets
    ```python
    from django.contrib import admin
    
    from image_assets.admin import AssetsInline
    from testproject.testapp import models
    
    
    @admin.register(models.Video)
    class VideoAdmin(admin.ModelAdmin):
        inlines = (AssetsInline,)
    ```

Usage
-----

1. Create new asset type (i.e. "thumbnail")
2. Add `Video` to `allowed_for` set: now you can add a thumbnail to a video. Or 
    you may skip this asset.
3. Add `Article` to `required_for` set: now you will able to create or edit
    an article with valid "thumbnail" asset only.
4. When an asset is deleted, it's file is owned by `DeletedAsset` object and may 
    be wiped later by manual or automatic cleanup.

Advanced
--------

If you need to alter model fields i.e. for `AssetType`, you may subclass
existing model and than change image_assets application settings.

1. Subclass `AssetType` model
    ```python
    from django.db import models
    from image_assets.models import AssetType
    
    
    class MyAssetType(AssetType):
        some_feature_flag = models.BooleanField(default=False)
    ```
2. Change a reference to an asset type model in settings:
    ```python
    IMAGE_ASSETS_CONFIG = {
        'ASSET_TYPE_MODEL': 'my_app.MyAssetType',
        'ASSET_MODEL': 'image_assets.Asset',
        'DELETED_ASSET_MODEL': 'image_assets.DeletedAsset'
    }
    ```
3. `image_assets.AssetType` will be declared as abstract and `MyAssetType`
    will be returned as result of `image_assets.models.get_asset_type_model()`
