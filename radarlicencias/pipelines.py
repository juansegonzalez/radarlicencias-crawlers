# Radarlicencias crawlers - Pipelines
# Normalize text fields for cross-referencing; do not alter URLs or IDs.


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
