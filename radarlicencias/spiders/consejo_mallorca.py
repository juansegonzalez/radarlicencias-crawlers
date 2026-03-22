"""
Consell de Mallorca spider — pure HTTP/AJAX (no Zyte, no Playwright).

URL: https://www.caib.es/cathosfront/cens?lang=ES

Behaviour:
- Calls the official JSON API that backs the census search UI:
  - POST https://www.caib.es/cathosfront/services/censo/establecimientos/filter
    with JSON body like:
      {
        "idSubtipoEstablecimientoWeb": "",
        "idCategoriaEstablecimiento": "",
        "signatura": "",
        "denominacionComercial": "",
        "idMunicipio": "",
        "direccion": "",
        "pagina": N,
        "resultados": 50
      }
  - Iterates pagina = 1,2,... until no more results are returned.
- For each establishment in the JSON result, calls:
    GET https://www.caib.es/cathosfront/services/censo/establecimientos/{id}
  to fetch ficha details in JSON and builds the final item.

Notes:
- This spider crawls the **full census (all groups)** by default (no filters),
  which is what you asked for now.
- It does not use Zyte API or Playwright; it is safe to run on Scrapy Cloud.
"""

import json

import scrapy

from radarlicencias.items import MallorcaLicenseItem

START_URL = "https://www.caib.es/cathosfront/cens?lang=ES"

FILTER_URL = "https://www.caib.es/cathosfront/services/censo/establecimientos/filter"
# API endpoint for ficha JSON
FICHA_API_URL_TEMPLATE = "https://www.caib.es/cathosfront/services/censo/establecimientos/{establecimiento_id}"
# Human-facing ficha URL (what you see in the browser)
FICHA_PAGE_URL_TEMPLATE = "https://www.caib.es/cathosfront/cens?id={establecimiento_id}"

ROWS_PER_PAGE = 50

def _normalize_status(raw: str) -> str:
    """Normalize current_status / estado to a clean label (e.g. 'Activa', 'Baja temporal')."""
    if not raw:
        return ""
    s = " ".join(raw.strip().split())
    low = s.lower()
    # JSON "estado" uses codes like "ALTA", "BAJA", etc. Map them too.
    if "alta" in low or "activa" in low:
        # If it is active, keep a clean 'Activa' regardless of surrounding text.
        return "Activa"
    if "baja" in low and "temporal" in low:
        return "Baja temporal"
    if "baixa" in low and "temporal" in low:
        return "Baixa temporal"
    return s


def _extract_entidades_relacionadas_json(entidades):
    """
    entidades: list of dicts from ficha JSON, each with at least
      { "nombre": "...", "relacion": "...", "desde": "..." }.
    Returns (name, relation) for the first one, or ("","") if none.
    """
    if not isinstance(entidades, list) or not entidades:
        return "", ""
    first = entidades[0] or {}
    # JSON uses entidadNombre / tipoRelacion
    name = (first.get("entidadNombre") or first.get("nombre") or "").strip()
    relation = (first.get("tipoRelacion") or first.get("relacion") or "").strip()
    return " ".join(name.split()), " ".join(relation.split())


class ConsejoMallorcaSpider(scrapy.Spider):
    name = "consejo_mallorca"
    allowed_domains = ["www.caib.es", "caib.es"]
    start_urls = [START_URL]

    # High concurrency + minimal waits. Tuned for max safe speed.
    custom_settings = {
        # Let this spider use higher per-domain concurrency than default.
        "CONCURRENT_REQUESTS_PER_DOMAIN": 32,
        "ROBOTSTXT_OBEY": True,
        "AUTOTHROTTLE_ENABLED": True,
        # Target around 32 concurrent in-flight requests.
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 32,
        "AUTOTHROTTLE_MAX_CONCURRENCY": 40,
        "AUTOTHROTTLE_START_DELAY": 0.2,
        # Disable Zyte API for this spider explicitly
        "ZYTE_API_ENABLED": False,
        # Use Scrapy's built-in HTTP/1.1 handlers instead of Zyte's
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
            "https": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
        },
    }

    def start_requests(self):
        # Optional: -a start_page=, -a max_pages= for testing.
        start_page = int(getattr(self, "start_page", 1))
        max_pages = getattr(self, "max_pages", None)
        if max_pages is not None:
            max_pages = int(max_pages)

        page = start_page
        if max_pages is not None and page > max_pages:
            return

        payload = {
            "idSubtipoEstablecimientoWeb": "",
            "idCategoriaEstablecimiento": "",
            "signatura": "",
            "denominacionComercial": "",
            "idMunicipio": "",
            "direccion": "",
            "pagina": page,
            "resultados": ROWS_PER_PAGE,
        }
        yield scrapy.Request(
            FILTER_URL,
            method="POST",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            callback=self.parse_list,
            errback=self.handle_list_error,
            meta={
                "page_number": page,
                "max_pages": max_pages,
            },
        )

    def parse_list(self, response):
        if response.status != 200:
            self.logger.warning("List API %s returned status %s", response.url, response.status)
            return

        page_number = response.meta.get("page_number", 1)
        max_pages = response.meta.get("max_pages", None)

        try:
            data = json.loads(response.text)
        except Exception as exc:
            self.logger.error("Failed to decode JSON on page %s: %s", page_number, exc)
            return

        # The response shape is not fully documented; try common patterns:
        # 1) {"resultados": [...], "total": ...}
        # 2) {"content": [...], ...}
        # 3) plain list [...]
        records = []
        if isinstance(data, dict):
            if isinstance(data.get("resultados"), list):
                records = data["resultados"]
            elif isinstance(data.get("content"), list):
                records = data["content"]
            elif isinstance(data.get("establecimientos"), list):
                records = data["establecimientos"]
        elif isinstance(data, list):
            records = data

        if not records:
            self.logger.info("No records on page %s; stopping.", page_number)
            return

        for rec in records:
            if not isinstance(rec, dict):
                continue
            # Names guessed from likely JSON keys; keep robust fallbacks.
            estab_id = rec.get("id") or rec.get("idEstablecimiento") or rec.get("idCenso")
            if not estab_id:
                continue

            signature = (rec.get("signatura") or rec.get("signature") or "").strip()
            commercial_name = (rec.get("denominacionComercial") or "").strip()
            municipality = (rec.get("municipio") or rec.get("municipi") or "").strip()
            address = (rec.get("direccion") or rec.get("adreca") or "").strip()

            signature = " ".join(signature.split()) if signature else ""

            ficha_api_url = FICHA_API_URL_TEMPLATE.format(establecimiento_id=estab_id)
            ficha_page_url = FICHA_PAGE_URL_TEMPLATE.format(establecimiento_id=estab_id)

            yield scrapy.Request(
                ficha_api_url,
                callback=self.parse_ficha,
                errback=self.handle_ficha_error,
                meta={
                    "list_data": {
                        "signature": signature,
                        "commercial_name": commercial_name,
                        "municipality": municipality,
                        "address": address,
                        # Expose the browser URL in results
                        "ficha_url": ficha_page_url,
                    },
                },
            headers={
                # Mimic the Ajax headers the site expects for ficha JSON.
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/json;charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": START_URL,
            },
                dont_filter=False,
            )

        # Pagination: if we got a full page of results, try next page, respecting max_pages if given.
        if len(records) < ROWS_PER_PAGE:
            self.logger.info(
                "Page %s returned %s < %s records; assuming last page.",
                page_number,
                len(records),
                ROWS_PER_PAGE,
            )
            return

        next_page = page_number + 1
        if max_pages is not None and next_page > max_pages:
            self.logger.info("Reached user max_pages=%s; stopping.", max_pages)
            return

        payload = {
            "idSubtipoEstablecimientoWeb": "",
            "idCategoriaEstablecimiento": "",
            "signatura": "",
            "denominacionComercial": "",
            "idMunicipio": "",
            "direccion": "",
            "pagina": next_page,
            "resultados": ROWS_PER_PAGE,
        }
        self.logger.info("Scheduling next list page %s", next_page)
        yield scrapy.Request(
            FILTER_URL,
            method="POST",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            callback=self.parse_list,
            errback=self.handle_list_error,
            meta={
                "page_number": next_page,
                "max_pages": max_pages,
            },
            dont_filter=True,
        )

    def parse_ficha(self, response):
        """Parse ficha JSON and yield one item with list data + Estado actual, unidades, plazas, desde."""
        if response.status != 200:
            self.logger.warning("Ficha API %s returned status %s", response.url, response.status)
        list_data = response.meta.get("list_data") or {}

        try:
            data = json.loads(response.text)
        except Exception as exc:
            self.logger.error("Failed to decode ficha JSON %s: %s", response.url, exc)
            data = {}

        item = MallorcaLicenseItem(
            signature=list_data.get("signature", ""),
            commercial_name=list_data.get("commercial_name", ""),
            municipality=list_data.get("municipality", ""),
            address=list_data.get("address", ""),
            ficha_url=list_data.get("ficha_url", ""),
        )

        # Map JSON fields to our ficha fields where possible.
        raw_status = data.get("estadoActual") or data.get("estado") or ""
        norm_status = _normalize_status(raw_status)
        if norm_status:
            item["current_status"] = norm_status

        # Number of units / places: from "datos" list with etiquetas UNIDADES / PLAZAS.
        datos = data.get("datos") or []
        num_unidades = None
        num_plazas = None
        for d in datos:
            if not isinstance(d, dict):
                continue
            etiqueta = (d.get("etiqueta") or "").upper()
            valor = d.get("valor")
            if etiqueta == "UNIDADES":
                num_unidades = valor
            elif etiqueta == "PLAZAS":
                num_plazas = valor
        if num_unidades is not None:
            item["number_of_units"] = str(num_unidades)
        if num_plazas is not None:
            item["number_of_places"] = str(num_plazas)

        # Activity start date
        act_date = data.get("inicioActividad") or data.get("fechaInicioActividad")
        if act_date:
            item["activity_start_date"] = str(act_date)

        # Locality, group
        locality = data.get("localidad") or data.get("localitat")
        group = data.get("grup") or data.get("grupo")
        if locality:
            item["locality"] = locality
        if group:
            item["group"] = group

        # Entidades relacionadas (first entity only)
        name, relation = _extract_entidades_relacionadas_json(
            data.get("entidades") or data.get("entidadesRelacionadas") or data.get("entitatsRelacionades") or []
        )
        if name:
            item["related_entity_name"] = name
        if relation:
            item["related_entity_relation"] = relation

        yield item

    def handle_ficha_error(self, failure):
        """On ficha request failure, yield item with list data only (no ficha fields)."""
        request = getattr(failure, "request", None)
        list_data = request.meta.get("list_data", {}) if request else {}
        self.logger.warning(
            "Ficha request failed: url=%s signature=%s",
            request.url if request else "unknown",
            list_data.get("signature", ""),
        )
        yield MallorcaLicenseItem(
            signature=list_data.get("signature", ""),
            commercial_name=list_data.get("commercial_name", ""),
            municipality=list_data.get("municipality", ""),
            address=list_data.get("address", ""),
            ficha_url=list_data.get("ficha_url", ""),
        )

    def handle_list_error(self, failure):
        """Log failed list/page requests for re-run or debugging."""
        request = getattr(failure, "request", None)
        self.logger.error(
            "Consejo request failed: url=%s page=%s reason=%s",
            request.url if request else "unknown",
            request.meta.get("page_number", "") if request else "",
            failure.getTraceback(),
        )

