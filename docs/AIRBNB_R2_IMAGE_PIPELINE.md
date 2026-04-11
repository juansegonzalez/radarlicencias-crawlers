# Airbnb main image → Cloudflare R2 (Scrapy pipeline)

## Purpose

Airbnb `picture_url` values are unstable (wrong asset, placeholder, or changed CDN paths). The crawler stores **one stable main image per listing** in **Cloudflare R2** and records only the **object key** on each `AirbnbListingItem` (`picture_r2_key`), e.g. `airbnb/12345678/main.webp`. Public URLs are built later in Django (or another app), not in this repo.

Periodic crawls **do not re-download or re-upload** when the object already exists: the pipeline uses `head_object` first.

## Flow

1. Spider extracts `listing_id` and `picture_url` and yields `AirbnbListingItem` (unchanged).
2. **`RadarlicenciasPipeline`** (300) normalizes text fields used for matching.
3. **`AirbnbImageR2Pipeline`** (400) runs only for `AirbnbListingItem`:
   - Requires both `listing_id` and non-empty `picture_url`; otherwise skips (no error).
   - Object key: `airbnb/{listing_id}/main.webp`.
   - If **R2 env vars are missing**: logs warnings; **`picture_r2_key` is set to `null`** on every item so feeds/schema include the field.
   - **`r2_object_exists` (head_object)** returns:
     - **True** → object present: set `picture_r2_key`, log reuse at **debug** (avoids log noise on large crawls).
     - **False** → object definitely missing (404 / NoSuchKey / NotFound): proceed to download + upload.
     - **None** → could not determine (transient R2/API error): **do not upload**; log **warning**; **`picture_r2_key` = `null`**.
   - **`download_and_upload_image_to_r2`**: validates `image/*`, minimum size **300×200** px (after decode), max width **1000** px, WebP, `Content-Type: image/webp`.
   - On upload success: sets `picture_r2_key`.
   - On upload failure or invalid image: sets `picture_r2_key` to `null`, logs warning; **item is not dropped**.

## Configuration (R2)

Resolution is **per key**, in order: **`os.environ` first**, then **Scrapy settings** (`crawler.settings`), e.g. project settings on Scrapy Cloud. `radarlicencias.settings.base` declares empty defaults so the keys exist; dashboard overrides supply values.

| Variable | Purpose |
|----------|---------|
| `R2_ACCESS_KEY_ID` | R2 S3-compatible access key |
| `R2_SECRET_ACCESS_KEY` | R2 secret |
| `R2_BUCKET_NAME` | Bucket name |
| `R2_ENDPOINT_URL` | R2 S3 API endpoint (account-specific) |

**Local:** `.env` / shell env, or `settings/local.py` if you set these on the Scrapy settings object.

**Scrapy Cloud:** project **Settings** (same names) work without duplicating into env vars. Startup logs show `R2 config source=env`, `scrapy_settings`, or `mixed_env_and_scrapy_settings`.

If nothing resolves, the pipeline sets **`picture_r2_key` to `null`** and logs `source=missing`.

## Code map

| Piece | Location |
|-------|----------|
| Item field `picture_r2_key` | `radarlicencias/items.py` |
| Pipeline `AirbnbImageR2Pipeline` | `radarlicencias/pipelines.py` |
| `head_object` + upload helper | `radarlicencias/r2_image.py` (`r2_object_exists`, `download_and_upload_image_to_r2`) |
| Pipeline order | `radarlicencias/settings/base.py` → `ITEM_PIPELINES` |

## Local smoke test (pipeline only)

With `.env` containing R2 variables:

```bash
python -c "
from dotenv import load_dotenv
load_dotenv()
import logging
logging.basicConfig(level=logging.INFO)
from radarlicencias.items import AirbnbListingItem
from radarlicencias.pipelines import AirbnbImageR2Pipeline
p = AirbnbImageR2Pipeline()
item = AirbnbListingItem(
    listing_id='TEST_LISTING_ID',
    picture_url='https://example.com/image.jpg',
    url='https://www.airbnb.com/rooms/TEST_LISTING_ID',
)
print(p.process_item(item).get('picture_r2_key'))
"
```

Run twice with the same `listing_id`: the second run should reuse R2 (see **debug** logs if enabled).

The boto3 S3 client is **cached for the process** after first use (`r2_image.py`).

## Dependencies

`boto3`, `requests`, and `Pillow` are listed in `requirements.txt` for R2 and image handling.
