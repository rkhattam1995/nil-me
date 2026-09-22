# -*- coding: utf-8 -*-

import math

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    # =========================================================
    # PER-TRAINING LCP INPUTS
    # =========================================================

    lcp_vat_rate = fields.Float(
        string='VAT %',
        default=0.0,
    )

    lcp_clcs_per_seat = fields.Float(
        string='Seat Rate',
        default=0.0,
    )

    lcp_rate_card_per_seat = fields.Monetary(
        string='Rate Card / Seat',
        currency_field='lcp_currency_id',
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

    lcp_instructor_md_rate = fields.Monetary(
        string='Instructor Rate',
        currency_field='lcp_currency_id',
        default=0.0,
    )

    lcp_vendor_instructor_day = fields.Monetary(
        string='Vendor Instructor / Day',
        currency_field='lcp_currency_id',
        default=0.0,
    )

    lcp_uber_day_rate = fields.Monetary(
        string='Uber / Day',
        currency_field='lcp_currency_id',
        default=0.0,
    )

    lcp_per_diem_rate = fields.Monetary(
        string='Per Diem / Day',
        currency_field='lcp_currency_id',
        default=0.0,
    )

    lcp_per_diem_days = fields.Integer(
        string='Per Diem Days',
        default=0,
    )

    lcp_cost_learning_partner = fields.Selection(
        [
            ('EnterOne', 'EnterOne'),
            ('Koenig', 'Koenig'),
        ],
        string='Learning Partner',
    )

    lcp_partner_share_pct = fields.Float(
        string='Partner Share %',
        default=0.0,
    )

    lcp_partner_cash_cost = fields.Monetary(
        string='Partner Cost',
        currency_field='lcp_currency_id',
        default=0.0,
    )

    # Venue/Catering must be per training so two training rows never
    # share or duplicate the same lead-level amount.
    lcp_venue_cost = fields.Monetary(
        string='Venue',
        currency_field='lcp_currency_id',
        default=0.0,
    )

    lcp_catering_cost = fields.Monetary(
        string='Catering',
        currency_field='lcp_currency_id',
        default=0.0,
    )

    # SO# remains the same CRM field and is only exposed through the
    # training card for visual parity with the old LCP.
    lcp_so_no = fields.Char(
        string='SO#',
        related='lead_id.so_no',
        readonly=False,
    )

    # =========================================================
    # PER-TRAINING LCP RESULTS
    # =========================================================

    lcp_is_online = fields.Boolean(
        string='Online Training',
        compute='_compute_lcp_per_training',
    )

    # Override the legacy training.course LCP result fields so they now
    # represent this training line only.
    lcp_days = fields.Integer(
        string='Total Training Days',
        compute='_compute_lcp_per_training',
    )

    lcp_total_seats = fields.Integer(
        string='Total Seats',
        compute='_compute_lcp_per_training',
    )

    lcp_total_clcs = fields.Float(
        string='Total CLCs',
        compute='_compute_lcp_per_training',
    )

    lcp_total_clcs_with_vat = fields.Integer(
        string='Total CLCs + VAT',
        compute='_compute_lcp_per_training',
    )

    lcp_total_rate_card = fields.Monetary(
        string='Total Rate Card',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_total_instructor_cost = fields.Monetary(
        string='Instructor Cost',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_total_instructor_md = fields.Monetary(
        string='Total Instructor Cost',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_total_vendor_instructor = fields.Monetary(
        string='Total Vendor Instructor',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_total_per_diem = fields.Monetary(
        string='Total Per Diem',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_total_uber_estimate = fields.Monetary(
        string='Uber Logistics',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_ticket_total = fields.Monetary(
        string='Tickets',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_hotel_total = fields.Monetary(
        string='Hotels',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_total_logistics = fields.Monetary(
        string='Total Logistics',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_partner_share = fields.Monetary(
        string='Partner Share',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_total_costs = fields.Monetary(
        string='Total Costs',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_nilme_profit = fields.Monetary(
        string='NIL ME Profit',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_per_training',
    )

    lcp_profit_margin = fields.Float(
        string='Profit Margin',
        compute='_compute_lcp_per_training',
    )

    lcp_unassigned_logistics_count = fields.Integer(
        string='Unassigned Logistics',
        compute='_compute_lcp_per_training',
    )

    def _lcp_line_days(self):
        self.ensure_one()

        if self.training_date_start and self.training_date_end:
            return max(
                (self.training_date_end - self.training_date_start).days + 1,
                0,
            )

        if self.duration:
            first_token = str(self.duration).strip().split(' ')[0]
            try:
                return max(int(float(first_token)), 0)
            except (TypeError, ValueError):
                return 0

        return 0

    def _lcp_ticket_records(self):
        self.ensure_one()

        lead = self.lead_id
        if not lead:
            return self.env['ticket.ticket']

        tickets = lead.ticket_ids
        if len(lead.training_course_ids) == 1:
            # Backward compatibility: old single-training leads did not
            # have a Training selector on ticket rows.
            return tickets.filtered(
                lambda ticket: (
                    not ticket.lcp_training_course_id
                    or ticket.lcp_training_course_id == self
                )
            )

        return tickets.filtered(
            lambda ticket: ticket.lcp_training_course_id == self
        )

    def _lcp_hotel_records(self):
        self.ensure_one()

        lead = self.lead_id
        if not lead:
            return self.env['hotel.hotel']

        hotels = lead.hotel_ids
        if len(lead.training_course_ids) == 1:
            # Backward compatibility: old single-training leads did not
            # have a Training selector on hotel rows.
            return hotels.filtered(
                lambda hotel: (
                    not hotel.lcp_training_course_id
                    or hotel.lcp_training_course_id == self
                )
            )

        return hotels.filtered(
            lambda hotel: hotel.lcp_training_course_id == self
        )

    @api.depends(
        'training_date_start',
        'training_date_end',
        'duration',
        'no_of_student',
        'price',
        'training_id.name',
        'payment_method',
        'location',
        'lcp_vat_rate',
        'lcp_clcs_per_seat',
        'lcp_rate_card_per_seat',
        'lcp_instructor_source',
        'lcp_instructor_md_rate',
        'lcp_vendor_instructor_day',
        'lcp_uber_day_rate',
        'lcp_per_diem_rate',
        'lcp_per_diem_days',
        'lcp_cost_learning_partner',
        'lcp_partner_share_pct',
        'lcp_partner_cash_cost',
        'lcp_venue_cost',
        'lcp_catering_cost',
        'lead_id.training_course_ids',
        'lead_id.ticket_ids.price',
        'lead_id.ticket_ids.lcp_training_course_id',
        'lead_id.hotel_ids.price',
        'lead_id.hotel_ids.lcp_training_course_id',
    )
    def _compute_lcp_per_training(self):
        for line in self:
            days = line._lcp_line_days()
            seats = max(line.no_of_student or 0, 0)
            is_online = line.location == 'Online'
            is_cisco_u = 'cisco u' in (
                (line.training_id.name or line.name or '').lower()
            )
            no_logistics = is_online or is_cisco_u

            # Pricing
            if line.payment_method == 'clc':
                total_clcs = (
                    (line.lcp_clcs_per_seat or 0.0)
                    * seats
                )
                clcs_with_vat_raw = (
                    total_clcs
                    * (
                        1.0
                        + ((line.lcp_vat_rate or 0.0) / 100.0)
                    )
                )
                total_clcs_with_vat = (
                    int(math.ceil(clcs_with_vat_raw))
                    if clcs_with_vat_raw > 0
                    else 0
                )
                total_rate_card = (
                    (line.price or 0.0)
                    if is_cisco_u
                    else (
                        (line.lcp_rate_card_per_seat or 0.0)
                        * seats
                    )
                )
            else:
                total_clcs = 0.0
                total_clcs_with_vat = 0
                total_rate_card = 0.0

            # Instructor
            if line.lcp_instructor_source == 'nil_me':
                total_instructor_md = (
                    (line.lcp_instructor_md_rate or 0.0)
                    * days
                )
                total_vendor_instructor = 0.0
                total_instructor_cost = total_instructor_md
                total_per_diem = (
                    0.0
                    if no_logistics
                    else (
                        (line.lcp_per_diem_rate or 0.0)
                        * max(line.lcp_per_diem_days or 0, 0)
                    )
                )
            else:
                total_instructor_md = 0.0
                total_per_diem = 0.0
                total_vendor_instructor = (
                    (line.lcp_vendor_instructor_day or 0.0)
                    * days
                )
                total_instructor_cost = total_vendor_instructor

            # Uber
            total_uber = (
                0.0
                if no_logistics
                else (
                    (line.lcp_uber_day_rate or 0.0)
                    * (days + 2)
                    if days > 0
                    else 0.0
                )
            )

            # Cisco U is a subscription: no flight/hotel/venue/catering logistics.
            # Online training keeps the same no-onsite-logistics behavior.
            if no_logistics:
                ticket_total = 0.0
                hotel_total = 0.0
                venue_cost = 0.0
                catering_cost = 0.0
                unassigned_logistics = 0
            else:
                ticket_total = sum(
                    line._lcp_ticket_records().mapped('price')
                )
                hotel_total = sum(
                    line._lcp_hotel_records().mapped('price')
                )
                venue_cost = line.lcp_venue_cost or 0.0
                catering_cost = line.lcp_catering_cost or 0.0

                lead = line.lead_id
                if lead and len(lead.training_course_ids) > 1:
                    unassigned_logistics = (
                        len(
                            lead.ticket_ids.filtered(
                                lambda ticket: not ticket.lcp_training_course_id
                            )
                        )
                        + len(
                            lead.hotel_ids.filtered(
                                lambda hotel: not hotel.lcp_training_course_id
                            )
                        )
                    )
                else:
                    unassigned_logistics = 0

            # Preserve the existing LCP calculation logic exactly, but
            # apply it to this training line only.
            nil_me_instructor_costs = 0.0
            if line.lcp_instructor_source == 'nil_me':
                nil_me_instructor_costs = (
                    total_instructor_cost
                    + ticket_total
                    + hotel_total
                )

            operational_costs = (
                nil_me_instructor_costs
                + venue_cost
                + catering_cost
                + total_uber
                + total_per_diem
            )

            revenue = line.price or 0.0
            net_after_costs = revenue - operational_costs

            if line.lcp_cost_learning_partner == 'EnterOne':
                enterone_share_base = (
                    total_rate_card
                    - total_instructor_cost
                    - ticket_total
                    - hotel_total
                )
                partner_share = (
                    max(enterone_share_base, 0.0) * 0.20
                )
                profit = net_after_costs - partner_share

            elif line.payment_method == 'clc':
                partner_share = (
                    total_rate_card
                    * (line.lcp_partner_share_pct or 0.0)
                    / 100.0
                )
                profit = net_after_costs - partner_share

            else:
                partner_share = (
                    line.lcp_partner_cash_cost or 0.0
                )
                profit = net_after_costs - partner_share

            total_costs = operational_costs + partner_share

            total_logistics = (
                total_uber
                + total_per_diem
                + (
                    ticket_total
                    if line.lcp_instructor_source == 'nil_me'
                    else 0.0
                )
                + (
                    hotel_total
                    if line.lcp_instructor_source == 'nil_me'
                    else 0.0
                )
            )

            line.lcp_is_online = is_online
            line.lcp_days = days
            line.lcp_total_seats = seats
            line.lcp_total_clcs = total_clcs
            line.lcp_total_clcs_with_vat = total_clcs_with_vat
            line.lcp_total_rate_card = total_rate_card
            line.lcp_total_instructor_cost = total_instructor_cost
            line.lcp_total_instructor_md = total_instructor_md
            line.lcp_total_vendor_instructor = total_vendor_instructor
            line.lcp_total_per_diem = total_per_diem
            line.lcp_total_uber_estimate = total_uber
            line.lcp_ticket_total = ticket_total
            line.lcp_hotel_total = hotel_total
            line.lcp_total_logistics = total_logistics
            line.lcp_partner_share = partner_share
            line.lcp_total_costs = total_costs
            line.lcp_nilme_profit = profit
            line.lcp_profit_margin = (
                profit / revenue
                if revenue
                else 0.0
            )
            line.lcp_unassigned_logistics_count = unassigned_logistics

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
        'lcp_venue_cost',
        'lcp_catering_cost',
    )
    def _check_lcp_per_training_values(self):
        labels = {
            'lcp_vat_rate': 'VAT %',
            'lcp_clcs_per_seat': 'CLCs / Seat or USD / Seat',
            'lcp_rate_card_per_seat': 'Rate Card / Seat',
            'lcp_instructor_md_rate': 'Instructor Rate',
            'lcp_vendor_instructor_day': 'Vendor Instructor / Day',
            'lcp_uber_day_rate': 'Uber / Day',
            'lcp_per_diem_rate': 'Per Diem / Day',
            'lcp_per_diem_days': 'Per Diem Days',
            'lcp_partner_share_pct': 'Partner Share %',
            'lcp_partner_cash_cost': 'Partner Cost',
            'lcp_venue_cost': 'Venue',
            'lcp_catering_cost': 'Catering',
        }

        for line in self:
            for field_name, label in labels.items():
                if (line[field_name] or 0) < 0:
                    raise ValidationError(
                        '%s cannot be negative.' % label
                    )


class TicketTicket(models.Model):
    _inherit = 'ticket.ticket'

    lcp_training_course_id = fields.Many2one(
        'training.course',
        string='Training',
        ondelete='set null',
        index=True,
    )


class HotelHotel(models.Model):
    _inherit = 'hotel.hotel'

    lcp_training_course_id = fields.Many2one(
        'training.course',
        string='Training',
        ondelete='set null',
        index=True,
    )
