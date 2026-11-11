# -*- coding: utf-8 -*-

from odoo import api, models


LCP_NUMERIC_INPUT_FIELDS = (
    'lcp_vat_rate',
    'lcp_clcs_per_seat',
    'lcp_rate_card_per_seat',
    'lcp_partner_share_pct',
    'lcp_partner_cash_cost',
    'lcp_instructor_md_rate',
    'lcp_vendor_instructor_day',
    'lcp_uber_day_rate',
    'lcp_per_diem_rate',
    'lcp_per_diem_days',
    'lcp_venue_cost',
    'lcp_catering_cost',
)


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    @api.onchange('payment_method')
    def _onchange_reset_lcp_inputs_on_payment_method(self):
        """Changing Cash/CLC always starts the manual LCP numeric inputs from zero."""
        for line in self:
            for field_name in LCP_NUMERIC_INPUT_FIELDS:
                line[field_name] = 0

    def write(self, vals):
        if 'payment_method' not in vals:
            return super().write(vals)

        result = True
        for line in self:
            safe_vals = dict(vals)
            new_method = safe_vals.get('payment_method')
            if new_method != line.payment_method:
                for field_name in LCP_NUMERIC_INPUT_FIELDS:
                    safe_vals[field_name] = 0
            result = super(TrainingCourse, line).write(safe_vals) and result
        return result
