# -*- coding: utf-8 -*-
"""Customer-facing per-training discounts for quotation / sales-order flows.

No changes to LCP partner-cost discounts or to historic invoices.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    nil_customer_discount_type = fields.Selection(
        [('percent', 'Percentage (%)'), ('amount', 'Fixed Amount')],
        string='Customer Discount Type',
        default=False,
        copy=True,
        help='Leave empty to preserve the existing sale-line discount behavior.',
    )
    nil_customer_discount_value = fields.Float(
        string='Customer Discount Value', digits=(16, 2), default=0.0,
    )
    nil_customer_discount_amount = fields.Float(
        string='Customer Discount Amount',
        compute='_compute_nil_customer_discount',
        digits=(16, 2),
    )
    nil_customer_net_price = fields.Float(
        string='Training After Discount',
        compute='_compute_nil_customer_discount',
        digits=(16, 2),
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

    @api.constrains('price', 'nil_customer_discount_type', 'nil_customer_discount_value')
    def _check_nil_customer_discount(self):
        for course in self:
            kind = course.nil_customer_discount_type
            value = course.nil_customer_discount_value
            if value < -0.0000001:
                raise ValidationError(_('Customer discount cannot be negative.'))
            if value and not kind:
                raise ValidationError(_('Select a Customer Discount Type before entering a value.'))
            if kind == 'percent' and value > 100.0000001:
                raise ValidationError(_('Customer discount percentage cannot exceed 100%.'))
            if kind == 'amount' and value > (course.price or 0.0) + 0.0000001:
                raise ValidationError(_('Fixed customer discount cannot exceed the training price.'))

    def _nil_apply_customer_discount_to_sale_vals(self, vals):
        """Mutate only the target training line's price/discount payload.

        For a fixed discount, adjust the unit price proportionally instead of
        using Odoo's rounded percentage discount field. This retains the fixed
        amount's precision for Cash/CLC and existing inclusive-VAT price rules.
        """
        self.ensure_one()
        kind = self.nil_customer_discount_type
        if not kind:
            return vals
        if kind == 'percent':
            vals['discount'] = self.nil_customer_discount_value
        else:
            original = self.price or 0.0
            ratio = self.nil_customer_discount_value / original if original > 0.0 else 0.0
            vals['price_unit'] = (vals.get('price_unit') or 0.0) * (1.0 - ratio)
            vals['discount'] = 0.0
        return vals

    @api.model
    def _nil_snapshot_field_names(self):
        # The snapshot helper explicitly whitelists ordinary fields. Include
        # these inputs so CRM, WO/SO, and invoice snapshots remain independent.
        names = super()._nil_snapshot_field_names()
        return sorted(set(names) | {
            'nil_customer_discount_type', 'nil_customer_discount_value',
        })


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _lcp_sale_lines(self, courses, company):
        lines = super()._lcp_sale_lines(courses, company)
        for course, command in zip(courses, lines):
            if course.nil_customer_discount_type:
                course._nil_apply_customer_discount_to_sale_vals(command[2])
                command[2]['nil_training_customer_discount_applied'] = True
        return lines


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    nil_customer_training_discount_amount = fields.Monetary(
        string='Training Customer Discount',
        currency_field='currency_id',
        compute='_compute_nil_customer_training_totals',
    )
    nil_customer_training_net_total = fields.Monetary(
        string='Training Total After Discount',
        currency_field='currency_id',
        compute='_compute_nil_customer_training_totals',
    )

    @api.depends(
        'training_course_ids.price',
        'training_course_ids.nil_customer_discount_type',
        'training_course_ids.nil_customer_discount_value',
    )
    def _compute_nil_customer_training_totals(self):
        for order in self:
            courses = order.training_course_ids
            order.nil_customer_training_discount_amount = sum(
                courses.mapped('nil_customer_discount_amount')
            )
            order.nil_customer_training_net_total = sum(
                courses.mapped('nil_customer_net_price')
            )

    def synch_order(self):
        # Parent maintains one training line per snapshot and protects unrelated
        # manual order lines. Apply discount only after it has refreshed prices.
        result = super().synch_order()
        for order in self:
            for course in order.training_course_ids:
                line = order.order_line.filtered(
                    lambda candidate: candidate.nil_sync_training_id == course
                )
                if len(line) != 1:
                    continue  # Parent owns ambiguous-line validation.
                if not course.nil_customer_discount_type:
                    if line.nil_training_customer_discount_applied:
                        # Reset only discounts previously managed by this feature.
                        line.write({
                            'discount': 0.0,
                            'nil_training_customer_discount_applied': False,
                        })
                    continue  # Preserve unrelated legacy/manual discounts.

                source = course.source_training_course_id or course
                if source.lead_id and course.lcp_cost_learning_partner:
                    # LCP prices were already discounted by _lcp_sale_lines().
                    # Never apply a fixed amount a second time.
                    if not line.nil_training_customer_discount_applied:
                        line.write({'nil_training_customer_discount_applied': True})
                    continue

                values = course._nil_apply_customer_discount_to_sale_vals({
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                })
                values['nil_training_customer_discount_applied'] = True
                changes = {
                    name: val for name, val in values.items()
                    if abs(val - line[name]) > 0.0000001
                }
                if changes:
                    line.write(changes)
        return result


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    nil_training_customer_discount_applied = fields.Boolean(
        string='Training Customer Discount Applied',
        default=False,
        copy=False,
    )
