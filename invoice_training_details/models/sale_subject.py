# -*- coding: utf-8 -*-
"""Optional Subject printed on all sale.order quotations and order reports."""

from odoo import fields, models


class SaleOrderSubject(models.Model):
    _inherit = "sale.order"

    nil_so_subject = fields.Char(
        string="Subject",
        help="Optional subject displayed before the item table on Sales reports.",
        copy=True,
    )
