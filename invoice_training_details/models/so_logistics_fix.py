# -*- coding: utf-8 -*-

from odoo import api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('ticket_ids.price', 'hotel_ids.price', 'cost')
    def _compute_total(self):
        """
        Keep each SO logistics total independent.

        The legacy implementation accumulated ticket/hotel values across
        records and returned zero when only tickets or only hotels existed.
        """
        for order in self:
            ticket_total = sum(order.ticket_ids.mapped('price'))
            hotel_total = sum(order.hotel_ids.mapped('price'))
            order.total_price_all = (
                ticket_total
                + hotel_total
                + (order.cost or 0.0)
            )
