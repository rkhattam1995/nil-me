# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    lcp_auto_price_generated = fields.Boolean(
        string='Auto Training Price', default=False, copy=False
    )

    lcp_markup_pct = fields.Float(
        string='Markup %',
        digits=(16, 2),
        default=0.0,
    )

    @api.constrains('lcp_markup_pct')
    def _check_lcp_markup_pct(self):
        for line in self:
            if (line.lcp_markup_pct or 0.0) < 0:
                raise ValidationError(_('Markup % cannot be negative.'))

    def _lcp_expected_cash_price(self):
        self.ensure_one()
        if self.payment_method != 'cash':
            return 0.0
        costs = self.lcp_total_costs or 0.0
        if costs <= 0:
            return 0.0
        value_before_vat = (
            costs * (1.0 + ((self.lcp_markup_pct or 0.0) / 100.0))
        )
        return (
            value_before_vat
            * (1.0 + ((self.lcp_vat_rate or 0.0) / 100.0))
        )

    def _lcp_autofill_cash_price_if_blank(self):
        for line in self:
            if line.payment_method != 'cash':
                continue
            line._lcp_apply_country_vat()
            expected = line._lcp_expected_cash_price()
            line.price = expected
            line.lcp_auto_price_generated = True

    def write(self, vals):
        should_reprice = bool({
            'payment_method', 'no_of_student', 'training_date_start',
            'training_date_end', 'duration', 'location', 'lcp_clcs_per_seat',
            'lcp_instructor_source', 'lcp_instructor_md_rate',
            'lcp_vendor_instructor_day', 'lcp_uber_day_rate',
            'lcp_per_diem_rate', 'lcp_per_diem_days',
            'lcp_cost_learning_partner', 'lcp_venue_cost',
            'lcp_catering_cost', 'lcp_vat_rate', 'lcp_markup_pct',
        }.intersection(vals)) and 'price' not in vals
        auto_before = {
            line.id: (
                line.lcp_auto_price_generated
                or not line.price
                or 'lcp_markup_pct' in vals
            )
            for line in self
        } if should_reprice else {}
        price_touched = (
            'price' in vals
            and 'lcp_auto_price_generated' not in vals
            and not self.env.context.get('skip_lcp_price_flag')
        )

        result = super().write(vals)

        if price_touched:
            for line in self:
                expected = line._lcp_expected_cash_price()
                is_auto = bool(
                    expected > 0
                    and abs((line.price or 0.0) - expected) <= 0.01
                )
                line.with_context(skip_lcp_price_flag=True).write({
                    'lcp_auto_price_generated': is_auto,
                })

        if should_reprice and not self.env.context.get('skip_lcp_reprice'):
            for line in self:
                if auto_before.get(line.id):
                    line.with_context(skip_lcp_reprice=True)._lcp_autofill_cash_price_if_blank()

        return result


class TicketTicket(models.Model):
    _inherit = 'ticket.ticket'

    def _lcp_refresh_training_prices(self):
        for lead in self.mapped('ticket_lead_id').filtered(lambda r: r):
            for course in lead.training_course_ids.filtered(lambda c: c.payment_method == 'cash'):
                course._lcp_autofill_cash_price_if_blank()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._lcp_refresh_training_prices()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'price', 'lcp_training_course_id', 'ticket_lead_id'}.intersection(vals):
            self._lcp_refresh_training_prices()
        return result


class HotelHotel(models.Model):
    _inherit = 'hotel.hotel'

    def _lcp_refresh_training_prices(self):
        for lead in self.mapped('hotel_lead_id').filtered(lambda r: r):
            for course in lead.training_course_ids.filtered(lambda c: c.payment_method == 'cash'):
                course._lcp_autofill_cash_price_if_blank()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._lcp_refresh_training_prices()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'price_without_tax', 'tax', 'lcp_training_course_id', 'hotel_lead_id'}.intersection(vals):
            self._lcp_refresh_training_prices()
        return result


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _lcp_sale_company(self, courses):
        self.ensure_one()
        ordering = self.ordering_partner_id.commercial_partner_id
        saudi_cash = bool(
            ordering
            and ordering.country_id.code == 'SA'
            and any(course.payment_method == 'cash' for course in courses)
        )
        if not saudi_cash:
            return self.company_id or self.env.company

        companies = self.env.user.company_ids.filtered(
            lambda company: (
                company.country_id.code == 'SA'
                or 'saudi' in (company.name or '').lower()
                or 'ksa' in (company.name or '').lower()
            )
        )
        if not companies:
            raise UserError(_(
                'Ordering Party is Saudi, but your user has no Saudi company/branch available. '
                'No UAE quotation was created.'
            ))
        preferred = companies.filtered(
            lambda company: company.country_id.code == 'SA'
        )
        return preferred[:1] or companies[:1]

    def _lcp_instructor_partner(self, instructor):
        employee = instructor.sudo()
        partner = employee.work_contact_id or employee.address_home_id
        if partner:
            return partner.commercial_partner_id
        partner = self.env['res.partner'].search([
            ('name', '=ilike', instructor.name),
            ('active', '=', True),
        ], limit=1)
        if partner:
            return partner.commercial_partner_id
        return self.env['res.partner'].create({
            'name': instructor.name,
            'company_type': 'person',
            'supplier_rank': 1,
        })

    def _lcp_marco_bill(self, course):
        self.ensure_one()
        company = self.company_id or self.env.company
        account = self.env['account.account'].with_company(company).search([
            ('name', 'ilike', 'Incentive'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not account:
            raise UserError(_(
                'No Incentive account was found in %s.'
            ) % company.display_name)

        instructor = course.instructor_id
        partner = self._lcp_instructor_partner(instructor)
        rate = (
            course.lcp_instructor_md_rate
            if course.lcp_instructor_source == 'nil_me'
            else course.lcp_vendor_instructor_day
        ) or 0.0
        total = (
            course.lcp_total_instructor_md
            if course.lcp_instructor_source == 'nil_me'
            else course.lcp_total_vendor_instructor
        ) or 0.0
        if total <= 0:
            raise UserError(_('Marco Instructor Total is zero. Fill the rate first.'))

        training_month_date = course.training_date_end or course.training_date_start
        if not training_month_date:
            raise UserError(_('Set the Training date before creating Marco Incentive Vendor Bill.'))
        due_date = fields.Date.end_of(training_month_date, 'month')

        customer = self.training_name or self.ordering_partner_id
        training = course.training_id.display_name or course.name or self.name
        description = 'Training: %s | Dates: %s - %s | Customer: %s' % (
            training,
            course.training_date_start or '',
            course.training_date_end or '',
            customer.display_name if customer else '',
        )
        bill = self.env['account.move'].with_company(company).create({
            'move_type': 'in_invoice',
            'company_id': company.id,
            'partner_id': partner.id,
            'currency_id': (course.lcp_currency_id or self.env.ref('base.USD')).id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': due_date,
            'invoice_origin': self.name,
            'ref': training,
            'crm_lead_id': self.id,
            'purchase_training_type': 'instructor',
            'instructor_training_course_id': course.id,
            'instructor_id': instructor.id,
            'instructor_from': course.training_date_start,
            'instructor_to': course.training_date_end,
            'instructor_days': course.lcp_days,
            'instructor_daily_rate': rate,
            'instructor_total': total,
            'invoice_line_ids': [(0, 0, {
                'name': description,
                'account_id': account.id,
                'quantity': 1.0,
                'price_unit': total,
            })],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Marco Incentive Vendor Bill'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
            'target': 'current',
        }
