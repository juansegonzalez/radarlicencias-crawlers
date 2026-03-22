# Airbnb Mallorca: Extracting the Registration Number

## Goal

From each listing detail page we need:

1. **URL** – the listing page URL  
2. **Municipality** – the municipality we used in the search (for matching even if Airbnb shows a different place name)  
3. **Registration number** – the **Mallorca Regional Registration Number** (e.g. ETV/9714), which appears in the **expanded** description.

## Where the registration appears on Airbnb

- In the **listing description** section.
- The description is often **collapsed** with a **“Show more”** button.
- After clicking **“Show more”**, at the end of the description you see something like:
  - **“Mallorca Regional Registration Number”**
  - Just below that: the **license number** (e.g. `ETV/9714`, `ALOY ETV/12460`).

So the scraper must:

1. Open the listing page (with Zyte browser).
2. Click **“Show more”** in the description (Zyte browser action).
3. Get the final **browser HTML** and find the text “Mallorca Regional Registration Number” and the value below it.

## Implementation in the spider

- **Detail requests** use Zyte with `browserHtml: true` and an **actions** array that:
  - Waits a couple of seconds for the page to load.
  - **Clicks** the “Show more” element (XPath/CSS selector).
  - Waits again so the expanded description is in the DOM.
- **Parsing** then runs on the returned HTML:
  - Prefer: regex/text search for “Mallorca Regional Registration Number” and capture the number on the same or next line (e.g. `ETV/12345`).
  - Fallback: search for a pattern like `ETV/\d+` or `ALOY ETV/\d+` in the description block.

## Selectors to refine with a real page

The exact DOM changes over time. To tune the spider it helps to inspect a **real** Mallorca listing:

1. **“Show more” button**  
   - Current placeholder: XPath for a button or link containing the text “Show more”.  
   - If your example page uses a different label (e.g. “Read more”, “Ver más”) or a `data-testid`, update `SHOW_MORE_ACTIONS` in `airbnb_mallorca.py` (and optionally use a data attribute or testid for robustness).

2. **Registration number**  
   - Current: regex on the full HTML for “Mallorca Regional Registration Number” followed by the value, plus fallback for `ETV/\d+`.  
   - If the label or format differs (e.g. “Registration number”, “Número de registro”), extend or add patterns in `REGISTRATION_PATTERN` / `REGISTRATION_FALLBACK`.

If you can share **one example listing URL** that you know shows the registration number after “Show more”, we can:

- Fetch it (e.g. with Zyte) and inspect the HTML structure.
- Adjust the **click** selector and the **regex** so the spider reliably extracts URL, municipality, and registration number for matching with the Consell data.
