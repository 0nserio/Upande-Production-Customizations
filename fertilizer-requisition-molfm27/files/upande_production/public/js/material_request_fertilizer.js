// Fertilizer Application ticket (MOLFM27) on Material Request.
// The section shows when any items row is in the Fertilizer item group;
// the server (production/logic/fertilizer.py) enforces the same rules on save.

const FA_API = "upande_production.production.logic.fertilizer";
const FA_AUTHORIZE_ROLES = ["Production Manager", "Farm Manager", "System Manager"];
const FA_COLLECT_ROLES = [
	"Production Supervisor",
	"SCP Production Supervisor",
	"Supervisor",
	"Production Manager",
	"Farm Manager",
	"System Manager",
];

let fa_groups_promise = null;
function fa_groups() {
	if (!fa_groups_promise) {
		fa_groups_promise = frappe
			.call({ method: `${FA_API}.get_fertilizer_groups` })
			.then((r) => new Set(r.message || []))
			.catch(() => {
				fa_groups_promise = null;
				return new Set();
			});
	}
	return fa_groups_promise;
}

const fa_has_role = (roles) => roles.some((r) => frappe.user.has_role(r));

async function fa_sync(frm) {
	if (frm.doc.docstatus !== 0) return;
	const groups = await fa_groups();
	const is_fert = (frm.doc.items || []).some((r) => r.item_group && groups.has(r.item_group)) ? 1 : 0;
	if (cint(frm.doc.production_is_fertilizer_request) !== is_fert) {
		await frm.set_value("production_is_fertilizer_request", is_fert);
	}
	if (is_fert && frm.doc.material_request_type !== "Material Issue") {
		await frm.set_value("material_request_type", "Material Issue");
	}
	fa_update_rates(frm);
}

function fa_update_rates(frm) {
	if (frm.doc.docstatus !== 0 || !cint(frm.doc.production_is_fertilizer_request)) return;
	const area = flt(frm.doc.production_fa_area_ha);
	(frm.doc.items || []).forEach((row) => {
		const rate = area > 0 ? flt(flt(row.qty) / area, 3) : 0;
		if (flt(row.production_rate_per_ha) !== rate) {
			frappe.model.set_value(row.doctype, row.name, "production_rate_per_ha", rate);
		}
	});
}

function fa_app_week(frm) {
	if (frm.doc.docstatus !== 0 || !frm.doc.transaction_date) return;
	// ISO week, same as the server's iso_of()
	const d = moment(frm.doc.transaction_date);
	if (cint(frm.doc.production_fa_app_week) !== d.isoWeek()) {
		frm.set_value("production_fa_app_week", d.isoWeek());
	}
}

function fa_sign_off_buttons(frm) {
	if (!cint(frm.doc.production_is_fertilizer_request) || frm.is_new()) return;
	const group = __("Fertilizer Ticket");
	const d = frm.doc;

	if (d.docstatus === 0 && !d.production_fa_authorized_by && !frm.is_dirty() && fa_has_role(FA_AUTHORIZE_ROLES)) {
		frm.add_custom_button(
			__("Authorize"),
			() =>
				frappe.confirm(
					__("Give technical authorization for {0}? Your name and the time are recorded on the ticket.", [d.name]),
					() => frappe.call({ method: `${FA_API}.authorize`, args: { name: d.name } }).then(() => frm.reload_doc())
				),
			group
		);
	}
	if (d.docstatus === 1 && d.production_fa_issued_by && !d.production_fa_collected_by && fa_has_role(FA_COLLECT_ROLES)) {
		frm.add_custom_button(
			__("Mark Collected"),
			() =>
				frappe.confirm(__("Confirm you have collected the fertilizer for {0}?", [d.name]), () =>
					frappe.call({ method: `${FA_API}.mark_collected`, args: { name: d.name } }).then(() => frm.reload_doc())
				),
			group
		);
	}
	if (d.docstatus === 1 && d.production_fa_collected_by && !d.production_fa_application_date && fa_has_role(FA_COLLECT_ROLES)) {
		frm.add_custom_button(
			__("Mark Applied"),
			() =>
				frappe.prompt(
					{
						fieldname: "application_date",
						fieldtype: "Date",
						label: __("Actual Date of Application"),
						reqd: 1,
						default: frappe.datetime.get_today(),
					},
					(v) =>
						frappe
							.call({
								method: `${FA_API}.mark_applied`,
								args: { name: d.name, application_date: v.application_date },
							})
							.then(() => frm.reload_doc()),
					__("Fertilizer applied"),
					__("Save")
				),
			group
		);
	}

	const steps = [
		[__("Prepared"), d.production_fa_prepared_by],
		[__("Authorized"), d.production_fa_authorized_by],
		[__("Issued"), d.production_fa_issued_by],
		[__("Collected"), d.production_fa_collected_by],
		[__("Applied"), d.production_fa_application_date],
	];
	const next = steps.find(([, done]) => !done);
	frm.dashboard.add_indicator(
		next ? __("Fertilizer ticket: waiting for {0}", [next[0]]) : __("Fertilizer ticket: applied"),
		next ? "orange" : "green"
	);
}

frappe.ui.form.on("Material Request", {
	setup(frm) {
		frm.set_query("production_fa_block", () => ({
			filters: { is_group: 0, status: "Active" },
		}));
	},
	onload(frm) {
		fa_groups();
	},
	refresh(frm) {
		fa_sync(frm);
		fa_sign_off_buttons(frm);
	},
	items_remove: fa_sync,
	transaction_date: fa_app_week,
	production_fa_block: fa_update_rates,
	production_fa_area_ha: fa_update_rates,
	production_is_fertilizer_request(frm) {
		fa_app_week(frm);
	},
});

frappe.ui.form.on("Material Request Item", {
	item_group: fa_sync,
	item_code: fa_sync,
	qty: fa_update_rates,
});
