# -*- coding: utf-8 -*-

from odoo import fields, models


class PurchaseOrderSubject(models.Model):
    _inherit = "purchase.order"

    nil_po_subject = fields.Char(
        string="Subject",
        help="Optional subject printed between the Purchase Order details and item table.",
        copy=True,
    )
