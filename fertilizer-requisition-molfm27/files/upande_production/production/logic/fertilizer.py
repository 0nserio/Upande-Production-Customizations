"""Fertilizer Application ticket (MOLFM27) on Material Request.

A Material Request whose items are in the Fertilizer item group (or a group
under it) is a fertilizer requisition. It must be a Material Issue for one
block, contain fertilizer only, and carry the ticket fields from the paper
form. The four paper sign-offs are recorded on the request itself:

    Prepared by      who created the request
    Authorized by    technical authorization, required before submit
    Issued by        who submitted the Stock Entry against it
    Collected by     supervisor confirms collection after issue
    Application date entered when the fertilizer has been applied

The site's Material Request workflow is left alone; these steps sit beside it.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from upande_production.production.logic.weeks import iso_of

FERTILIZER_ROOT_GROUP = "Fertilizer"
REQUEST_TYPE = "Material Issue"
AUTHORIZE_ROLES = ("Production Manager", "Farm Manager", "System Manager")
COLLECT_ROLES = (
	"Production Supervisor",
	"SCP Production Supervisor",
	"Supervisor",
	"Production Manager",
	"Farm Manager",
	"System Manager",
)

# (fieldname, paper label) for each tick-box group on MOLFM27.
EQUIPMENT = (
	("production_fa_eq_graduated_container", "Graduated container"),
	("production_fa_eq_knapsack", "Knapsack"),
	("production_fa_eq_injector_pump", "Injector Pump"),
	("production_fa_eq_others", "Others"),
)
METHODS = (
	("production_fa_m_broadcasting", "Broadcasting"),
	("production_fa_m_drilling", "Drilling"),
	("production_fa_m_foliar", "Spraying (foliar)"),
	("production_fa_m_fertigation", "Fertigation"),
	("production_fa_m_banding", "Banding"),
)
APPLICATION_TYPES = (
	("production_fa_t_base_dressing", "Base dressing"),
	("production_fa_t_top_dressing", "Top dressing"),
	("production_fa_t_marking", "Marking"),
)
TICK_GROUPS = (
	(_("Equipment / Machinery Used"), EQUIPMENT),
	(_("Method of Application"), METHODS),
	(_("Type of Application"), APPLICATION_TYPES),
)


# ---------------------------------------------------------------- pure helpers


def app_week(transaction_date) -> int:
	"""ISO week number printed as 'App Week No' on the ticket."""
	return iso_of(transaction_date)[1] if transaction_date else 0


def rate_per_ha(qty, area_ha) -> float:
	area = flt(area_ha)
	return round(flt(qty) / area, 3) if area > 0 else 0.0


def ticked(doc, group) -> list[str]:
	return [label for fieldname, label in group if cint(doc.get(fieldname))]


def ticket_errors(doc, row_groups, fertilizer_groups) -> list[str]:
	"""Rule check for a fertilizer request. `row_groups` is the item group of
	each items row, in order. Returns readable messages; empty means valid."""
	errors = []
	others = [i + 1 for i, g in enumerate(row_groups) if g not in fertilizer_groups]
	if others:
		errors.append(
			_("A fertilizer requisition can only hold fertilizer items. Move row(s) {0} to a separate Material Request.").format(
				", ".join(str(i) for i in others)
			)
		)
	if doc.get("material_request_type") != REQUEST_TYPE:
		errors.append(_("A fertilizer requisition must have Purpose set to {0}.").format(REQUEST_TYPE))
	if not doc.get("production_fa_block"):
		errors.append(_("Select the Block the fertilizer is for."))
	if flt(doc.get("production_fa_area_ha")) <= 0:
		errors.append(_("Area (ha) must be more than 0."))
	for label, group in TICK_GROUPS:
		if not ticked(doc, group):
			errors.append(_("Tick at least one option under {0}.").format(label))
	if cint(doc.get("production_fa_eq_others")) and not (doc.get("production_fa_eq_others_detail") or "").strip():
		errors.append(_("Equipment 'Others' is ticked: say which equipment."))
	return errors


# ---------------------------------------------------------------- lookups


def fertilizer_groups() -> set[str]:
	"""The Fertilizer item group and every group under it (empty if the site has none)."""
	if not frappe.db.exists("Item Group", FERTILIZER_ROOT_GROUP):
		return set()
	from frappe.utils.nestedset import get_descendants_of

	return {FERTILIZER_ROOT_GROUP, *get_descendants_of("Item Group", FERTILIZER_ROOT_GROUP)}


def _row_groups(doc) -> list[str]:
	groups = []
	for row in doc.get("items") or []:
		if not row.item_group and row.item_code:
			row.item_group = frappe.db.get_value("Item", row.item_code, "item_group")
		groups.append(row.item_group)
	return groups


def is_fertilizer_request(doc, groups=None) -> bool:
	groups = fertilizer_groups() if groups is None else groups
	return bool(groups) and any(g in groups for g in _row_groups(doc))


def _has_any_role(roles) -> bool:
	return bool(set(roles) & set(frappe.get_roles()))


# ---------------------------------------------------------------- Material Request hooks


def material_request_validate(doc, method=None):
	groups = fertilizer_groups()
	is_fert = is_fertilizer_request(doc, groups)
	doc.production_is_fertilizer_request = 1 if is_fert else 0
	if not is_fert:
		return

	block = None
	if doc.production_fa_block:
		block = frappe.db.get_value(
			"Production Unit",
			doc.production_fa_block,
			["is_group", "farm", "crop", "area_ha", "cost_center"],
			as_dict=True,
		)
		if not block:
			frappe.throw(_("Block {0} does not exist.").format(doc.production_fa_block))
		if cint(block.is_group):
			frappe.throw(_("{0} is a group. Pick a single block.").format(doc.production_fa_block))
		doc.production_fa_farm = block.farm
		doc.production_fa_crop = block.crop
		if flt(doc.production_fa_area_ha) <= 0:
			doc.production_fa_area_ha = block.area_ha

	errors = ticket_errors(doc, _row_groups(doc), groups)
	if errors:
		frappe.throw("<br>".join(errors), title=_("Fertilizer Application ticket incomplete"))

	doc.production_fa_app_week = app_week(doc.transaction_date)
	for row in doc.items:
		row.production_rate_per_ha = rate_per_ha(row.qty, doc.production_fa_area_ha)
		if block and block.cost_center:
			row.cost_center = block.cost_center
	if block and block.cost_center and doc.meta.has_field("custom_cost_center"):
		doc.custom_cost_center = block.cost_center

	if not doc.production_fa_prepared_by:
		doc.production_fa_prepared_by = doc.owner or frappe.session.user
		doc.production_fa_prepared_on = doc.creation or now_datetime()


def material_request_before_submit(doc, method=None):
	if cint(doc.production_is_fertilizer_request) and not doc.production_fa_authorized_by:
		frappe.throw(
			_("This fertilizer requisition needs technical authorization before it can be approved. Ask a {0} to click Authorize.").format(
				_(" or ").join(AUTHORIZE_ROLES[:2])
			),
			title=_("Not authorized yet"),
		)


# ---------------------------------------------------------------- Stock Entry hooks


def _fertilizer_requests(stock_entry) -> dict[str, frappe._dict]:
	names = {r.material_request for r in stock_entry.get("items") or [] if r.get("material_request")}
	if not names:
		return {}
	rows = frappe.get_all(
		"Material Request",
		filters={"name": ["in", list(names)], "production_is_fertilizer_request": 1},
		fields=["name", "production_fa_block", "production_fa_issued_by"],
	)
	return {r.name: r for r in rows}


def stock_entry_validate(doc, method=None):
	requests = _fertilizer_requests(doc)
	if not requests:
		return
	has_unit = frappe.get_meta("Stock Entry Detail").has_field("production_unit")
	for row in doc.items:
		mr = requests.get(row.get("material_request"))
		if not mr or not mr.production_fa_block:
			continue
		if has_unit:
			row.production_unit = mr.production_fa_block
		if not row.cost_center:
			row.cost_center = frappe.db.get_value("Production Unit", mr.production_fa_block, "cost_center")


def stock_entry_on_submit(doc, method=None):
	for mr in _fertilizer_requests(doc).values():
		if not mr.production_fa_issued_by:
			frappe.db.set_value(
				"Material Request",
				mr.name,
				{"production_fa_issued_by": frappe.session.user, "production_fa_issued_on": now_datetime()},
			)


def stock_entry_on_cancel(doc, method=None):
	for mr in _fertilizer_requests(doc).values():
		still_issued = frappe.db.sql(
			"""select 1 from `tabStock Entry Detail` d join `tabStock Entry` s on s.name = d.parent
			where d.material_request = %s and s.docstatus = 1 and s.name != %s limit 1""",
			(mr.name, doc.name),
		)
		if still_issued:
			continue
		if frappe.db.get_value("Material Request", mr.name, "production_fa_collected_by"):
			frappe.throw(
				_("{0} has already been collected by the supervisor, so its issue cannot be cancelled.").format(mr.name)
			)
		frappe.db.set_value(
			"Material Request", mr.name, {"production_fa_issued_by": None, "production_fa_issued_on": None}
		)


# ---------------------------------------------------------------- sign-off actions


def _load_request(name):
	doc = frappe.get_doc("Material Request", name)
	doc.check_permission("read")
	if not cint(doc.production_is_fertilizer_request):
		frappe.throw(_("{0} is not a fertilizer requisition.").format(name))
	return doc


@frappe.whitelist()
def get_fertilizer_groups():
	return sorted(fertilizer_groups())


@frappe.whitelist()
def authorize(name):
	doc = _load_request(name)
	if not _has_any_role(AUTHORIZE_ROLES):
		frappe.throw(_("Only a {0} can give technical authorization.").format(_(" or ").join(AUTHORIZE_ROLES[:2])), frappe.PermissionError)
	if doc.docstatus != 0:
		frappe.throw(_("{0} is already submitted.").format(name))
	if doc.production_fa_authorized_by:
		frappe.throw(_("{0} was already authorized by {1}.").format(name, doc.production_fa_authorized_by))
	doc.db_set(
		{"production_fa_authorized_by": frappe.session.user, "production_fa_authorized_on": now_datetime()},
		notify=True,
	)
	doc.add_comment("Info", _("Technical authorization given (MOLFM27)."))


@frappe.whitelist()
def mark_collected(name):
	doc = _load_request(name)
	if not _has_any_role(COLLECT_ROLES):
		frappe.throw(_("Only a supervisor can confirm collection."), frappe.PermissionError)
	if not doc.production_fa_issued_by:
		frappe.throw(_("The stores have not issued {0} yet.").format(name))
	if doc.production_fa_collected_by:
		frappe.throw(_("{0} was already collected by {1}.").format(name, doc.production_fa_collected_by))
	doc.db_set(
		{"production_fa_collected_by": frappe.session.user, "production_fa_collected_on": now_datetime()},
		notify=True,
	)
	doc.add_comment("Info", _("Collected by supervisor (MOLFM27)."))


@frappe.whitelist()
def mark_applied(name, application_date):
	doc = _load_request(name)
	if not _has_any_role(COLLECT_ROLES):
		frappe.throw(_("Only a supervisor can record the application date."), frappe.PermissionError)
	if not doc.production_fa_collected_by:
		frappe.throw(_("Confirm collection before recording the application date."))
	if doc.production_fa_application_date:
		frappe.throw(
			_("{0} already has an application date ({1}).").format(
				name, frappe.format(doc.production_fa_application_date, "Date")
			)
		)
	applied = getdate(application_date)
	if applied > getdate(nowdate()):
		frappe.throw(_("The application date cannot be in the future."))
	if applied < getdate(doc.transaction_date):
		frappe.throw(_("The application date cannot be before the advice date ({0}).").format(doc.transaction_date))
	doc.db_set({"production_fa_application_date": applied}, notify=True)
	doc.add_comment("Info", _("Applied on {0} (MOLFM27).").format(frappe.format(applied, "Date")))
