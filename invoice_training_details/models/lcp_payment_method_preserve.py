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
    def _onchange_preserve_lcp_inputs_on_payment_method(self):
        """Changing Cash/CLC must never wipe user-entered LCP inputs."""
        for line in self:
            origin = line._origin
            if not origin or not origin.id:
                continue

            for field_name in LCP_NUMERIC_INPUT_FIELDS:
                current = line[field_name]
                previous = origin[field_name]
                if current in (False, None, 0, 0.0) and previous not in (False, None, 0, 0.0):
                    line[field_name] = previous

    def write(self, vals):
        if 'payment_method' not in vals:
            return super().write(vals)

        result = True
        for line in self:
            safe_vals = dict(vals)
            for field_name in LCP_NUMERIC_INPUT_FIELDS:
                if field_name not in safe_vals:
                    continue
                new_value = safe_vals[field_name]
                old_value = line[field_name]
                if new_value in (False, None, 0, 0.0) and old_value not in (False, None, 0, 0.0):
                    safe_vals[field_name] = old_value
            result = super(TrainingCourse, line).write(safe_vals) and result
        return result
