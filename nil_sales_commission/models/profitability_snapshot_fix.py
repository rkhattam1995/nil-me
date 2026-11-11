# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SalesCommission(models.Model):
    _inherit = 'nil.sales.commission'

    # Read-only LCP display. Nothing in the underlying LCP is modified.
    profit_total_rate_card = fields.Float(
        string='Total Rate Card', compute='_compute_profit_margin_summary', compute_sudo=True)
    profit_partner_share = fields.Float(
        string='Partner Share', compute='_compute_profit_margin_summary', compute_sudo=True)
    profit_instructor_cost = fields.Float(
        string='Instructor Cost', compute='_compute_profit_margin_summary', compute_sudo=True)
    profit_logistics_cost = fields.Float(
        string='Logistics Cost', compute='_compute_profit_margin_summary', compute_sudo=True)
    profit_ticket_cost = fields.Float(
        string='Tickets', compute='_compute_profit_margin_summary', compute_sudo=True)
    profit_hotel_cost = fields.Float(
        string='Hotels', compute='_compute_profit_margin_summary', compute_sudo=True)
    profit_per_diem_cost = fields.Float(
        string='Per Diem', compute='_compute_profit_margin_summary', compute_sudo=True)
    profit_uber_cost = fields.Float(
        string='Uber', compute='_compute_profit_margin_summary', compute_sudo=True)
    profit_venue_cost = fields.Float(
        string='Venue', compute='_compute_profit_margin_summary', compute_sudo=True)
    profit_catering_cost = fields.Float(
        string='Catering', compute='_compute_profit_margin_summary', compute_sudo=True)

    @api.depends(
        'invoice_id',
        'invoice_id.training_course_ids',
        'invoice_id.training_course_ids.source_training_course_id',
        'invoice_id.training_course_ids.snapshot_lcp_total_costs',
        'invoice_id.training_course_ids.snapshot_lcp_profit',
        'invoice_id.training_course_ids.snapshot_lcp_rate_card',
        'lead_id',
        'lead_id.training_course_ids',
        'lead_id.training_course_ids.lcp_total_costs',
        'lead_id.training_course_ids.lcp_nilme_profit',
        'lead_id.training_course_ids.lcp_total_rate_card',
        'lead_id.training_course_ids.lcp_cost_learning_partner',
        'lead_id.training_course_ids.lcp_partner_share',
        'lead_id.training_course_ids.lcp_total_instructor_cost',
        'lead_id.training_course_ids.lcp_total_logistics',
        'lead_id.training_course_ids.lcp_ticket_total',
        'lead_id.training_course_ids.lcp_hotel_total',
        'lead_id.training_course_ids.lcp_total_per_diem',
        'lead_id.training_course_ids.lcp_total_uber_estimate',
        'lead_id.training_course_ids.lcp_venue_cost',
        'lead_id.training_course_ids.lcp_catering_cost',
        'lead_id.training_course_ids.lcp_profit_margin',
    )
    def _compute_profit_margin_summary(self):
        for rec in self:
            invoice_courses = (
                rec.invoice_id.sudo().training_course_ids
                if rec.invoice_id else self.env['training.course']
            )
            source_courses = invoice_courses.mapped(
                'source_training_course_id').exists()
            lead = (
                rec.lead_id.sudo() if rec.lead_id
                else rec.invoice_id._nil_get_commission_lead().sudo()
                if rec.invoice_id else self.env['crm.lead']
            )
            courses = (
                source_courses
                or (lead.training_course_ids.sudo() if lead else self.env['training.course'])
                or invoice_courses
            )
            partners = sorted(
                set(courses.mapped('lcp_cost_learning_partner')) - {False, ''}
            )
            costs = sum(courses.mapped('lcp_total_costs'))
            profit = sum(courses.mapped('lcp_nilme_profit'))
            rate_card = sum(courses.mapped('lcp_total_rate_card'))
            partner_share = sum(courses.mapped('lcp_partner_share'))
            instructor = sum(courses.mapped('lcp_total_instructor_cost'))
            logistics = sum(courses.mapped('lcp_total_logistics'))
            tickets = sum(courses.mapped('lcp_ticket_total'))
            hotels = sum(courses.mapped('lcp_hotel_total'))
            per_diem = sum(courses.mapped('lcp_total_per_diem'))
            uber = sum(courses.mapped('lcp_total_uber_estimate'))
            venue = sum(courses.mapped('lcp_venue_cost'))
            catering = sum(courses.mapped('lcp_catering_cost'))
            revenue = sum(courses.mapped('price'))
            margin = (
                courses.lcp_profit_margin if len(courses) == 1
                else profit / revenue if revenue else 0.0
            )

            # Older LCPs stored their final results on the CRM Lead, not
            # on the related individual training rows.
            if lead and not costs and lead.lcp_total_costs:
                costs = lead.lcp_total_costs
                profit = lead.lcp_nilme_profit
                margin = lead.lcp_profit_margin
                partner_share = lead.lcp_partner_share
                instructor = lead.lcp_total_instructor_cost
                logistics = lead.lcp_total_logistics
                tickets = lead.lcp_ticket_total
                hotels = lead.lcp_hotel_total
                per_diem = lead.lcp_total_per_diem
                uber = lead.lcp_total_uber_estimate
                if not rate_card:
                    rate_card = lead.lcp_total_rate_card
                if not partners and lead.lcp_cost_learning_partner:
                    partners = [lead.lcp_cost_learning_partner]

            # Some invoice snapshots predate LCP cost freezing; avoid
            # selecting stale zero-cost snapshot values over live LCP.
            if invoice_courses and not costs:
                frozen = invoice_courses.filtered(
                    lambda c: bool(c.snapshot_lcp_total_costs)
                )
                if frozen:
                    costs = sum(frozen.mapped('snapshot_lcp_total_costs'))
                    profit = sum(frozen.mapped('snapshot_lcp_profit'))
                    partner_share = sum(frozen.mapped('snapshot_lcp_partner_share'))
                    logistics = sum(frozen.mapped('snapshot_lcp_logistics'))
                    frozen_revenue = sum(frozen.mapped('snapshot_lcp_revenue'))
                    margin = profit / frozen_revenue if frozen_revenue else 0.0
                    frozen_rate = sum(frozen.mapped('snapshot_lcp_rate_card'))
                    if frozen_rate:
                        rate_card = frozen_rate
                    frozen_partners = sorted(
                        set(frozen.mapped('snapshot_lcp_learning_partner')) - {False, ''}
                    )
                    if frozen_partners:
                        partners = frozen_partners

            # Read old cost.details results only if no populated per-training
            # or lead-level LCP values exist. Never recompute their formulas.
            if lead and not costs and lead.cost_details_ids:
                old = lead.sudo().cost_details_ids.filtered(
                    lambda d: bool(d.margin1)
                )[:1]
                if old:
                    costs = old.margin1
                    profit = old.nilme_share
                    margin = old.margin
                    partner_share = old.training_vendor
                    instructor = old.ins_time
                    logistics = old.total_price_all
                    if old.learning_partner:
                        partners = [old.learning_partner]

            rec.profit_learning_partner = ', '.join(partners)
            rec.profit_total_costs = costs
            rec.profit_nilme_share = profit
            rec.profit_margin_pct = margin
            rec.profit_total_rate_card = rate_card
            rec.profit_partner_share = partner_share
            rec.profit_instructor_cost = instructor
            rec.profit_logistics_cost = logistics
            rec.profit_ticket_cost = tickets
            rec.profit_hotel_cost = hotels
            rec.profit_per_diem_cost = per_diem
            rec.profit_uber_cost = uber
            rec.profit_venue_cost = venue
            rec.profit_catering_cost = catering
