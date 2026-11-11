# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Preserve existing LCP data where the mapping is unambiguous.

    Old LCP inputs lived on crm.lead.  For existing leads that have exactly
    one training line, copy those inputs to that training and attach any old
    unassigned ticket/hotel rows to it.  Multi-training leads are deliberately
    left unassigned because an aggregate historical amount cannot be split
    safely without user input.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Lead = env['crm.lead'].with_context(active_test=False)

    for lead in Lead.search([]):
        lines = lead.training_course_ids
        if len(lines) != 1:
            continue

        line = lines[0]
        vals = {
            'lcp_vat_rate': lead.lcp_vat_rate or 0.0,
            'lcp_clcs_per_seat': lead.lcp_clcs_per_seat or 0.0,
            'lcp_rate_card_per_seat': lead.lcp_rate_card_per_seat or 0.0,
            'lcp_instructor_source': lead.lcp_instructor_source or 'nil_me',
            'lcp_instructor_md_rate': lead.lcp_instructor_md_rate or 0.0,
            'lcp_vendor_instructor_day': lead.lcp_vendor_instructor_day or 0.0,
            'lcp_uber_day_rate': lead.lcp_uber_day_rate or 0.0,
            'lcp_per_diem_rate': lead.lcp_per_diem_rate or 0.0,
            'lcp_per_diem_days': lead.lcp_per_diem_days or 0,
            'lcp_cost_learning_partner': lead.lcp_cost_learning_partner or False,
            'lcp_partner_share_pct': lead.lcp_partner_share_pct or 0.0,
            'lcp_partner_cash_cost': lead.lcp_partner_cash_cost or 0.0,
            'lcp_venue_cost': lead.venue or 0.0,
            'lcp_catering_cost': lead.ctrng or 0.0,
        }

        if not line.instructor_id and lead.instructor_id:
            vals['instructor_id'] = lead.instructor_id.id

        line.write(vals)

        lead.ticket_ids.filtered(
            lambda ticket: not ticket.lcp_training_course_id
        ).write({
            'lcp_training_course_id': line.id,
        })

        lead.hotel_ids.filtered(
            lambda hotel: not hotel.lcp_training_course_id
        ).write({
            'lcp_training_course_id': line.id,
        })
