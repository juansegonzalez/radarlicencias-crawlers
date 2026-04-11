# Radarlicencias crawlers - Pipelines
# Normalize text fields for cross-referencing; do not alter URLs or IDs.

import logging

from radarlicencias.items import AirbnbListingItem
from radarlicencias.r2_image import (
    download_and_upload_image_to_r2,
    r2_env_configured,
    r2_object_exists,
)

logger = logging.getLogger(__name__)


def _normalize_string(value):
    """Strip and collapse spaces for consistent cross-referencing."""
    if value is None or not isinstance(value, str):
        return value
    return " ".join(value.strip().split())


# Only normalize text fields used for matching; skip url, ficha_url, listing_id (URLs and identifiers).
TEXT_FIELDS_FOR_NORMALIZE = frozenset({
    "signature", "commercial_name", "municipality", "address",
    "current_status", "number_of_units", "number_of_places", "activity_start_date",
    "locality", "group", "related_entity_name", "related_entity_relation",
    "location", "registration_number",
})


class AirbnbImageR2Pipeline:
    """
    For Airbnb listings: ensure main photo exists in Cloudflare R2 at airbnb/<listing_id>/main.webp.
    Skips download/upload when the object already exists (periodic crawls).
    """

    def __init__(self):
        self._warned_missing_r2 = False

    def process_item(self, item, spider=None):
        if not isinstance(item, AirbnbListingItem):
            return item

        if not r2_env_configured():
            if not self._warned_missing_r2:
                logger.warning(
                    "AirbnbImageR2Pipeline: R2 env vars missing; skipping image pipeline. "
                    "Set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_ENDPOINT_URL."
                )
                self._warned_missing_r2 = True
            return item

        listing_id = item.get("listing_id")
        picture_url = item.get("picture_url")
        listing_id_str = str(listing_id).strip() if listing_id is not None else ""

        if not listing_id_str:
            logger.debug("AirbnbImageR2Pipeline: missing or empty listing_id, skip")
            return item

        if not picture_url or not str(picture_url).strip():
            logger.debug(
                "AirbnbImageR2Pipeline: missing picture_url listing_id=%s, skip",
                listing_id_str,
            )
            return item

        object_key = f"airbnb/{listing_id_str}/main.webp"

        exists = r2_object_exists(object_key)
        if exists is True:
            item["picture_r2_key"] = object_key
            logger.debug(
                "AirbnbImageR2Pipeline: reused existing R2 image listing_id=%s object_key=%s",
                listing_id_str,
                object_key,
            )
            return item
        if exists is None:
            logger.warning(
                "AirbnbImageR2Pipeline: could not verify R2 object; skipping upload listing_id=%s object_key=%s",
                listing_id_str,
                object_key,
            )
            return item

        ok = download_and_upload_image_to_r2(str(picture_url).strip(), object_key)
        if ok:
            item["picture_r2_key"] = object_key
            logger.info(
                "AirbnbImageR2Pipeline: uploaded new image listing_id=%s object_key=%s",
                listing_id_str,
                object_key,
            )
        else:
            # Explicit None so feeds/DB consumers can distinguish "attempted but failed" from "never set".
            item["picture_r2_key"] = None
            logger.warning(
                "AirbnbImageR2Pipeline: upload failed listing_id=%s object_key=%s",
                listing_id_str,
                object_key,
            )
        return item


class RadarlicenciasPipeline:
    """Normalize text fields so cross-referencing (Consejo vs Airbnb) is reliable. URLs/IDs are left as-is."""

    def process_item(self, item, spider=None):
        if item is None:
            return item
        for key in item.fields:
            if key not in TEXT_FIELDS_FOR_NORMALIZE:
                continue
            if key in item and item[key] and isinstance(item[key], str):
                item[key] = _normalize_string(item[key])
        return item
