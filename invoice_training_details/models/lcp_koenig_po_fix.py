# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def action_new_purchase_order(self):
        self.ensure_one()

        cash_courses = self.training_course_ids.filtered(
            lambda course: course.payment_method == 'cash'
        )
        if not cash_courses:
            return super().action_new_purchase_order()

        code = self._lcp_partner_code(cash_courses)
        if code != 'Koenig':
            return super().action_new_purchase_order()

        # KOENIG CASH ONLY:
        # - NEVER read, calculate, autofill, or overwrite Training Price.
        # - The actual PO Order Line value is exactly the LCP Partner Share.
        # Create the draft PO immediately so product/vendor onchanges cannot
        # replace the Partner Share with another purchase price in the form.
        partner = self._lcp_partner('Koenig')
        usd = self.env.ref('base.USD')
        lines = []

        for course in cash_courses:
            product = course.training_id
            if not product:
                raise UserError(_('Every Cash Training must have a Training Name.'))

            partner_share = course.lcp_partner_share or 0.0
            lines.append((0, 0, {
                'product_id': product.id,
                'name': product.display_name or course.name or self.name,
                'product_qty': 1,
                'product_uom': product.uom_po_id.id or product.uom_id.id,
                'price_unit': partner_share,
                'date_planned': fields.Datetime.now(),
            }))

        po = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'origin': self.name,
            'currency_id': usd.id,
            'crm_lead_id': self.id,
            'is_training_order': True,
            'po_training_type': 'training_vendor',
            'training_course_ids': [(6, 0, cash_courses.ids)],
            'order_line': lines,
            'term_and_cond': self._lcp_koenig_po_terms(cash_courses),
            'display_training_table': True,
            'display_total': True,
        })

        # Final hard guarantee on the saved draft PO lines: line N = course N
        # and its unit price equals that course's Partner Share, exactly.
        for po_line, course in zip(po.order_line, cash_courses):
            partner_share = course.lcp_partner_share or 0.0
            if po_line.price_unit != partner_share:
                po_line.write({'price_unit': partner_share})

        return {
            'type': 'ir.actions.act_window',
            'name': _('New PO'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': po.id,
            'target': 'current',
        }
