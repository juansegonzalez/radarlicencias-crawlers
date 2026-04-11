# Deploy and test

## Is the project ready for Scrapy Cloud?

Yes. The project is set up for deployment:

- **scrapy.cfg** – project name `radarlicencias`
- **requirements.txt** – `scrapy`, `scrapy-zyte-api`
- **Spiders** – `consejo_mallorca`, `airbnb_mallorca` (Airbnb spider is the one ready to test)
- **Data file** – `radarlicencias/data/mallorca_municipalities.txt` is bundled on deploy

On Scrapy Cloud, set **ZYTE_API_KEY** in the project settings (or link your Zyte API). Configure the **feed** (e.g. JSON Lines) in the job or project settings.

---

## Test locally (recommended before deploy)

Use a **virtual environment** so project dependencies are isolated:

```bash
cd /path/to/radarlicencias-crawlers

# Create and activate venv
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set Zyte API key (pick one):
#   Option A: cp radarlicencias/local_config.py.example radarlicencias/local_config.py && edit it
#   Option B: export ZYTE_API_KEY=your_key_here
```

List spiders:

```bash
scrapy list
```

Run the Airbnb spider with local feed (writes to `data/`):

```bash
# From project root; if you get "ModuleNotFoundError: No module named 'radarlicencias'", run with:
PYTHONPATH=. SCRAPY_SETTINGS_MODULE=radarlicencias.settings.local scrapy crawl airbnb_mallorca
```

---

## Deploy to Scrapy Cloud

**Where to put what:** See **[docs/API_KEYS_AND_DEPLOY.md](docs/API_KEYS_AND_DEPLOY.md)** for API keys and project ID.

1. **Sign up / log in** at [app.zyte.com](https://app.zyte.com/) and create a **Scrapy Cloud** project (or use an existing one).

2. **Scrapy Cloud API key (for deploy):**  
   Run `shub login` and paste your dashboard API key. It is stored in `~/.scrapinghub.yml` (not in the repo).

3. **Project ID (for deploy):**  
   From the project root, run `shub deploy`. The first time, enter your **Scrapy Cloud project ID** when prompted; shub creates **`scrapinghub.yml`** with `project: <ID>`. Or copy `scrapinghub.yml.example` to `scrapinghub.yml` and set your project ID.

4. **Zyte API key (for running spiders):**  
   In the Scrapy Cloud dashboard → your project → **Settings** → add **`ZYTE_API_KEY`** with your Zyte API key. Do not put this in the repo.

5. **Feed and runs:**  
   In the dashboard, set the **feed** (e.g. JSON Lines) for jobs, then run the spider `airbnb_mallorca` and set up **periodic jobs** (e.g. monthly) if needed.

6. **Deploy fails with “Pip checks failed” / `awscli` vs `botocore`:**  
   Scrapy Cloud’s image includes **awscli**, which pins **botocore** (e.g. `1.31.62`). The project pins **`boto3` / `botocore`** in `requirements.txt` to match so `shub deploy` passes dependency checks. Do not upgrade boto3 in requirements without checking compatibility with the platform’s awscli.

---

## Quick checklist before first run

- [ ] `ZYTE_API_KEY` set (locally in env, on Scrapy Cloud in project settings)
- [ ] Local test: `scrapy list` shows `airbnb_mallorca` and `consejo_mallorca`
- [ ] Optional: reduce `mallorca_municipalities.txt` to 1–2 lines for a short test run
- [ ] Feed destination configured (local: `radarlicencias.settings.local`; cloud: job/project feed settings)
