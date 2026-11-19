# -*- coding: utf-8 -*-
"""Informational required down payment on NIL training quotations / sales orders.

This does not invoice, allocate or reconcile a payment.
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    nil_required_downpayment_type = fields.Selection(
        [('percent', 'Percentage (%)'), ('amount', 'Fixed Amount')],
        string='Required Down Payment Type',
        copy=False,
        help='Customer advance requested for this quotation/order. '
             'Does not create a down-payment invoice or change order totals.',
    )
    nil_required_downpayment_value = fields.Float(
        string='Required Down Payment Value',
        digits=(16, 2), default=0.0, copy=False,
        help='Enter a percentage of the final order total or a fixed amount '
             'in the order currency.',
    )
    nil_required_downpayment_amount = fields.Monetary(
        string='Required Down Payment',
        currency_field='currency_id',
        compute='_compute_nil_required_downpayment_amount',
        help='Amount requested, calculated from the final total including '
             'discount and tax. Does not reduce Total Amount.',
    )

    @api.depends(
        'nil_required_downpayment_type', 'nil_required_downpayment_value',
        'amount_total', 'currency_id',
    )
    def _compute_nil_required_downpayment_amount(self):
        for order in self:
            kind = order.nil_required_downpayment_type
            value = order.nil_required_downpayment_value or 0.0
            if kind == 'percent':
                amount = (order.amount_total or 0.0) * value / 100.0
            elif kind == 'amount':
                amount = value
            else:
                amount = 0.0
            order.nil_required_downpayment_amount = (
                order.currency_id.round(amount) if order.currency_id else amount
            )

    @api.constrains('nil_required_downpayment_type', 'nil_required_downpayment_value')
    def _check_nil_required_downpayment(self):
        for order in self:
            kind = order.nil_required_downpayment_type
            value = order.nil_required_downpayment_value
            if value < 0:
                raise ValidationError(_('Required down payment cannot be negative.'))
            if value and not kind:
                raise ValidationError(_(
                    'Select Required Down Payment Type before entering a value.'
                ))
            if kind == 'percent' and value > 100:
                raise ValidationError(_(
                    'Required down payment percentage cannot exceed 100%.'
                ))
            if kind == 'amount' and value > order.amount_total + 0.0000001:
                raise ValidationError(_(
                    'Required fixed down payment cannot exceed the order total.'
                ))
