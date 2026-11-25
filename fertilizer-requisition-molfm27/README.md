# Fertilizer Requisition (MOLFM27) on Material Request

Puts Mutara Orchards' paper **Fertilizer Advice** ticket (MOLFM27) and **Input Issuance Record** (MOLFM07) into ERPNext, as part of the `upande_production` Frappe app.

Built and tested on Frappe / ERPNext v16.

## What it does

When a Material Request contains an item from the **Fertilizer** item group (or a group under it), a **Fertilizer Application (MOLFM27)** section appears on the form.

- **One block, fertilizer only:** the request must be a Material Issue for a single block, and can hold fertilizer items only.
- **Ticket details:** Block, Farm, Location, Area (ha), Crop, Crop Stage, App Week No and Operator. Farm, crop and area fill in from the block (Production Unit).
- **Tick boxes:** equipment, method of application and type of application, the same options as the paper form. You can tick more than one in each group, and at least one is required in each.
- **Rate (Qty/ha):** worked out on each item row as qty ÷ area.
- **Cost:** the block's cost center goes on the request and on the stock issue, so the fertilizer cost lands on the block.

### Sign-offs

| Paper line | How it is recorded |
|---|---|
| Prepared by | Automatically, from whoever creates the request |
| Technical Authorization by | **Authorize** button, for Production Manager or Farm Manager. The request cannot be approved without it. |
| Issued by (Stores person) | Automatically, when the Stock Entry against the request is submitted |
| Collected by (Supervisor) | **Mark Collected** button, available once the request has been issued |
| Actual Date of Application | **Mark Applied** button, available once collected. The date can't be in the future or before the advice date, and can only be recorded once. |

Each sign-off records the user and the time, and adds a line to the request's activity log. The site's existing Material Request workflow is not changed.

### Print format and report

- **Print format "MOLFM27 Fertilizer Advice":** a copy of the paper ticket, including the Field/FSQM/2 document-control footer.
- **Report "Input Issuance Record" (MOLFM07):** every Material Issue with its requisition, block, and who authorized, issued and collected it. It doesn't cover returns or the condition columns yet.

## What's in this folder

| Path | What it is |
|---|---|
| `upande_production-fertilizer.patch` | The full change as a git patch against `upande_production` (includes `hooks.py` and the fixtures) |
| `fertilizer_custom_fields.json` | The 47 custom fields on their own (Material Request, Material Request Item, Item) |
| `files/` | The new files, at the same paths they have inside the app |

## How to apply

From the `upande_production` app folder:

```bash
git apply /path/to/upande_production-fertilizer.patch
```

Then on the site:

```bash
bench --site <site> execute frappe.utils.fixtures.sync_fixtures --kwargs "{'app': 'upande_production'}"
bench --site <site> reload-doc production print_format molfm27_fertilizer_advice
bench --site <site> reload-doc production report input_issuance_record
bench --site <site> clear-cache
```

(`bench migrate` does the same, but also runs every other pending patch on the site.)

After applying:

- **Fill in Fertilizer Composition** on each fertilizer item (e.g. `N-P-K 13-2-44`) so it prints on the ticket.
- **Check roles:** Production Manager or Farm Manager is needed to authorize, and a supervisor role (e.g. Production Supervisor) to collect and mark applied.

## Tests

```bash
cd sites
../env/bin/python -m unittest upande_production.production.tests.test_fertilizer_ticket
```
