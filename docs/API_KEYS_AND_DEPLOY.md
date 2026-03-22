# Where to put your API keys and Scrapy Cloud project ID

## Two different keys

| What | Used for | Where to put it |
|------|----------|------------------|
| **Scrapy Cloud API key** (shub) | Deploying the project with `shub deploy` | **Not in the repo.** Use `shub login` (saved to `~/.scrapinghub.yml`) or env var `SHUB_APIKEY`. |
| **Zyte API key** | Running the spiders (Zyte API requests) | **Not in the repo.** Set in Scrapy Cloud project **Settings** in the dashboard. Locally: env var `ZYTE_API_KEY`. |
| **Scrapy Cloud project ID** | Telling `shub` which cloud project to deploy to | In the project: **`scrapinghub.yml`** in the project root (see below). |

---

## 1. Scrapy Cloud API key (for deploy)

Used only when you run `shub deploy`.

**Option A – recommended (one-time setup):**

```bash
shub login
```

When prompted, paste your **Scrapy Cloud API key**. It is stored in `~/.scrapinghub.yml` on your machine (outside the project).  
Get the key from the Zyte dashboard: **[app.zyte.com](https://app.zyte.com)** → your profile/settings → API key (Scrapy Cloud / dashboard key).

**Option B – environment variable (e.g. for CI):**

```bash
export SHUB_APIKEY=your_scrapy_cloud_api_key_here
```

Then run `shub deploy` as usual.

---

## 2. Scrapy Cloud project ID (for deploy)

Tells `shub` which Scrapy Cloud project to deploy to.

**Option A – let shub create the file (easiest):**

1. Create a project in the [Scrapy Cloud dashboard](https://app.zyte.com/) if you don’t have one.
2. In the project, find the **Project ID** (e.g. in the URL or project settings).
3. From your project root run:
   ```bash
   shub deploy
   ```
4. The first time, shub will ask for the **project ID**. Enter it (e.g. `12345`).
5. shub creates **`scrapinghub.yml`** in the project root with something like:
   ```yaml
   project: 12345
   ```

**Option B – create the file yourself:**

In the **project root** (same folder as `scrapy.cfg`), create **`scrapinghub.yml`**:

```yaml
# Replace 12345 with your Scrapy Cloud project ID (from the dashboard).
project: 12345
```

Then run `shub deploy`.

**Note:** `scrapinghub.yml` is in `.gitignore` by default so you don’t commit your project ID if you prefer. You can remove it from `.gitignore` and commit the file if your team shares one project.

---

## 3. Zyte API key (for running the spiders)

Used when the spider runs (Zyte API for fetching pages). **Do not put this in the repo.**

**On Scrapy Cloud:**

1. Open your project on [app.zyte.com](https://app.zyte.com).
2. Go to **Project settings** (or **Settings**).
3. Add the Zyte API key:
   - If there is a **Settings** tab with a form for key/value pairs, add name **`ZYTE_API_KEY`** and value = your key.
   - If you use **Raw Settings**, use **Python syntax** (one setting per line). You **must** use spaces before and after `=`, for example:
     ```python
     ZYTE_API_KEY = "your_actual_key_here"
     ```
     Without the spaces, the setting may not save or apply. Keep the value in quotes and click **Save**.
4. If the key still doesn’t persist, try the **Settings** tab instead of Raw, or add it under **Environment variables** if that section exists.

Get the Zyte API key from the Zyte dashboard (e.g. Zyte API / API access).

**Locally (option A – config file, recommended):**

1. Copy the example config and add your key:
   ```bash
   cp radarlicencias/local_config.py.example radarlicencias/local_config.py
   ```
2. Edit `radarlicencias/local_config.py` and set `ZYTE_API_KEY = "your_actual_key_here"`.
3. Run the spider with local settings (it will read the key from the file):
   ```bash
   SCRAPY_SETTINGS_MODULE=radarlicencias.settings.local scrapy crawl airbnb_mallorca
   ```
   The file `local_config.py` is in `.gitignore`, so your key is not committed.

**Locally (option B – environment variable):**

```bash
export ZYTE_API_KEY=your_zyte_api_key_here
SCRAPY_SETTINGS_MODULE=radarlicencias.settings.local scrapy crawl airbnb_mallorca
```

---

## Summary

- **Scrapy Cloud API key** → `shub login` (or `SHUB_APIKEY` env var). Not in the repo.
- **Project ID** → in **`scrapinghub.yml`** in the project root (create it or let `shub deploy` create it).
- **Zyte API key** → Scrapy Cloud project **Settings** in the dashboard; locally use **`ZYTE_API_KEY`** env var. Not in the repo.
