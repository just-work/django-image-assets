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
            slug="video_asset", formats=assets_models.AssetType.formats.png,
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
            slug="allowed_asset", formats=assets_models.AssetType.formats.png,
            allowed_for=[models.Video]
        )
        cls.unrelated_asset_type = cls.create_asset_type(
            slug="unrelated", formats=assets_models.AssetType.formats.png)

    def test_required_asset_types(self):
        """ Check fetching required asset types for model or instance."""
        qs = assets_models.AssetType.objects.get_for_model(None)
        # Return all asset types for unknown object
        self.assertEqual(qs.count(), assets_models.AssetType.objects.count())

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
        kw = {f'{self.prefix}-0-image': self.create_uploaded_image(self.image)}
        r = self.post_changeform(fields=kw)

        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(self.get_errors_from_response(r))
        self.set_allowed_for(self.asset_type, models.Video)

        kw = {f'{self.prefix}-0-image': self.create_uploaded_image(self.image)}
        r = self.post_changeform(fields=kw)

        self.assertFalse(self.get_errors_from_response(r))
        self.assertEqual(r.status_code, 302)

    def test_maintain_single_active_asset(self):
        """ Only one active asset of same asset type is allowed."""
        kw = {
            f'{self.prefix}-1-image': self.create_uploaded_image(self.image),
            f'{self.prefix}-1-asset_type': self.asset_type.id,
        }
        r = self.post_changeform(fields=kw)

        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.get_errors_from_response(r))

        kw = {
            f'{self.prefix}-0-active': False,
            f'{self.prefix}-1-image': self.create_uploaded_image(self.image),
            f'{self.prefix}-1-asset_type': self.asset_type.id,
        }
        r = self.post_changeform(fields=kw)

        self.assertFalse(self.get_errors_from_response(r))
        self.assertEqual(r.status_code, 302)
        self.assert_object_fields(
            self.asset,
            active=False)
        asset = self.video.assets.last()
        self.assertTrue(asset.active)

    def test_multiple_inactive_assets_allowed(self):
        """
        There may be multiple inactive assets of same type for same object.
        :return:
        """
        kw = {
            f'{self.prefix}-1-active': False,
            f'{self.prefix}-1-image': self.create_uploaded_image(self.image),
            f'{self.prefix}-1-asset_type': self.asset_type.id,
            f'{self.prefix}-2-active': False,
            f'{self.prefix}-2-image': self.create_uploaded_image(self.image),
            f'{self.prefix}-2-asset_type': self.asset_type.id,
        }
        r = self.post_changeform(fields=kw)

        self.assertFalse(self.get_errors_from_response(r))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(2, self.video.assets.filter(active=False).count())


class AssetModelTestCase(VideoBaseTestCase):
    """ Asset model test case"""

    def test_str(self):
        """ Check __str__ method."""
        self.assertIsInstance(self.asset.__str__(), str)
        empty = assets_models.get_asset_model()()
        self.assertIsInstance(empty.__str__(), str)


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

    def test_str(self):
        """ Check __str__ method."""
        self.asset.delete()
        deleted_model = assets_models.get_deleted_asset_model()
        deleted = deleted_model.objects.last()
        self.assertIsInstance(deleted.__str__(), str)
        empty = deleted_model()
        self.assertIsInstance(empty.__str__(), str)

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

    def test_delete_multiple_assets_for_same_object(self):
        """
        There may be multiple deleted assets of same type for same object.
        """
        self.asset.delete()
        asset = self.create_asset(self.asset.asset_type, self.asset.related)
        asset.delete()

        deleted = assets_models.DeletedAsset.objects.filter(
            content_type=self.asset.content_type,
            object_id=self.asset.object_id,
            asset_type=self.asset.asset_type)
        self.assertEqual(2, deleted.count())

    def test_recover_deleted_asset(self):
        """
        Deleted asset is recovered as inactive asset with same image.
        """
        self.asset.delete()
        deleted = assets_models.DeletedAsset.objects.get()
        qs = assets_models.DeletedAsset.objects.filter(pk=deleted.pk)
        filename = deleted.image.name

        deleted.recover()

        asset = assets_models.Asset.objects.order_by('id').last()
        self.assert_object_fields(
            asset,
            content_type=self.asset.content_type,
            object_id=self.asset.object_id,
            asset_type=self.asset.asset_type,
            active=False,
        )
        self.assertEqual(asset.image.name, filename)
        self.delete_mock.assert_not_called()
        self.assertFalse(qs.exists())


class AssetValidationTestCase(VideoBaseTestCase):
    """ Checks image validation for asset type."""

    def assert_validation_not_passed(self):
        with self.assertRaises(ValidationError) as e:
            self.asset.full_clean()
        invalid_keys = set(e.exception.error_dict)
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
        self.asset_type.formats = assets_models.AssetType.formats.jpeg

        self.assert_validation_not_passed()

        self.asset.image = self.create_uploaded_image(
            image_format='jpeg', filename='asset.jpg')

        self.assert_validation_passed()

        # format is checked from image, not filename
        self.asset.image = self.create_uploaded_image(
            image_format='png', filename='asset.jpg')

        self.assert_validation_not_passed()

        # multiple formats are allowed
        formats = assets_models.AssetType.formats
        self.asset_type.formats = formats.jpeg | formats.png

        self.assert_validation_passed()

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

    def test_validate_exact_aspect(self):
        """
        Asset aspect ratio must correspond asset type aspect with accuracy.
        """
        self.asset_type.accuracy = 0

        # zero aspect disables aspect check
        self.assert_validation_passed()

        self.asset_type.aspect = 3

        self.assert_validation_not_passed()

        self.asset_type.aspect = 2

        self.assert_validation_passed()
