# -*- coding: utf-8 -*-
"""Customer discounts belong to sale.order.line, not training.course.

Keep legacy training fields for old data; do not backfill or modify old records.
"""
import math

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    # Previously installed fields stay readable, but never drive new prices.
    nil_customer_discount_type = fields.Selection(
        [('percent', 'Percentage (%)'), ('amount', 'Fixed Amount')],
        string='Legacy Training Discount Type', copy=False,
    )
    nil_customer_discount_value = fields.Float(
        string='Legacy Training Discount Value', digits=(16, 2), copy=False,
    )
    nil_customer_discount_amount = fields.Float(
        string='Legacy Training Discount Amount',
        compute='_compute_nil_customer_discount', digits=(16, 2),
    )
    nil_customer_net_price = fields.Float(
        string='Legacy Training After Discount',
        compute='_compute_nil_customer_discount', digits=(16, 2),
    )

    @api.depends('price', 'nil_customer_discount_type', 'nil_customer_discount_value')
    def _compute_nil_customer_discount(self):
        for course in self:
            amount = 0.0
            if course.nil_customer_discount_type == 'percent':
                amount = (course.price or 0.0) * course.nil_customer_discount_value / 100.0
            elif course.nil_customer_discount_type == 'amount':
                amount = course.nil_customer_discount_value
            course.nil_customer_discount_amount = amount
            course.nil_customer_net_price = (course.price or 0.0) - amount


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    nil_order_discount_amount = fields.Monetary(
        string='Order Lines Discount', currency_field='currency_id',
        compute='_compute_nil_order_discount_totals',
    )
    nil_order_subtotal_before_discount = fields.Monetary(
        string='Total Before Discount (incl. VAT)', currency_field='currency_id',
        compute='_compute_nil_order_discount_totals',
    )
    # Compatibility with old nonstored fields, now computed from Order Lines.
    nil_customer_training_discount_amount = fields.Monetary(
        string='Order Lines Discount', currency_field='currency_id',
        compute='_compute_nil_order_discount_totals',
    )
    nil_customer_training_net_total = fields.Monetary(
        string='Untaxed Subtotal After Discount', currency_field='currency_id',
        compute='_compute_nil_order_discount_totals',
    )

    @api.depends(
        'amount_total', 'order_line.display_type',
        'order_line.price_unit', 'order_line.product_uom_qty',
        'order_line.discount', 'order_line.currency_id', 'order_line.price_total',
    )
    def _compute_nil_order_discount_totals(self):
        for order in self:
            lines = order.order_line.filtered(lambda line: not line.display_type)
            discount = sum(lines.mapped('nil_line_discount_amount'))
            order.nil_order_discount_amount = discount
            order.nil_order_subtotal_before_discount = order.amount_total + discount
            order.nil_customer_training_discount_amount = discount
            order.nil_customer_training_net_total = order.amount_untaxed


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Odoo's original 'Discount' decimal precision is commonly two digits.
    # Fixed discounts cannot be represented precisely at 2 decimal percent.
    # Preserve 12 decimal places through the order and invoice pipeline.
    discount = fields.Float(digits=(16, 12))

    # Legacy flag remains, avoiding schema loss and double-discounting.
    nil_training_customer_discount_applied = fields.Boolean(
        string='Legacy Training Discount Applied', default=False, copy=False,
    )
    nil_discount_type = fields.Selection(
        [('percent', 'Percentage (%)'), ('amount', 'Fixed Amount')],
        string='Discount Type', copy=False,
        help='Applies exclusively to this order line.',
    )
    nil_discount_value = fields.Float(
        string='Discount Value', digits=(16, 2), default=0.0, copy=False,
        help='A percentage or fixed amount in the order currency.',
    )
    nil_discount_managed = fields.Boolean(default=False, copy=False)
    nil_original_discount_percent = fields.Float(default=0.0, copy=False)
    nil_line_discount_amount = fields.Monetary(
        string='Discount Amount (incl. VAT)', currency_field='currency_id',
        compute='_compute_nil_line_discount_amount',
    )

    def _nil_line_total_at_discount(self, percent):
        """Total with VAT/CLC rules at a candidate native discount percent.

        Fixed amount is a reduction in the *payable* line total, not a
        reduction in the untaxed amount plus an extra VAT reduction.
        """
        self.ensure_one()
        discounted_unit = self.price_unit * (1.0 - percent / 100.0)
        if self.tax_id:
            totals = self.tax_id.compute_all(
                discounted_unit, currency=self.currency_id,
                quantity=self.product_uom_qty, product=self.product_id,
                partner=self.order_id.partner_id,
            )
            total = totals['total_included']
            if self.order_id and self.order_id._nil_is_clc_pricelist_quote():
                # The existing CLC override rounds positive VAT up per line.
                raw_tax = total - totals['total_excluded']
                if raw_tax > 0:
                    total = totals['total_excluded'] + math.ceil(round(raw_tax, 8))
        else:
            total = discounted_unit * self.product_uom_qty
        return self.currency_id.round(total) if self.currency_id else total

    def _nil_gross_before_discount(self):
        return self._nil_line_total_at_discount(0.0)

    @api.depends(
        'price_unit', 'product_uom_qty', 'discount', 'price_total',
        'tax_id', 'product_id', 'order_id.partner_id', 'currency_id', 'display_type',
        'order_id.pricelist_id', 'order_id.opportunity_id', 'order_id.is_training_so',
    )
    def _compute_nil_line_discount_amount(self):
        for line in self:
            if line.display_type:
                line.nil_line_discount_amount = 0.0
                continue
            raw = max(0.0, line._nil_gross_before_discount() - line.price_total)
            line.nil_line_discount_amount = (
                line.currency_id.round(raw) if line.currency_id else raw
            )

    def _nil_discount_percent(self):
        """Use native Odoo line.discount so tax/total/invoice stay consistent."""
        self.ensure_one()
        if self.nil_discount_type == 'percent':
            return self.nil_discount_value
        if self.nil_discount_type == 'amount':
            original_total = self._nil_gross_before_discount()
            if original_total <= 0:
                return 0.0
            # No VAT: a monetary discount is precisely a share of line total.
            # Never invent tax on lines without tax_id.
            if not self.tax_id:
                return 100.0 * self.nil_discount_value / original_total
            target_total = original_total - self.nil_discount_value
            # Find the precise native % that reduces the VAT-INCLUSIVE total
            # by the requested fixed amount. Never over-discount due to
            # VAT/CLC rounding. Price-unit and tax engine remain unchanged.
            low, high = 0.0, 100.0
            for _step in range(48):
                mid = (low + high) / 2.0
                if self._nil_line_total_at_discount(mid) >= target_total:
                    low = mid
                else:
                    high = mid
            # Tax/CLC monetary totals are rounded. Choose the candidate whose
            # final monetary total is closest to the requested exact target.
            return min(
                (low, high), key=lambda value: (
                    abs(self._nil_line_total_at_discount(value) - target_total),
                    value,
                )
            )
        return None

    @api.constrains('nil_discount_type', 'nil_discount_value', 'price_unit', 'product_uom_qty')
    def _check_nil_order_line_discount(self):
        for line in self:
            kind = line.nil_discount_type
            value = line.nil_discount_value
            if value < 0:
                raise ValidationError(_('Discount cannot be negative.'))
            if value and not kind:
                raise ValidationError(_('Select Discount Type before entering a value.'))
            if kind and value and line.nil_training_customer_discount_applied:
                raise ValidationError(_(
                    'A legacy training discount is already applied to this line. '
                    'Review and restore its undiscounted selling price before adding '
                    'a new order-line discount.'
                ))
            if kind and (line.display_type or line.is_downpayment):
                raise ValidationError(_('Discounts can only be applied to normal order lines.'))
            if kind == 'percent' and value > 100:
                raise ValidationError(_('Percentage discount must be between 0 and 100.'))
            if kind == 'amount' and value > line._nil_gross_before_discount() + 0.0000001:
                raise ValidationError(_('Fixed discount cannot exceed the order line amount.'))

    @api.onchange('nil_discount_type', 'nil_discount_value', 'price_unit', 'product_uom_qty', 'tax_id')
    def _onchange_nil_order_line_discount(self):
        for line in self:
            percent = line._nil_discount_percent()
            if percent is not None:
                if not line.nil_discount_managed:
                    line.nil_original_discount_percent = line.discount
                line.discount = percent
                line.nil_discount_managed = True
            elif line.nil_discount_managed:
                line.discount = line.nil_original_discount_percent
                line.nil_original_discount_percent = 0.0
                line.nil_discount_managed = False
                line.nil_discount_value = 0.0

    def _nil_verify_fixed_discount(self):
        """Reject a mismatch rather than charging a customer the wrong price."""
        for line in self:
            if line.nil_discount_type != 'amount' or not line.nil_discount_value:
                continue
            actual = line._nil_gross_before_discount() - line.price_total
            currency = line.currency_id
            expected = line.nil_discount_value
            if currency:
                actual = currency.round(actual)
                expected = currency.round(expected)
                mismatch = not currency.is_zero(actual - expected)
            else:
                mismatch = abs(actual - expected) > 0.0000001
            if mismatch:
                raise ValidationError(_(
                    'Fixed discount must be exactly %(expected).2f %(currency)s, '
                    'but the order line calculates %(actual).2f. '
                    'Check price, taxes and CLC rounding.'
                ) % {
                    'expected': expected,
                    'actual': actual,
                    'currency': currency.name if currency else '',
                })

    def _nil_sync_order_line_discount(self):
        # Never change unrelated lines; only sync an explicitly managed input.
        for line in self:
            percent = line._nil_discount_percent()
            changes = {}
            if percent is not None:
                if not line.nil_discount_managed:
                    changes['nil_original_discount_percent'] = line.discount
                    changes['nil_discount_managed'] = True
                if abs(line.discount - percent) > 0.00000001:
                    changes['discount'] = percent
            elif line.nil_discount_managed:
                changes = {
                    'discount': line.nil_original_discount_percent,
                    'nil_discount_managed': False,
                    'nil_original_discount_percent': 0.0,
                    'nil_discount_value': 0.0,
                }
            if changes:
                line.with_context(nil_skip_customer_discount_sync=True).write(changes)
            # Read the final Odoo-computed price_total, not the input percent.
            line._nil_verify_fixed_discount()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('nil_skip_customer_discount_sync'):
            if any('nil_discount_type' in vals or 'nil_discount_value' in vals for vals in vals_list):
                lines._nil_sync_order_line_discount()
        return lines

    def write(self, vals):
        if 'nil_discount_type' in vals and not vals['nil_discount_type'] and 'nil_discount_value' not in vals:
            vals = dict(vals, nil_discount_value=0.0)
        relevant = {
            'nil_discount_type', 'nil_discount_value', 'price_unit',
            'product_uom_qty', 'discount', 'tax_id',
        }
        needs_sync = bool(relevant.intersection(vals)) and not self.env.context.get(
            'nil_skip_customer_discount_sync'
        )
        if needs_sync:
            for line in self:
                if not (line.nil_discount_type or vals.get('nil_discount_type') or
                        line.nil_discount_managed or 'nil_discount_value' in vals):
                    continue
                if any(inv.move_id.state == 'posted' for inv in line.invoice_lines):
                    raise UserError(_(
                        'Cannot change a managed order-line discount after its invoice is posted.'
                    ))
        result = super().write(vals)
        if needs_sync:
            self._nil_sync_order_line_discount()
        return result

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # sale.order.line._prepare_invoice_line transfers discount percentage as
    # is. Without matching precision, an invoice can silently re-round it.
    # This only expands decimal precision, not invoice totals/posted locks.
    discount = fields.Float(digits=(16, 12))
