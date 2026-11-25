"""Input Issuance Record (MOLFM07): every input issued from a store, with the
requisition it was issued against and who authorized, issued and collected it.
Built from submitted Material Issue stock entries."""

import frappe
from frappe import _
from frappe.utils import getdate
from frappe.utils.nestedset import get_descendants_of


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.from_date and filters.to_date and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date must be on or before To Date."))
	return columns(), data(filters)


def columns():
	return [
		{"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date", "width": 95},
		{"fieldname": "item_code", "label": _("Input"), "fieldtype": "Link", "options": "Item", "width": 110},
		{"fieldname": "item_name", "label": _("Input Name"), "fieldtype": "Data", "width": 170},
		{"fieldname": "item_group", "label": _("Category"), "fieldtype": "Link", "options": "Item Group", "width": 110},
		{"fieldname": "material_request", "label": _("Ref: Allocation"), "fieldtype": "Link", "options": "Material Request", "width": 150},
		{"fieldname": "block", "label": _("Block"), "fieldtype": "Link", "options": "Production Unit", "width": 90},
		{"fieldname": "authorized_by", "label": _("Authorized by"), "fieldtype": "Data", "width": 140},
		{"fieldname": "qty", "label": _("Quantity"), "fieldtype": "Float", "width": 90},
		{"fieldname": "uom", "label": _("UOM"), "fieldtype": "Link", "options": "UOM", "width": 60},
		{"fieldname": "issued_by", "label": _("Issued by"), "fieldtype": "Data", "width": 140},
		{"fieldname": "collected_by", "label": _("Collected by"), "fieldtype": "Data", "width": 140},
		{"fieldname": "application_date", "label": _("Applied on"), "fieldtype": "Date", "width": 95},
		{"fieldname": "s_warehouse", "label": _("From Store"), "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"fieldname": "stock_entry", "label": _("Stock Entry"), "fieldtype": "Link", "options": "Stock Entry", "width": 150},
	]


def data(filters):
	se = frappe.qb.DocType("Stock Entry")
	sed = frappe.qb.DocType("Stock Entry Detail")
	mr = frappe.qb.DocType("Material Request")
	q = (
		frappe.qb.from_(sed)
		.join(se).on(se.name == sed.parent)
		.left_join(mr).on(mr.name == sed.material_request)
		.select(
			se.posting_date,
			sed.item_code,
			sed.item_name,
			sed.material_request,
			sed.qty,
			sed.uom,
			sed.s_warehouse,
			se.name.as_("stock_entry"),
			se.owner.as_("se_owner"),
			mr.production_fa_block.as_("block"),
			mr.production_fa_authorized_by.as_("authorized_by"),
			mr.production_fa_issued_by.as_("issued_by"),
			mr.production_fa_collected_by.as_("collected_by"),
			mr.production_fa_application_date.as_("application_date"),
		)
		.where((se.docstatus == 1) & (se.purpose == "Material Issue"))
		.orderby(se.posting_date)
		.orderby(se.posting_time)
		.orderby(sed.idx)
	)
	if filters.company:
		q = q.where(se.company == filters.company)
	if filters.from_date:
		q = q.where(se.posting_date >= filters.from_date)
	if filters.to_date:
		q = q.where(se.posting_date <= filters.to_date)
	if filters.warehouse:
		q = q.where(sed.s_warehouse == filters.warehouse)
	if filters.block:
		q = q.where(mr.production_fa_block == filters.block)
	if filters.item_group:
		groups = [filters.item_group, *get_descendants_of("Item Group", filters.item_group)]
		item = frappe.qb.DocType("Item")
		q = q.join(item).on(item.name == sed.item_code).where(item.item_group.isin(groups))

	rows = q.run(as_dict=True)
	groups = dict(
		frappe.get_all("Item", filters={"name": ["in", list({r.item_code for r in rows}) or [""]]}, fields=["name", "item_group"], as_list=True)
	)
	names = {}

	def full_name(user):
		if not user:
			return None
		if user not in names:
			names[user] = frappe.db.get_value("User", user, "full_name") or user
		return names[user]

	for r in rows:
		r.item_group = groups.get(r.item_code)
		r.authorized_by = full_name(r.authorized_by)
		r.issued_by = full_name(r.issued_by or r.se_owner)
		r.collected_by = full_name(r.collected_by)
		del r["se_owner"]
	return rows
