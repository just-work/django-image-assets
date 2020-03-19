import io
from unittest import mock

from PIL import Image
from admin_smoke.tests import AdminTests, AdminBaseTestCase, BaseTestCase
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from image_assets import models as assets_models
from testproject.testapp import admin, models


class VideoBaseTestCase(BaseTestCase):
    """ Common methods for test cases."""

    image: Image.Image

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.image = Image.new('RGB', (60, 30), color='red')
        cls.video_asset_type = assets_models.AssetType.objects.create(
            slug="video_asset", format=assets_models.AssetType.Formats.PNG)
        cls.video_content_type = ContentType.objects.get_for_model(models.Video)
        cls.video_asset_type.required_for.set([cls.video_content_type])
        cls.video = models.Video.objects.create(pk=23)

    @classmethod
    def create_uploaded_file(cls):
        buffer = io.BytesIO()
        cls.image.save(buffer, format='png')
        return SimpleUploadedFile(
            "asset.jpg", buffer.getvalue(), content_type="image/jpeg")

    def setUp(self):
        super().setUp()
        self.delete_patcher = mock.patch(
            'django.core.files.storage.FileSystemStorage.delete')
        self.delete_mock = self.delete_patcher.start()
        self.save_patcher = mock.patch(
            'django.core.files.storage.FileSystemStorage.save',
            side_effect=self._storage_save_mock)
        self.save_mock = self.save_patcher.start()
        self.asset = self.video.assets.create(
            asset_type=self.video_asset_type,
            active=True, image=self.create_uploaded_file())

    def tearDown(self):
        super().tearDown()
        self.delete_patcher.stop()
        self.save_patcher.stop()

    # noinspection PyUnusedLocal
    @staticmethod
    def _storage_save_mock(name, content, max_length=None):
        return name


class VideoAdminTestCase(VideoBaseTestCase, AdminTests, AdminBaseTestCase):
    model_admin = admin.VideoAdmin
    model = models.Video
    object_name = 'video'
    prefix = 'image_assets-asset-content_type-object_id'

    def transform_to_new(self, data: dict) -> dict:
        self.reset_inline_data(data, self.prefix, None)
        data[f'{self.prefix}-0-image'] = self.create_uploaded_file()
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
        data[f'{self.prefix}-0-image'] = self.create_uploaded_file()

        r = self.client.post(url, data=data)

        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(self.get_errors_from_response(r))

        self.video_asset_type.allowed_for.set([self.video_content_type])
        data[f'{self.prefix}-0-image'] = self.create_uploaded_file()

        r = self.client.post(url, data=data)

        self.assertFalse(self.get_errors_from_response(r))
        self.assertEqual(r.status_code, 302)

    def test_maintain_single_active_asset(self):
        """ Only one active asset of same asset type is allowed."""
        r = self.client.get(self.change_url)
        data = self.get_form_data_from_response(r)
        data[f'{self.prefix}-1-image'] = self.create_uploaded_file()
        data[f'{self.prefix}-1-asset_type'] = self.video_asset_type.id

        r = self.client.post(self.change_url, data=data)

        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.get_errors_from_response(r))

        data[f'{self.prefix}-0-active'] = False
        data[f'{self.prefix}-1-image'] = self.create_uploaded_file()

        r = self.client.post(self.change_url, data=data)

        self.assertFalse(self.get_errors_from_response(r))
        self.assertEqual(r.status_code, 302)
        self.assert_object_fields(
            self.asset,
            active=False)
        asset = self.video.assets.last()
        self.assertTrue(asset.active)


class DeletedAssetModelTestCase(VideoBaseTestCase):
    """ Asset deletion handling test case."""

    def test_delete_asset(self):
        """
        Asset file is moved to DeletedAsset instance after asset deletion.
        """
        filename = self.asset.image.name
        self.asset.delete()

        self.delete_mock.assert_not_called()
        deleted = assets_models.DeletedAsset.objects.get()
        self.assertEqual(deleted.image.name, filename)

    def test_purge_deleted_asset(self):
        """
        A file for DeletedAsset is purged on object deletion.
        """
        self.asset.delete()
        deleted = assets_models.DeletedAsset.objects.get()
        filename = deleted.image.name

        deleted.delete()

        self.delete_mock.assert_called_once_with(filename)


class AssetValidationTestCase(BaseTestCase):
    """ Checks image validation for asset type."""
    image: Image.Image

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.image = Image.new('RGB', (60, 30), color='red')
        cls.asset_type = assets_models.AssetType.objects.create(
            slug="video_asset",
            min_width=0,
            min_height=0,
            max_size=0,
            aspect=0,
            accuracy=0,
            format=assets_models.AssetType.Formats.PNG)
        cls.asset = assets_models.Asset(
            asset_type=cls.asset_type,
            image=cls.create_uploaded_file())

    @classmethod
    def create_uploaded_file(cls, image_format='png', filename='asset.png'):
        buffer = io.BytesIO()
        cls.image.save(buffer, format=image_format)
        return SimpleUploadedFile(
            filename, buffer.getvalue())

    def setUp(self):
        super().setUp()
        # copy asset_type from cls to self
        self.asset_type: assets_models.AssetType = self.reload(self.asset_type)
        self.asset.asset_type = self.asset_type

    def assert_validation_not_passed(self):
        try:
            self.asset.full_clean()
        except ValidationError as e:
            invalid_keys = set(e.error_dict)
            expected = {'asset_type', 'content_type', 'object_id'}
            self.assertTrue(invalid_keys - expected)

    def assert_validation_passed(self):
        try:
            self.asset.full_clean()
        except ValidationError as e:
            invalid_keys = set(e.error_dict)
            expected = {'asset_type', 'content_type', 'object_id'}
            self.assertFalse(invalid_keys - expected)

    def test_validate_without_asset_type(self):
        """ Asset object passes image validation if no asset type is set."""
        self.asset.asset_type = None

        self.assert_validation_passed()

        self.asset.asset_type = self.asset_type
        self.asset_type.max_size = 1

        self.assert_validation_not_passed()

    def test_validate_format(self):
        """ Asset image format must correspond asset type format."""
        self.asset_type.format = assets_models.AssetType.Formats.JPEG

        self.assert_validation_not_passed()

        self.asset.image = self.create_uploaded_file(
            image_format='jpeg', filename='asset.jpg')

        self.assert_validation_passed()

        # format is checked from image, not filename
        self.asset.image = self.create_uploaded_file(
            image_format='png', filename='asset.jpg')

        self.assert_validation_not_passed()

    def test_validate_min_width(self):
        """ Asset image width must correspond asset type min width."""
        self.asset_type.min_width = self.image.width + 1

        self.assert_validation_not_passed()

        self.asset_type.min_width = self.image.width

        self.assert_validation_passed()

    def test_validate_min_height(self):
        """ Asset image height must correspond asset type min height."""
        self.asset_type.min_height = self.image.height + 1

        self.assert_validation_not_passed()

        self.asset_type.min_height = self.image.height

        self.assert_validation_passed()

    def test_validate_max_size(self):
        """ Asset file size must correspond asset type max size."""
        # zero max size disables file size check
        self.assert_validation_passed()

        self.asset_type.max_size = self.asset.image.size - 1

        self.assert_validation_not_passed()

        self.asset_type.max_size = self.asset.image.size

        self.assert_validation_passed()

    def test_validate_aspect_with_accuracy(self):
        """
        Asset aspect ratio must correspond asset type aspect with accuracy.
        """
        # zero aspect disables aspect check
        self.assert_validation_passed()

        self.asset_type.aspect = 2.1

        self.assert_validation_not_passed()

        self.asset_type.accuracy = 0.1

        self.assert_validation_passed()

        self.asset_type.aspect = 1.8

        self.assert_validation_not_passed()

        self.asset_type.aspect = 1.99
        self.asset_type.accuracy = 0.01

        self.assert_validation_passed()
