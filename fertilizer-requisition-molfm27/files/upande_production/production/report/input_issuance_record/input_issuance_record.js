frappe.query_reports["Input Issuance Record"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "item_group",
			label: __("Category of Input"),
			fieldtype: "Link",
			options: "Item Group",
			default: "Fertilizer",
		},
		{
			fieldname: "warehouse",
			label: __("From Store"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({ filters: { is_group: 0 } }),
		},
		{
			fieldname: "block",
			label: __("Block"),
			fieldtype: "Link",
			options: "Production Unit",
			get_query: () => ({ filters: { is_group: 0 } }),
		},
	],
};
