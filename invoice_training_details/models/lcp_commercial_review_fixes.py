# -*- coding: utf-8 -*-

from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def write(self, vals):
        """Keep auto-generated Cash prices in sync when Ordering Party changes.

        The commercial automation layer already updates the VAT on an Ordering
        Party change. This final layer also refreshes a Training Price when it
        was generated automatically, while preserving manually edited prices.
        """
        result = super().write(vals)

        if 'ordering_partner_id' in vals:
            for lead in self:
                for course in lead.training_course_ids.filtered(
                    lambda line: line.payment_method == 'cash'
                ):
                    course._lcp_apply_country_vat()
                    if course.lcp_auto_price_generated or not course.price:
                        course._lcp_autofill_cash_price_if_blank()

        return result

    def action_new_instructor_purchase_order(self):
        """Preload the instructor PO accounting line from the LCP total.

        This makes the PO amount visible immediately and keeps the standard
        instructor-fee synchronization idempotent when the PO is saved.
        Marco keeps the special Incentive Vendor Bill flow from the previous
        layer.
        """
        action = super().action_new_instructor_purchase_order()

        if action.get('res_model') != 'purchase.order' or action.get('res_id'):
            return action

        course = self._lcp_instructor_course()
        instructor = course.instructor_id
        product = course.training_id
        if not product or not instructor:
            return action

        if course.lcp_instructor_source == 'nil_me':
            rate = course.lcp_instructor_md_rate or 0.0
            total = course.lcp_total_instructor_md or 0.0
        else:
            rate = course.lcp_vendor_instructor_day or 0.0
            total = course.lcp_total_vendor_instructor or 0.0

        days = course._lcp_line_days()
        if not days or not rate or not total:
            return action

        description = [
            'Instructor Fee',
            'Training: %s' % (product.display_name or course.name or self.name),
            'Instructor: %s' % instructor.name,
        ]
        if course.training_date_start:
            description.append('From: %s' % course.training_date_start)
        if course.training_date_end:
            description.append('To: %s' % course.training_date_end)
        description.append('Days: %s' % days)

        context = dict(action.get('context') or {})
        context['default_order_line'] = [(0, 0, {
            'product_id': product.id,
            'name': '\n'.join(description),
            'product_qty': days,
            'product_uom': product.uom_po_id.id or product.uom_id.id,
            'price_unit': rate,
            'date_planned': fields.Datetime.now(),
            'is_instructor_fee_line': True,
        })]
        action['context'] = context
        return action
