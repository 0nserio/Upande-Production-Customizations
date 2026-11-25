import unittest

import frappe

from upande_production.production.logic.fertilizer import app_week, rate_per_ha, ticket_errors

FERT = {"Fertilizer"}


def _ticket(**kw):
	base = {
		"material_request_type": "Material Issue",
		"production_fa_block": "P1-B1",
		"production_fa_area_ha": 2.13,
		"production_fa_eq_injector_pump": 1,
		"production_fa_m_fertigation": 1,
		"production_fa_t_top_dressing": 1,
	}
	base.update(kw)
	return frappe._dict(base)


class TestFertilizerTicket(unittest.TestCase):
	def test_app_week_is_iso_week(self):
		self.assertEqual(app_week("2026-11-25"), 48)
		self.assertEqual(app_week("2027-01-02"), 53)
		self.assertEqual(app_week(None), 0)

	def test_rate_per_ha(self):
		self.assertEqual(rate_per_ha(42.6, 2.13), 20.0)
		self.assertEqual(rate_per_ha(10, 3), 3.333)
		self.assertEqual(rate_per_ha(10, 0), 0.0)

	def test_complete_ticket_has_no_errors(self):
		self.assertEqual(ticket_errors(_ticket(), ["Fertilizer", "Fertilizer"], FERT), [])

	def test_mixed_items_are_rejected(self):
		errors = ticket_errors(_ticket(), ["Fertilizer", "Consumables", "Fertilizer", "Chemicals"], FERT)
		self.assertEqual(len(errors), 1)
		self.assertIn("2, 4", errors[0])

	def test_purpose_block_and_area_required(self):
		errors = ticket_errors(
			_ticket(material_request_type="Purchase", production_fa_block=None, production_fa_area_ha=0), ["Fertilizer"], FERT
		)
		self.assertEqual(len(errors), 3)

	def test_each_tick_group_needs_one_tick(self):
		doc = _ticket(production_fa_eq_injector_pump=0, production_fa_m_fertigation=0, production_fa_t_top_dressing=0)
		self.assertEqual(len(ticket_errors(doc, ["Fertilizer"], FERT)), 3)

	def test_several_ticks_allowed(self):
		doc = _ticket(production_fa_m_broadcasting=1, production_fa_m_banding=1, production_fa_t_marking=1)
		self.assertEqual(ticket_errors(doc, ["Fertilizer"], FERT), [])

	def test_others_needs_detail(self):
		doc = _ticket(production_fa_eq_others=1)
		self.assertEqual(len(ticket_errors(doc, ["Fertilizer"], FERT)), 1)
		doc.production_fa_eq_others_detail = "Tractor spreader"
		self.assertEqual(ticket_errors(doc, ["Fertilizer"], FERT), [])
