# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    # Cash + EnterOne: this is the partner's cost per seat.
    lcp_partner_cash_cost = fields.Monetary(
        string='Cost / Seat',
        currency_field='lcp_currency_id',
        default=0.0,
    )

    lcp_koenig_discount_pct = fields.Float(
        string='Koenig Discount %',
        compute='_compute_lcp_partner_breakdown',
    )
    lcp_koenig_discounted_seat_cost = fields.Monetary(
        string='Koenig Discounted Seat Cost',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_partner_breakdown',
    )
    lcp_koenig_nil_return = fields.Monetary(
        string='NIL ME Return from Koenig Seats',
        currency_field='lcp_currency_id',
        compute='_compute_lcp_partner_breakdown',
    )

    def _koenig_cash_discount_pct(self):
        """
        Koenig Cash slab discount, expressed as one effective percentage
        so the existing downstream calculations remain unchanged:

        - First 2 seats: 25% discount
        - Seats 3 to 5: 30% discount
        - Seat 6 onward: 45% discount
        """
        self.ensure_one()

        seats = max(self.no_of_student or 0, 0)
        if not seats:
            return 0.0

        first_two = min(seats, 2)
        three_to_five = min(max(seats - 2, 0), 3)
        six_onward = max(seats - 5, 0)

        total_discount_units = (
            (first_two * 25.0)
            + (three_to_five * 30.0)
            + (six_onward * 45.0)
        )

        return total_discount_units / seats

    @api.depends(
        'payment_method',
        'lcp_cost_learning_partner',
        'lcp_clcs_per_seat',
        'no_of_student',
        'lcp_instructor_source',
    )
    def _compute_lcp_partner_breakdown(self):
        for line in self:
            line.lcp_koenig_discount_pct = 0.0
            line.lcp_koenig_discounted_seat_cost = 0.0
            line.lcp_koenig_nil_return = 0.0

            if (
                line.payment_method != 'cash'
                or line.lcp_cost_learning_partner != 'Koenig'
            ):
                continue

            discount_pct = line._koenig_cash_discount_pct()
            discounted_seat_cost = (
                (line.lcp_clcs_per_seat or 0.0)
                * (1.0 - (discount_pct / 100.0))
            )
            total_discounted_seats = (
                discounted_seat_cost
                * max(line.no_of_student or 0, 0)
            )

            nil_return = 0.0
            if line.lcp_instructor_source == 'nil_me':
                nil_return = total_discounted_seats * 0.55

            line.lcp_koenig_discount_pct = discount_pct
            line.lcp_koenig_discounted_seat_cost = discounted_seat_cost
            line.lcp_koenig_nil_return = nil_return

    @api.depends(
        'training_date_start',
        'training_date_end',
        'duration',
        'no_of_student',
        'price',
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
        # Keep all existing instructor/logistics/CLC calculations, then
        # replace only the Cash partner invoice calculation.
        super()._compute_lcp_per_training()

        for line in self:
            if line.payment_method != 'cash':
                continue

            seats = max(line.no_of_student or 0, 0)
            revenue = line.price or 0.0

            # Parent total = operational costs + old partner share.
            # Remove only the old partner-share amount, preserving every
            # instructor/logistics/venue/catering calculation exactly.
            operational_costs = (
                (line.lcp_total_costs or 0.0)
                - (line.lcp_partner_share or 0.0)
            )

            partner_share = line.lcp_partner_share or 0.0

            if line.lcp_cost_learning_partner == 'EnterOne':
                # EnterOne Cash invoice = Cost / Seat x number of seats.
                partner_share = (
                    (line.lcp_partner_cash_cost or 0.0)
                    * seats
                )

            elif line.lcp_cost_learning_partner == 'Koenig':
                # Koenig Cash:
                # - exactly 2 seats: 25% discount on each seat
                # - all other seat counts: no automatic discount
                discount_pct = line._koenig_cash_discount_pct()
                discounted_seat_cost = (
                    (line.lcp_clcs_per_seat or 0.0)
                    * (1.0 - (discount_pct / 100.0))
                )
                discounted_total = discounted_seat_cost * seats

                if line.lcp_instructor_source == 'nil_me':
                    # 55% returns to NIL ME, therefore Koenig's payable
                    # partner invoice/share is the remaining 45%.
                    partner_share = discounted_total * 0.45
                else:
                    partner_share = discounted_total

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


class TicketTicket(models.Model):
    _inherit = 'ticket.ticket'

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        readonly=True,
        default=lambda self: self.env.ref('base.USD'),
    )

    def _single_onsite_training(self, lead):
        onsite = lead.training_course_ids.filtered(
            lambda course: course.location == 'On site'
        )
        return onsite if len(onsite) == 1 else self.env['training.course']

    def _apply_training_defaults(self, vals):
        vals = dict(vals)
        vals['currency_id'] = self.env.ref('base.USD').id

        training_id = vals.get('lcp_training_course_id')
        lead_id = vals.get('ticket_lead_id')

        if not training_id and lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
            single = self._single_onsite_training(lead)
            if single:
                training_id = single.id
                vals['lcp_training_course_id'] = training_id

        if training_id:
            training = self.env['training.course'].browse(training_id)
            if training.location != 'On site':
                raise UserError(_('Flight expenses must belong to an On-site Training.'))
            if vals.get('ticket_lead_id') and vals['ticket_lead_id'] != training.lead_id.id:
                raise UserError(_('The Flight and Training must belong to the same Lead.'))
            if training.lead_id:
                vals['ticket_lead_id'] = training.lead_id.id
            if training.training_date_start:
                vals['date'] = (
                    training.training_date_start - timedelta(days=1)
                )

        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([
            self._apply_training_defaults(vals)
            for vals in vals_list
        ])

    def write(self, vals):
        vals = dict(vals)
        vals['currency_id'] = self.env.ref('base.USD').id
        if 'lcp_training_course_id' in vals and vals['lcp_training_course_id']:
            training = self.env['training.course'].browse(
                vals['lcp_training_course_id']
            )
            if training.location != 'On site':
                raise UserError(_('Flight expenses must belong to an On-site Training.'))
            if any(row.ticket_lead_id and row.ticket_lead_id != training.lead_id for row in self):
                raise UserError(_('The Flight and Training must belong to the same Lead.'))
            vals['ticket_lead_id'] = training.lead_id.id
            if training.training_date_start:
                vals['date'] = (
                    training.training_date_start - timedelta(days=1)
                )
        return super().write(vals)

    @api.onchange('ticket_lead_id')
    def _onchange_ticket_lead_training(self):
        for ticket in self:
            ticket.currency_id = self.env.ref('base.USD')
            if not ticket.ticket_lead_id:
                continue
            single = ticket._single_onsite_training(ticket.ticket_lead_id)
            if single:
                ticket.lcp_training_course_id = single
                if single.training_date_start:
                    ticket.date = (
                        single.training_date_start - timedelta(days=1)
                    )

    @api.onchange('lcp_training_course_id')
    def _onchange_lcp_training_course_id_dates(self):
        for ticket in self:
            ticket.currency_id = self.env.ref('base.USD')
            training = ticket.lcp_training_course_id
            if training and training.training_date_start:
                ticket.date = (
                    training.training_date_start - timedelta(days=1)
                )


class HotelHotel(models.Model):
    _inherit = 'hotel.hotel'

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        readonly=True,
        default=lambda self: self.env.ref('base.USD'),
    )

    def _single_onsite_training(self, lead):
        onsite = lead.training_course_ids.filtered(
            lambda course: course.location == 'On site'
        )
        return onsite if len(onsite) == 1 else self.env['training.course']

    def _apply_training_defaults(self, vals):
        vals = dict(vals)
        vals['currency_id'] = self.env.ref('base.USD').id

        training_id = vals.get('lcp_training_course_id')
        lead_id = vals.get('hotel_lead_id')

        if not training_id and lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
            single = self._single_onsite_training(lead)
            if single:
                training_id = single.id
                vals['lcp_training_course_id'] = training_id

        if training_id:
            training = self.env['training.course'].browse(training_id)
            if training.location != 'On site':
                raise UserError(_('Hotel expenses must belong to an On-site Training.'))
            if vals.get('hotel_lead_id') and vals['hotel_lead_id'] != training.lead_id.id:
                raise UserError(_('The Hotel and Training must belong to the same Lead.'))
            if training.lead_id:
                vals['hotel_lead_id'] = training.lead_id.id
            if training.training_date_start:
                vals['date_from'] = (
                    training.training_date_start - timedelta(days=1)
                )
            if training.training_date_end and 'date_to' not in vals:
                vals['date_to'] = training.training_date_end

        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([
            self._apply_training_defaults(vals)
            for vals in vals_list
        ])

    def write(self, vals):
        vals = dict(vals)
        vals['currency_id'] = self.env.ref('base.USD').id
        if 'lcp_training_course_id' in vals and vals['lcp_training_course_id']:
            training = self.env['training.course'].browse(
                vals['lcp_training_course_id']
            )
            if training.location != 'On site':
                raise UserError(_('Hotel expenses must belong to an On-site Training.'))
            if any(row.hotel_lead_id and row.hotel_lead_id != training.lead_id for row in self):
                raise UserError(_('The Hotel and Training must belong to the same Lead.'))
            vals['hotel_lead_id'] = training.lead_id.id
            if training.training_date_start:
                vals['date_from'] = (
                    training.training_date_start - timedelta(days=1)
                )
            if training.training_date_end:
                vals['date_to'] = training.training_date_end
        return super().write(vals)

    @api.onchange('hotel_lead_id')
    def _onchange_hotel_lead_training(self):
        for hotel in self:
            hotel.currency_id = self.env.ref('base.USD')
            if not hotel.hotel_lead_id:
                continue
            single = hotel._single_onsite_training(hotel.hotel_lead_id)
            if single:
                hotel.lcp_training_course_id = single
                if single.training_date_start:
                    hotel.date_from = (
                        single.training_date_start - timedelta(days=1)
                    )
                if single.training_date_end:
                    hotel.date_to = single.training_date_end

    @api.onchange('lcp_training_course_id')
    def _onchange_lcp_training_course_id_dates(self):
        for hotel in self:
            hotel.currency_id = self.env.ref('base.USD')
            training = hotel.lcp_training_course_id
            if not training:
                continue
            if training.training_date_start:
                hotel.date_from = (
                    training.training_date_start - timedelta(days=1)
                )
            if training.training_date_end:
                hotel.date_to = training.training_date_end
