# -*- coding: utf-8 -*-
"""One editable Professional Services column heading per CRM lead or sales order.

Each individual service continues to store its own nil_custom_value.
"""

from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    nil_ps_custom_heading = fields.Char(
        string="PS Custom Column Heading",
        copy=True,
    )

    nil_ps_custom_heading_2 = fields.Char(
        string="PS Custom Column Heading 2",
        copy=True,
    )

    def _prepare_opportunity_quotation_context(self):
        context = super()._prepare_opportunity_quotation_context()
        if self.nil_ps_custom_heading:
            context["default_nil_ps_custom_heading"] = self.nil_ps_custom_heading
        if self.nil_ps_custom_heading_2:
            context["default_nil_ps_custom_heading_2"] = self.nil_ps_custom_heading_2
        return context


class SaleOrder(models.Model):
    _inherit = "sale.order"

    nil_ps_custom_heading = fields.Char(
        string="PS Custom Column Heading",
        copy=True,
    )

    nil_ps_custom_heading_2 = fields.Char(
        string="PS Custom Column Heading 2",
        copy=True,
    )
