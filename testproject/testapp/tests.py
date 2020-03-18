import io

from admin_smoke.tests import AdminTests, AdminBaseTestCase
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from image_assets import models as assets_models
from testproject.testapp import admin, models


class VideoAdminTestCase(AdminTests, AdminBaseTestCase):
    model_admin = admin.VideoAdmin
    model = models.Video
    object_name = 'video'
    prefix = 'image_assets-asset-content_type-object_id'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.image = Image.new('RGB', (60, 30), color='red')
        buffer = io.BytesIO()
        cls.image.save(buffer, format='png')
        cls.image_content = buffer.getvalue()
        cls.video_asset_type = assets_models.AssetType.objects.create(
            slug="video_asset")
        cls.video_content_type = ContentType.objects.get_for_model(models.Video)
        cls.video_asset_type.required_for.set([cls.video_content_type])
        cls.video = models.Video.objects.create(pk=23)
        cls.video.assets.create(
            asset_type=cls.video_asset_type,
            active=True, image=SimpleUploadedFile(
                "asset.jpg", cls.image_content, content_type="image/jpeg"))

    def transform_to_new(self, data: dict) -> dict:
        self.reset_inline_data(data, self.prefix, None)
        data[f'{self.prefix}-0-image'] = SimpleUploadedFile(
            "asset.jpg", self.image_content, content_type="image/jpeg")
        return data

    def test_validate_required_asset_type(self):
        """ Without required assets object can't be saved."""
        r = self.client.get(self.change_url)
        data = self.get_form_data_from_response(r)
        url = self.add_url
        data = self.transform_to_new(data)
        for k in list(data):
            if '-0-' in k:
                del data[k]
            elif '-3-' in k:
                data[k.replace('-3-', '-0-')] = data.pop(k)
        data[f'{self.prefix}-TOTAL_FORMS'] = 3

        r = self.client.post(url, data=data)

        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(self.get_errors_from_response(r))

        self.video_asset_type.required_for.clear()

        r = self.client.post(url, data=data)

        self.assertEqual(r.status_code, 302)
        self.assertFalse(self.get_errors_from_response(r))

    def test_validate_allowed_asset_type(self):
        """ If asset type is not allowed, object will not be saved."""
        self.video_asset_type.required_for.clear()
        r = self.client.get(self.change_url)
        data = self.get_form_data_from_response(r)
        url = self.add_url
        data = self.transform_to_new(data)
        data[f'{self.prefix}-0-image'] = SimpleUploadedFile(
            "asset.jpg", self.image_content, content_type="image/jpeg")

        r = self.client.post(url, data=data)

        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(self.get_errors_from_response(r))

        self.video_asset_type.allowed_for.set([self.video_content_type])
        data[f'{self.prefix}-0-image'] = SimpleUploadedFile(
            "asset.jpg", self.image_content, content_type="image/jpeg")

        r = self.client.post(url, data=data)

        self.assertFalse(self.get_errors_from_response(r))
        self.assertEqual(r.status_code, 302)
