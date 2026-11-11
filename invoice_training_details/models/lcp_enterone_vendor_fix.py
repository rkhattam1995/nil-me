# -*- coding: utf-8 -*-

from odoo import api, models


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    @api.depends(
        'payment_method',
        'price',
        'lcp_cost_learning_partner',
        'lcp_partner_share_pct',
        'lcp_instructor_source',
        'lcp_total_rate_card',
        'lcp_total_instructor_md',
        'lcp_ticket_total',
        'lcp_hotel_total',
    )
    def _compute_lcp_per_training(self):
        """
        Final EnterOne CLC correction.

        Vendor instructor cost is already included in the Rate Card, so it
        must NOT be deducted again before the manual EnterOne split. Only a
        NIL ME instructor is a deductible instructor amount. Flight/hotel
        remain deductible exactly as shown in the EnterOne SO terms.
        """
        super()._compute_lcp_per_training()

        for line in self:
            if not (
                line.payment_method == 'clc'
                and line.lcp_cost_learning_partner == 'EnterOne'
            ):
                continue

            operational_costs = (
                (line.lcp_total_costs or 0.0)
                - (line.lcp_partner_share or 0.0)
            )

            deductible_instructor = (
                line.lcp_total_instructor_md or 0.0
                if line.lcp_instructor_source == 'nil_me'
                else 0.0
            )

            share_base = max(
                (line.lcp_total_rate_card or 0.0)
                - deductible_instructor
                - (line.lcp_ticket_total or 0.0)
                - (line.lcp_hotel_total or 0.0),
                0.0,
            )

            partner_share = (
                share_base
                * (line.lcp_partner_share_pct or 0.0)
                / 100.0
            )
            revenue = line.price or 0.0
            total_costs = operational_costs + partner_share
            profit = revenue - total_costs

            line.lcp_partner_share = partner_share
            line.lcp_total_costs = total_costs
            line.lcp_nilme_profit = profit
            line.lcp_profit_margin = (
                profit / revenue
                if revenue
                else 0.0
            )
