from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from image_assets.models import Asset


class Video(models.Model):
    assets = GenericRelation(Asset, blank=True)


class Article(models.Model):
    assets = GenericRelation(Asset, blank=True)
