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
   - If **R2 env vars are missing**: logs one warning for the run and skips all image work.
   - If **`head_object`** succeeds: sets `picture_r2_key` to that key, logs **reuse**, done.
   - Else: **`download_and_upload_image_to_r2`** (in `radarlicencias/r2_image.py`) downloads from `picture_url`, validates `image/*`, resizes to max width 1000px, WebP, uploads with `Content-Type: image/webp`.
   - On upload success: sets `picture_r2_key`.
   - On upload failure or invalid image: sets `picture_r2_key` to `null`, logs warning; **item is not dropped**.

## Environment variables (R2)

Set in the shell, `.env` (for local scripts that call `load_dotenv()`), or Scrapy Cloud project settings:

| Variable | Purpose |
|----------|---------|
| `R2_ACCESS_KEY_ID` | R2 S3-compatible access key |
| `R2_SECRET_ACCESS_KEY` | R2 secret |
| `R2_BUCKET_NAME` | Bucket name |
| `R2_ENDPOINT_URL` | R2 S3 API endpoint (account-specific) |

Without these, the pipeline skips image processing and leaves `picture_r2_key` unset (except when explicitly set to `null` after a failed upload attempt when env **is** present).

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

Run twice with the same `listing_id`: the second run should log **reused existing R2 image**.

## Dependencies

`boto3`, `requests`, and `Pillow` are listed in `requirements.txt` for R2 and image handling.
