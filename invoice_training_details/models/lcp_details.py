# -*- coding: utf-8 -*-

import math

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # =========================================================
    # LCP PRICING SETUP - MANUAL INPUTS
    # =========================================================

    lcp_vat_rate = fields.Float(
        string='VAT %',
        default=0.0,
    )

    # Payment Method is taken ONLY from Training lines.
    # Payment method rule:
    # if ALL Training lines are CLC -> CLC
    # otherwise -> Cash.
    lcp_payment_method = fields.Selection(
        [
            ('cash', 'Cash'),
            ('clc', 'CLC'),
        ],
        string='Payment Method',
        compute='_compute_lcp_payment_method',
    )

    lcp_is_online = fields.Boolean(
        string='Online Training',
        compute='_compute_lcp_is_online',
    )

    lcp_has_onsite = fields.Boolean(
        string='Has On-site Training',
        compute='_compute_lcp_is_online',
    )

    # MANUAL ONLY.
    # CLC training: shown as "CLCs / Seat"
    # Cash training: shown as "USD / Seat"
    #
    # It is NOT taken from Training clcs_qty or any other existing field.
    lcp_clcs_per_seat = fields.Float(
        string='Seat Rate',
        default=0.0,
    )

    # Used only for CLC training.
    lcp_rate_card_per_seat = fields.Monetary(
        string='Rate Card / Seat',
        currency_field='currency_id',
        default=0.0,
    )

    lcp_instructor_source = fields.Selection(
        [
            ('nil_me', 'NIL ME'),
            ('vendor', 'Vendor'),
        ],
        string='Instructor From',
        default='nil_me',
    )

    # NIL ME ONLY.
    # Label in UI: Instructor Rate
    # Total = Instructor Rate x Total Training Days.
    lcp_instructor_md_rate = fields.Monetary(
        string='Instructor Rate',
        currency_field='currency_id',
        default=0.0,
    )

    # VENDOR ONLY.
    # Total = Vendor Instructor / Day x Total Training Days.
    lcp_vendor_instructor_day = fields.Monetary(
        string='Vendor Instructor / Day',
        currency_field='currency_id',
        default=0.0,
    )

    lcp_uber_day_rate = fields.Monetary(
        string='Uber / Day',
        currency_field='currency_id',
        default=0.0,
    )

    # NIL ME ONLY.
    lcp_per_diem_rate = fields.Monetary(
        string='Per Diem / Day',
        currency_field='currency_id',
        default=0.0,
    )

    # NIL ME ONLY.
    # Manual number of Per Diem days, independent from Training Days.
    lcp_per_diem_days = fields.Integer(
        string='Per Diem Days',
        default=0,
    )

    # =========================================================
    # LCP CALCULATED TOTALS
    # =========================================================

    lcp_total_days = fields.Integer(
        string='Total Training Days',
        compute='_compute_lcp_totals',
    )

    lcp_total_seats = fields.Integer(
        string='Total Seats',
        compute='_compute_lcp_totals',
    )

    # Kept for backward compatibility only.
    # It is intentionally NOT displayed in LCP Summary.
    lcp_total_clcs = fields.Float(
        string='Total CLCs',
        compute='_compute_lcp_totals',
    )

    # CLC ONLY.
    # VAT is applied to GRAND TOTAL CLCs, then rounded UP once.
    lcp_total_clcs_with_vat = fields.Integer(
        string='Total CLCs + VAT',
        compute='_compute_lcp_totals',
    )

    # CLC ONLY.
    lcp_total_rate_card = fields.Monetary(
        string='Total Rate Card',
        currency_field='currency_id',
        compute='_compute_lcp_totals',
    )

    lcp_total_instructor_cost = fields.Monetary(
        string='Instructor Cost',
        currency_field='currency_id',
        compute='_compute_lcp_totals',
    )

    lcp_total_instructor_md = fields.Monetary(
        string='Total Instructor Cost',
        currency_field='currency_id',
        compute='_compute_lcp_totals',
    )

    lcp_total_vendor_instructor = fields.Monetary(
        string='Total Vendor Instructor',
        currency_field='currency_id',
        compute='_compute_lcp_totals',
    )

    lcp_total_per_diem = fields.Monetary(
        string='Total Per Diem',
        currency_field='currency_id',
        compute='_compute_lcp_totals',
    )

    lcp_total_uber_estimate = fields.Monetary(
        string='Uber Logistics',
        currency_field='currency_id',
        compute='_compute_lcp_totals',
    )

    # =========================================================
    # EXISTING LOGISTICS / COST DETAILS RESULTS
    # =========================================================

    lcp_ticket_total = fields.Monetary(
        string='Tickets',
        currency_field='currency_id',
        compute='_compute_lcp_existing_results',
    )

    lcp_hotel_total = fields.Monetary(
        string='Hotels',
        currency_field='currency_id',
        compute='_compute_lcp_existing_results',
    )

    lcp_total_logistics = fields.Monetary(
        string='Total Logistics',
        currency_field='currency_id',
        compute='_compute_lcp_existing_results',
    )

    # Kept under the SAME technical field name used by the existing view.
    # It is now entered directly in LCP and no longer comes from cost.details.
    lcp_cost_learning_partner = fields.Selection(
        [
            ('EnterOne', 'EnterOne'),
            ('Koenig', 'Koenig'),
        ],
        string='Learning Partner',
    )

    # CLC ONLY. Manual percentage, never hard-coded.
    lcp_partner_share_pct = fields.Float(
        string='Partner Share %',
        default=0.0,
    )

    # CASH ONLY. Final all-inclusive amount quoted by the partner.
    lcp_partner_cash_cost = fields.Monetary(
        string='Partner Cost',
        currency_field='currency_id',
        default=0.0,
    )

    lcp_partner_share = fields.Monetary(
        string='Partner Share',
        currency_field='currency_id',
        compute='_compute_lcp_existing_results',
    )

    lcp_total_costs = fields.Monetary(
        string='Total Costs',
        currency_field='currency_id',
        compute='_compute_lcp_existing_results',
    )

    lcp_nilme_profit = fields.Monetary(
        string='NIL ME Profit',
        currency_field='currency_id',
        compute='_compute_lcp_existing_results',
    )

    lcp_profit_margin = fields.Float(
        string='Profit Margin',
        compute='_compute_lcp_existing_results',
    )

    lcp_cost_detail_count = fields.Integer(
        string='Cost Details Count',
        compute='_compute_lcp_existing_results',
    )

    # =========================================================
    # PAYMENT METHOD FROM TRAINING
    # =========================================================

    @api.depends(
        'training_course_ids.payment_method'
    )
    def _compute_lcp_payment_method(self):
        for lead in self:
            methods = lead.training_course_ids.mapped(
                'payment_method'
            )

            if methods and all(
                method == 'clc'
                for method in methods
            ):
                lead.lcp_payment_method = 'clc'
            else:
                lead.lcp_payment_method = 'cash'

    @api.depends(
        'training_course_ids.location'
    )
    def _compute_lcp_is_online(self):
        for lead in self:
            lines = lead.training_course_ids

            lead.lcp_is_online = (
                bool(lines)
                and all(
                    line.location == 'Online'
                    for line in lines
                )
            )

            lead.lcp_has_onsite = (
                bool(lines)
                and any(
                    line.location == 'On site'
                    for line in lines
                )
            )

    # =========================================================
    # TRAINING DAYS HELPER
    # =========================================================

    def _lcp_training_days(self):
        self.ensure_one()

        total_days = 0

        for line in self.training_course_ids:
            if (
                line.training_date_start
                and line.training_date_end
            ):
                total_days += max(
                    (
                        line.training_date_end
                        - line.training_date_start
                    ).days + 1,
                    0,
                )
                continue

            if line.duration:
                first_token = (
                    str(line.duration)
                    .strip()
                    .split(' ')[0]
                )

                try:
                    total_days += max(
                        int(float(first_token)),
                        0,
                    )
                except (TypeError, ValueError):
                    pass

        return total_days

    # =========================================================
    # LCP TOTALS
    # =========================================================

    @api.depends(
        'training_course_ids.training_date_start',
        'training_course_ids.training_date_end',
        'training_course_ids.duration',
        'training_course_ids.no_of_student',
        'training_course_ids.payment_method',
        'training_course_ids.location',
        'lcp_vat_rate',
        'lcp_clcs_per_seat',
        'lcp_rate_card_per_seat',
        'lcp_instructor_source',
        'lcp_instructor_md_rate',
        'lcp_vendor_instructor_day',
        'lcp_uber_day_rate',
        'lcp_per_diem_rate',
        'lcp_per_diem_days',
    )
    def _compute_lcp_totals(self):
        for lead in self:
            total_days = lead._lcp_training_days()

            total_seats = sum(
                max(line.no_of_student or 0, 0)
                for line in lead.training_course_ids
            )

            # =====================================================
            # CLC / CASH SEAT INPUT
            #
            # CLC:
            #   lcp_clcs_per_seat means CLCs / Seat.
            #
            # Cash:
            #   the SAME manual input is displayed as USD / Seat.
            #   No CLC calculation is performed for Cash.
            # =====================================================

            if lead.lcp_payment_method == 'clc':
                total_clcs = (
                    (lead.lcp_clcs_per_seat or 0.0)
                    * total_seats
                )

                clcs_with_vat_raw = (
                    total_clcs
                    * (
                        1.0
                        + (
                            (lead.lcp_vat_rate or 0.0)
                            / 100.0
                        )
                    )
                )

                total_rate_card = (
                    (lead.lcp_rate_card_per_seat or 0.0)
                    * total_seats
                )

                total_clcs_with_vat = (
                    int(math.ceil(clcs_with_vat_raw))
                    if clcs_with_vat_raw > 0
                    else 0
                )

            else:
                total_clcs = 0.0
                total_clcs_with_vat = 0
                total_rate_card = 0.0

            # =====================================================
            # INSTRUCTOR
            #
            # NIL ME:
            # Instructor Rate x Total Training Days
            #
            # Vendor:
            # Vendor Instructor / Day x Total Training Days
            # =====================================================

            if lead.lcp_instructor_source == 'nil_me':
                total_instructor_md = (
                    (lead.lcp_instructor_md_rate or 0.0)
                    * total_days
                )

                total_vendor_instructor = 0.0
                total_instructor_cost = total_instructor_md

                # Per Diem is an on-site cost only.
                total_per_diem = (
                    0.0
                    if lead.lcp_is_online
                    else (
                        (lead.lcp_per_diem_rate or 0.0)
                        * max(
                            lead.lcp_per_diem_days or 0,
                            0,
                        )
                    )
                )

            else:
                total_instructor_md = 0.0
                total_per_diem = 0.0

                total_vendor_instructor = (
                    (
                        lead.lcp_vendor_instructor_day
                        or 0.0
                    )
                    * total_days
                )

                total_instructor_cost = (
                    total_vendor_instructor
                )

            # =====================================================
            # UBER
            # Uber / Day x (Total Training Days + 2)
            # =====================================================

            total_uber = (
                0.0
                if lead.lcp_is_online
                else (
                    (lead.lcp_uber_day_rate or 0.0)
                    * (total_days + 2)
                    if total_days > 0
                    else 0.0
                )
            )

            lead.lcp_total_days = total_days
            lead.lcp_total_seats = total_seats
            lead.lcp_total_clcs = total_clcs
            lead.lcp_total_clcs_with_vat = (
                total_clcs_with_vat
            )
            lead.lcp_total_rate_card = total_rate_card

            lead.lcp_total_instructor_md = (
                total_instructor_md
            )
            lead.lcp_total_vendor_instructor = (
                total_vendor_instructor
            )
            lead.lcp_total_instructor_cost = (
                total_instructor_cost
            )

            lead.lcp_total_per_diem = total_per_diem
            lead.lcp_total_uber_estimate = total_uber

    # =========================================================
    # TRAINING PRICE SYNC FROM LCP
    # If Training Price is empty, fill it from Total Rate Card.
    # Once Training Price has any value, never overwrite it.
    # =========================================================

    def _sync_training_price_from_lcp_if_empty(self):
        for lead in self:
            if (
                lead.lcp_payment_method == 'clc'
                and not lead.total_training_price
                and lead.lcp_total_rate_card
            ):
                lead.with_context(
                    skip_lcp_training_price_sync=True
                ).write({
                    'total_training_price': lead.lcp_total_rate_card,
                })

    @api.onchange(
        'lcp_rate_card_per_seat',
        'training_course_ids',
        'training_course_ids.no_of_student',
        'training_course_ids.payment_method',
    )
    def _onchange_lcp_training_price(self):
        for lead in self:
            if (
                lead.lcp_payment_method == 'clc'
                and not lead.total_training_price
                and lead.lcp_total_rate_card
            ):
                lead.total_training_price = lead.lcp_total_rate_card

    # =========================================================
    # UBER SYNC TO EXISTING LOGISTICS -> UBER
    # =========================================================

    def _get_lcp_uber_amount(self):
        self.ensure_one()

        if len(self.training_course_ids) > 1:
            # Mixed delivery modes calculate Uber only for onsite lines.
            # The old lead-level days include online training as well.
            return sum(
                course.lcp_total_uber_estimate or 0.0
                for course in self.training_course_ids
                if course.location == 'On site'
            )

        total_days = self._lcp_training_days()

        if self.lcp_is_online:
            return 0.0

        if total_days <= 0:
            return 0.0

        return (
            (self.lcp_uber_day_rate or 0.0)
            * (total_days + 2)
        )

    def _sync_lcp_uber_to_logistics(self):
        for lead in self:
            amount = lead._get_lcp_uber_amount()

            if (lead.uber or 0.0) != amount:
                lead.with_context(
                    skip_lcp_uber_sync=True,
                    skip_lcp_logistics_sync=True,
                ).write({
                    'uber': amount,
                })

    @api.onchange(
        'lcp_uber_day_rate',
        'training_course_ids',
        'training_course_ids.training_date_start',
        'training_course_ids.training_date_end',
        'training_course_ids.duration',
        'training_course_ids.location',
    )
    def _onchange_lcp_uber(self):
        for lead in self:
            lead.uber = (
                lead._get_lcp_uber_amount()
            )

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        leads._sync_lcp_uber_to_logistics()

        if not self.env.context.get(
            'skip_lcp_training_price_sync'
        ):
            leads._sync_training_price_from_lcp_if_empty()

        return leads

    def write(self, vals):
        result = super().write(vals)

        if (
            not self.env.context.get(
                'skip_lcp_uber_sync'
            )
            and 'lcp_uber_day_rate' in vals
        ):
            self._sync_lcp_uber_to_logistics()

        if (
            not self.env.context.get(
                'skip_lcp_training_price_sync'
            )
            and 'total_training_price' not in vals
            and {
                'lcp_rate_card_per_seat',
                'training_course_ids',
            }.intersection(vals)
        ):
            self._sync_training_price_from_lcp_if_empty()

        return result

    # =========================================================
    # EXISTING RESULT FIELD NAMES - STANDALONE CALCULATION
    # The field/method names are intentionally preserved so the
    # existing XML and any external references do not need renaming.
    # There is NO dependency on cost.details.
    # =========================================================

    @api.depends(
        'ticket_ids.price',
        'hotel_ids.price',
        'venue',
        'ctrng',
        'total_training_price',
        'uber',
        'lcp_payment_method',
        'lcp_cost_learning_partner',
        'lcp_total_rate_card',
        'lcp_partner_share_pct',
        'lcp_partner_cash_cost',
        'lcp_total_per_diem',
        'lcp_total_instructor_cost',
        'lcp_instructor_source',
        'lcp_is_online',
    )
    def _compute_lcp_existing_results(self):
        for lead in self:
            # On-line training must not carry any on-site cost.
            # Flight, hotel, venue, catering, Uber and per diem are all
            # treated as zero when every training line is Online.
            if lead.lcp_is_online:
                ticket_total = 0.0
                hotel_total = 0.0
                venue_cost = 0.0
                catering_cost = 0.0
                uber_cost = 0.0
                per_diem_cost = 0.0
            else:
                ticket_total = sum(
                    lead.ticket_ids.mapped('price')
                )
                hotel_total = sum(
                    lead.hotel_ids.mapped('price')
                )
                venue_cost = lead.venue or 0.0
                catering_cost = lead.ctrng or 0.0
                uber_cost = lead.uber or 0.0
                per_diem_cost = lead.lcp_total_per_diem or 0.0

            # Operational costs before partner share.
            # Instructor cost is valid for both Online and On-site.
            # Hotel and flight are included only for an NIL ME instructor
            # and only for On-site training.
            nil_me_instructor_costs = 0.0
            if lead.lcp_instructor_source == 'nil_me':
                nil_me_instructor_costs = (
                    (lead.lcp_total_instructor_cost or 0.0)
                    + ticket_total
                    + hotel_total
                )

            operational_costs = (
                nil_me_instructor_costs
                + venue_cost
                + catering_cost
                + uber_cost
                + per_diem_cost
            )

            revenue = lead.total_training_price or 0.0
            net_after_costs = revenue - operational_costs

            # EnterOne: fixed 20% of Total Rate Card after deducting
            # Instructor Cost + Flight/Tickets + Hotel only.
            if lead.lcp_cost_learning_partner == 'EnterOne':
                enterone_share_base = (
                    (lead.lcp_total_rate_card or 0.0)
                    - (lead.lcp_total_instructor_cost or 0.0)
                    - ticket_total
                    - hotel_total
                )
                partner_share = max(enterone_share_base, 0.0) * 0.20
                profit = net_after_costs - partner_share

            # Koenig: keep the existing calculation logic unchanged.
            elif lead.lcp_payment_method == 'clc':
                partner_share = (
                    (lead.lcp_total_rate_card or 0.0)
                    * (lead.lcp_partner_share_pct or 0.0)
                    / 100.0
                )
                profit = net_after_costs - partner_share

            else:
                partner_share = (
                    lead.lcp_partner_cash_cost or 0.0
                )
                profit = net_after_costs - partner_share

            total_costs = operational_costs + partner_share

            # Total Logistics = Uber + Per Diem + Hotel + Flight/Tickets.
            # Hotel and Flight/Tickets apply only when the instructor is from NIL ME,
            # exactly as agreed in the existing costing logic.
            total_logistics = (
                uber_cost
                + per_diem_cost
                + (ticket_total if lead.lcp_instructor_source == 'nil_me' else 0.0)
                + (hotel_total if lead.lcp_instructor_source == 'nil_me' else 0.0)
            )

            lead.lcp_ticket_total = ticket_total
            lead.lcp_hotel_total = hotel_total
            lead.lcp_total_logistics = total_logistics
            lead.lcp_partner_share = partner_share
            lead.lcp_total_costs = total_costs
            lead.lcp_nilme_profit = profit
            lead.lcp_profit_margin = (
                profit / revenue
                if revenue
                else 0.0
            )

            # Legacy technical field kept only so the existing XML
            # remains compatible. It no longer counts cost.details.
            lead.lcp_cost_detail_count = 0

    # =========================================================
    # VALIDATION
    # =========================================================

    @api.constrains(
        'lcp_vat_rate',
        'lcp_clcs_per_seat',
        'lcp_rate_card_per_seat',
        'lcp_instructor_md_rate',
        'lcp_vendor_instructor_day',
        'lcp_uber_day_rate',
        'lcp_per_diem_rate',
        'lcp_per_diem_days',
        'lcp_partner_share_pct',
        'lcp_partner_cash_cost',
    )
    def _check_lcp_values(self):
        for lead in self:
            values = [
                ('VAT %', lead.lcp_vat_rate),
                (
                    'CLCs / Seat or USD / Seat',
                    lead.lcp_clcs_per_seat,
                ),
                (
                    'Rate Card / Seat',
                    lead.lcp_rate_card_per_seat,
                ),
                (
                    'Instructor Rate',
                    lead.lcp_instructor_md_rate,
                ),
                (
                    'Vendor Instructor / Day',
                    lead.lcp_vendor_instructor_day,
                ),
                (
                    'Uber / Day',
                    lead.lcp_uber_day_rate,
                ),
                (
                    'Per Diem / Day',
                    lead.lcp_per_diem_rate,
                ),
                (
                    'Per Diem Days',
                    lead.lcp_per_diem_days,
                ),
                (
                    'Partner Share %',
                    lead.lcp_partner_share_pct,
                ),
                (
                    'Partner Cost',
                    lead.lcp_partner_cash_cost,
                ),
            ]

            for label, value in values:
                if value < 0:
                    raise ValidationError(
                        '%s cannot be negative.'
                        % label
                    )


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    # =========================================================
    # BACKWARD-COMPATIBILITY FIELDS
    # Kept so older stored LCP child views cannot break upgrade.
    # They are NOT used by the current CRM LCP calculations.
    # =========================================================

    lcp_currency_id = fields.Many2one(
        'res.currency',
        string='LCP Currency',
        related='lead_id.currency_id',
        readonly=True,
    )

    lcp_rate_card = fields.Monetary(
        string='Rate Card / Seat',
        currency_field='lcp_currency_id',
    )

    lcp_instructor_rate_day = fields.Monetary(
        string='Instructor Rate / Day',
        currency_field='lcp_currency_id',
    )

    lcp_days = fields.Integer(
        string='Days',
        compute='_compute_lcp_legacy_results',
    )

    lcp_total_rate_card = fields.Monetary(
        string='Total Rate Card',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_legacy_results',
    )

    lcp_total_instructor_cost = fields.Monetary(
        string='Instructor Cost',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_legacy_results',
    )

    @api.depends(
        'training_date_start',
        'training_date_end',
        'duration',
        'no_of_student',
        'lcp_rate_card',
        'lcp_instructor_rate_day',
    )
    def _compute_lcp_legacy_results(self):
        for line in self:
            days = 0

            if (
                line.training_date_start
                and line.training_date_end
            ):
                days = max(
                    (
                        line.training_date_end
                        - line.training_date_start
                    ).days + 1,
                    0,
                )

            elif line.duration:
                first_token = (
                    str(line.duration)
                    .strip()
                    .split(' ')[0]
                )

                try:
                    days = max(
                        int(float(first_token)),
                        0,
                    )
                except (TypeError, ValueError):
                    days = 0

            seats = max(
                line.no_of_student or 0,
                0,
            )

            line.lcp_days = days
            line.lcp_total_rate_card = (
                (line.lcp_rate_card or 0.0)
                * seats
            )
            line.lcp_total_instructor_cost = (
                (
                    line.lcp_instructor_rate_day
                    or 0.0
                )
                * days
            )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)

        leads = lines.mapped('lead_id')
        leads._sync_lcp_uber_to_logistics()
        leads._sync_training_price_from_lcp_if_empty()

        return lines

    def write(self, vals):
        leads_before = self.mapped(
            'lead_id'
        )

        result = super().write(vals)

        leads_after = self.mapped('lead_id')
        affected_leads = leads_before | leads_after

        if {
            'training_date_start',
            'training_date_end',
            'duration',
            'location',
            'lead_id',
        }.intersection(vals):
            affected_leads._sync_lcp_uber_to_logistics()

        if {
            'no_of_student',
            'payment_method',
            'lead_id',
        }.intersection(vals):
            affected_leads._sync_training_price_from_lcp_if_empty()

        return result

    def unlink(self):
        leads = self.mapped('lead_id')

        result = super().unlink()

        leads._sync_lcp_uber_to_logistics()
        leads._sync_training_price_from_lcp_if_empty()

        return result
