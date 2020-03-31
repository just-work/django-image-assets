from unittest import mock

from admin_smoke.tests import AdminTests, AdminBaseTestCase, BaseTestCase
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from image_assets import models as assets_models
from image_assets.tests.mixins import ImageAssetsMixin
from testproject.testapp import admin, models


class VideoBaseTestCase(ImageAssetsMixin, BaseTestCase):
    """ Common methods for test cases."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.image = cls.create_image()
        cls.asset_type = cls.create_asset_type(
            slug="video_asset", format=assets_models.AssetType.PNG,
            required_for=[models.Video])
        cls.video = models.Video.objects.create(pk=23)

    def setUp(self):
        super().setUp()
        self.asset = self.create_asset(
            self.asset_type, image=self.image, related=self.video, active=True)

    # noinspection PyUnusedLocal
    @staticmethod
    def _storage_save_mock(name, content, max_length=None):
        return name


class VideoAssetTypeTestCase(VideoBaseTestCase):
    video_content_type: ContentType

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.allowed_asset_type = cls.create_asset_type(
            slug="allowed_asset", format=assets_models.AssetType.PNG,
            allowed_for=[models.Video]
        )
        cls.unrelated_asset_type = cls.create_asset_type(
            slug="unrelated", format=assets_models.AssetType.PNG)

    def test_required_asset_types(self):
        """ Check fetching required asset types for model or instance."""
        qs = assets_models.AssetType.objects.get_required(self.video)
        # Video has active asset of required asset type
        self.assertEqual(qs.count(), 0)

        qs = assets_models.AssetType.objects.get_required(models.Video)
        # For Video model one required asset type
        self.assertEqual(set(qs), {self.asset_type})

        qs = assets_models.AssetType.objects.get_required(None)
        # Return all asset types
        self.assertEqual(set(qs), {self.asset_type, self.allowed_asset_type,
                                   self.unrelated_asset_type})

        self.update_object(self.asset, active=False)

        qs = assets_models.AssetType.objects.get_required(self.video)
        # Video has inactive asset of required asset type
        self.assertEqual(set(qs), {self.asset_type})

        self.update_object(self.asset, active=True,
                           asset_type=self.allowed_asset_type)

        qs = assets_models.AssetType.objects.get_required(self.video)
        # Video has active asset for another asset type
        self.assertEqual(set(qs), {self.asset_type})


class VideoAdminTestCase(VideoBaseTestCase, AdminTests, AdminBaseTestCase):
    model_admin = admin.VideoAdmin
    model = models.Video
    object_name = 'video'
    prefix = 'image_assets-asset-content_type-object_id'

    def transform_to_new(self, data: dict) -> dict:
        self.reset_inline_data(data, self.prefix, None)
        data[f'{self.prefix}-0-image'] = self.create_uploaded_image(self.image)
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

        self.asset_type.required_for.clear()

        r = self.client.post(url, data=data)

        self.assertEqual(r.status_code, 302)
        self.assertFalse(self.get_errors_from_response(r))

    def test_validate_allowed_asset_type(self):
        """ If asset type is not allowed, object will not be saved."""
        self.asset_type.required_for.clear()
        r = self.client.get(self.change_url)
        data = self.get_form_data_from_response(r)
        url = self.add_url
        data = self.transform_to_new(data)
        data[f'{self.prefix}-0-image'] = self.create_uploaded_image(self.image)

        r = self.client.post(url, data=data)

        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(self.get_errors_from_response(r))
        self.set_allowed_for(self.asset_type, models.Video)

        data[f'{self.prefix}-0-image'] = self.create_uploaded_image(self.image)

        r = self.client.post(url, data=data)

        self.assertFalse(self.get_errors_from_response(r))
        self.assertEqual(r.status_code, 302)

    def test_maintain_single_active_asset(self):
        """ Only one active asset of same asset type is allowed."""
        r = self.client.get(self.change_url)
        data = self.get_form_data_from_response(r)
        data[f'{self.prefix}-1-image'] = self.create_uploaded_image(self.image)
        data[f'{self.prefix}-1-asset_type'] = self.asset_type.id

        r = self.client.post(self.change_url, data=data)

        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.get_errors_from_response(r))

        data[f'{self.prefix}-0-active'] = False
        data[f'{self.prefix}-1-image'] = self.create_uploaded_image(self.image)

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

    def setUp(self):
        super().setUp()
        self.delete_patcher = mock.patch(
            'inmemorystorage.InMemoryStorage.delete')
        self.delete_mock = self.delete_patcher.start()

    def tearDown(self):
        super().tearDown()
        self.delete_patcher.stop()

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


class AssetValidationTestCase(VideoBaseTestCase):
    """ Checks image validation for asset type."""

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
        self.asset_type.format = assets_models.AssetType.JPEG

        self.assert_validation_not_passed()

        self.asset.image = self.create_uploaded_image(
            image_format='jpeg', filename='asset.jpg')

        self.assert_validation_passed()

        # format is checked from image, not filename
        self.asset.image = self.create_uploaded_image(
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
