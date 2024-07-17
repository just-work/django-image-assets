from django.contrib import admin

from image_assets.admin import AssetsInline
from testproject.testapp import models


@admin.register(models.Video)
class VideoAdmin(admin.ModelAdmin):
    inlines = (AssetsInline,)


@admin.register(models.Article)
class ArticleAdmin(admin.ModelAdmin):
    inlines = (AssetsInline,)
