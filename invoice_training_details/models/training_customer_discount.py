# -*- coding: utf-8 -*-
"""Customer discounts belong to sale.order.line, not training.course.

Keep legacy training fields for old data; do not backfill or modify old records.
"""
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
        string='Subtotal Before Discount', currency_field='currency_id',
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
        'amount_untaxed', 'order_line.display_type',
        'order_line.price_unit', 'order_line.product_uom_qty',
        'order_line.discount', 'order_line.currency_id',
    )
    def _compute_nil_order_discount_totals(self):
        for order in self:
            lines = order.order_line.filtered(lambda line: not line.display_type)
            discount = sum(lines.mapped('nil_line_discount_amount'))
            order.nil_order_discount_amount = discount
            order.nil_order_subtotal_before_discount = order.amount_untaxed + discount
            order.nil_customer_training_discount_amount = discount
            order.nil_customer_training_net_total = order.amount_untaxed


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

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
        string='Discount Amount', currency_field='currency_id',
        compute='_compute_nil_line_discount_amount',
    )

    def _nil_untaxed_before_discount(self):
        self.ensure_one()
        total = self.price_unit * self.product_uom_qty
        if self.tax_id:
            total = self.tax_id.compute_all(
                self.price_unit, currency=self.currency_id,
                quantity=self.product_uom_qty, product=self.product_id,
                partner=self.order_id.partner_id,
            )['total_excluded']
        return total

    @api.depends(
        'price_unit', 'product_uom_qty', 'discount', 'price_subtotal',
        'tax_id', 'product_id', 'order_id.partner_id', 'currency_id', 'display_type',
    )
    def _compute_nil_line_discount_amount(self):
        for line in self:
            if line.display_type:
                line.nil_line_discount_amount = 0.0
                continue
            raw = max(0.0, line._nil_untaxed_before_discount() - line.price_subtotal)
            line.nil_line_discount_amount = (
                line.currency_id.round(raw) if line.currency_id else raw
            )

    def _nil_discount_percent(self):
        """Use native Odoo line.discount so tax/total/invoice stay consistent."""
        self.ensure_one()
        if self.nil_discount_type == 'percent':
            return self.nil_discount_value
        if self.nil_discount_type == 'amount':
            base = self._nil_untaxed_before_discount()
            return 100.0 * self.nil_discount_value / base if base > 0 else 0.0
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
            if kind == 'amount' and value > line._nil_untaxed_before_discount() + 0.0000001:
                raise ValidationError(_('Fixed discount cannot exceed the order line amount.'))

    @api.onchange('nil_discount_type', 'nil_discount_value', 'price_unit', 'product_uom_qty')
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

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('nil_skip_customer_discount_sync'):
            if any('nil_discount_type' in vals or 'nil_discount_value' in vals for vals in vals_list):
                lines._nil_sync_order_line_discount()
        return lines

    def write(self, vals):
        relevant = {
            'nil_discount_type', 'nil_discount_value', 'price_unit',
            'product_uom_qty', 'discount',
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
