import os

import cloudinary
import cloudinary.uploader
from cloudinary_storage.storage import RawMediaCloudinaryStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class AuthenticatedDeliveryDocumentStorage(RawMediaCloudinaryStorage):
    """Cloudinary storage for private delivery-partner KYC documents."""

    DELIVERY_TYPE = "authenticated"

    def _upload(self, name, content):
        options = {
            "use_filename": True,
            "unique_filename": True,
            "resource_type": self._get_resource_type(name),
            "type": self.DELIVERY_TYPE,
            "tags": self.TAG,
        }

        folder = os.path.dirname(name)
        if folder:
            options["folder"] = folder

        return cloudinary.uploader.upload(content, **options)

    def _get_url(self, name):
        name = self._prepend_prefix(name)
        resource = cloudinary.CloudinaryResource(
            name,
            default_resource_type=self._get_resource_type(name),
            type=self.DELIVERY_TYPE,
        )
        return resource.build_url(
            secure=True,
            sign_url=True,
        )

    def delete(self, name):
        response = cloudinary.uploader.destroy(
            name,
            invalidate=True,
            resource_type=self._get_resource_type(name),
            type=self.DELIVERY_TYPE,
        )
        return response.get("result") == "ok"


private_delivery_document_storage = (
    AuthenticatedDeliveryDocumentStorage()
)
