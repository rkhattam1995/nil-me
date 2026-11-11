# -*- coding: utf-8 -*-

from html import escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError


VAT_BY_COUNTRY = {'AE': 5.0, 'SA': 15.0, 'BH': 10.0}
PARTNER_NAMES = {
    'EnterOne': ('EnterOne Corporation', 'EnterOne'),
    'Koenig': ('Koenig Solutions Limited', 'Koenig Solutions', 'Koenig'),
}


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    lcp_vat_locked = fields.Boolean(
        string='VAT Auto', compute='_compute_lcp_vat_locked'
    )
    lcp_allowed_instructor_ids = fields.Many2many(
        'hr.employee', string='Allowed LCP Instructors',
        compute='_compute_lcp_allowed_instructor_ids'
    )

    @api.depends('lcp_instructor_source')
    def _compute_lcp_allowed_instructor_ids(self):
        Employee = self.env['hr.employee']
        for line in self:
            domain = [('active', '=', True)]
            if line.lcp_instructor_source == 'nil_me':
                domain += ['|', ('job_id.name', 'ilike', 'Instructor'), ('name', 'ilike', 'Marco')]
            line.lcp_allowed_instructor_ids = Employee.search(domain)

    def _lcp_ordering_country_code(self):
        self.ensure_one()
        partner = self.lead_id.ordering_partner_id
        return partner.commercial_partner_id.country_id.code if partner and partner.commercial_partner_id.country_id else False

    def _lcp_country_vat_rate(self):
        self.ensure_one()
        return VAT_BY_COUNTRY.get(self._lcp_ordering_country_code())

    @api.depends('lead_id.ordering_partner_id.country_id')
    def _compute_lcp_vat_locked(self):
        for line in self:
            line.lcp_vat_locked = line._lcp_country_vat_rate() is not None

    def _lcp_apply_country_vat(self):
        for line in self:
            rate = line._lcp_country_vat_rate()
            if rate is not None:
                line.lcp_vat_rate = rate

    def _lcp_cash_partner_invoice(self):
        self.ensure_one()
        if self.payment_method != 'cash':
            return 0.0
        seats = max(self.no_of_student or 0, 0)
        seat_rate = self.lcp_clcs_per_seat or 0.0
        if self.lcp_cost_learning_partner == 'EnterOne':
            return seat_rate * seats
        if self.lcp_cost_learning_partner == 'Koenig':
            discount = self._koenig_cash_discount_pct()
            discounted = seat_rate * (1.0 - discount / 100.0) * seats
            return discounted * 0.45 if self.lcp_instructor_source == 'nil_me' else discounted
        return 0.0

    def _lcp_cash_all_costs(self):
        self.ensure_one()
        days = self._lcp_line_days()
        online = self.location == 'Online'
        partner = self._lcp_cash_partner_invoice()
        if self.lcp_instructor_source == 'nil_me':
            instructor = (self.lcp_instructor_md_rate or 0.0) * days
            per_diem = 0.0 if online else (self.lcp_per_diem_rate or 0.0) * max(self.lcp_per_diem_days or 0, 0)
        else:
            instructor = (self.lcp_vendor_instructor_day or 0.0) * days
            per_diem = 0.0
        if online:
            tickets = hotels = venue = catering = uber = 0.0
        else:
            tickets = sum(self._lcp_ticket_records().mapped('price'))
            hotels = sum(self._lcp_hotel_records().mapped('price'))
            venue = self.lcp_venue_cost or 0.0
            catering = self.lcp_catering_cost or 0.0
            uber = (self.lcp_uber_day_rate or 0.0) * (days + 2) if days > 0 else 0.0
        return partner + instructor + tickets + hotels + venue + catering + uber + per_diem

    def _lcp_autofill_cash_price_if_blank(self):
        for line in self:
            if line.payment_method != 'cash':
                continue
            line._lcp_apply_country_vat()
            costs = line.lcp_total_costs or 0.0
            value_before_vat = (
                costs * (1.0 + ((line.lcp_markup_pct or 0.0) / 100.0))
                if costs > 0
                else 0.0
            )
            line.price = (
                value_before_vat
                * (1.0 + ((line.lcp_vat_rate or 0.0) / 100.0))
            )

    def _lcp_sync_to_lead_logistics(self):
        for lead in self.mapped('lead_id').filtered(lambda r: r):
            courses = lead.training_course_ids.filtered(
                lambda c: c.location == 'On site'
            )
            lead.with_context(skip_lcp_logistics_sync=True).write({
                'venue': sum(courses.mapped('lcp_venue_cost')),
                'ctrng': sum(courses.mapped('lcp_catering_cost')),
                'uber': sum(courses.mapped('lcp_total_uber_estimate')),
            })

    @api.onchange(
        'payment_method', 'no_of_student', 'training_date_start', 'training_date_end',
        'duration', 'location', 'lcp_clcs_per_seat', 'lcp_instructor_source',
        'lcp_instructor_md_rate', 'lcp_vendor_instructor_day', 'lcp_uber_day_rate',
        'lcp_per_diem_rate', 'lcp_per_diem_days', 'lcp_cost_learning_partner',
        'lcp_venue_cost', 'lcp_catering_cost', 'lcp_vat_rate', 'lcp_markup_pct'
    )
    def _onchange_lcp_commercial_values(self):
        for line in self:
            line._lcp_apply_country_vat()
            line._lcp_autofill_cash_price_if_blank()
            lead = line.lead_id
            if lead:
                courses = lead.training_course_ids.filtered(
                    lambda c: c.location == 'On site'
                )
                lead.venue = sum(courses.mapped('lcp_venue_cost'))
                lead.ctrng = sum(courses.mapped('lcp_catering_cost'))
                lead.uber = sum(courses.mapped('lcp_total_uber_estimate'))

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get('skip_lcp_logistics_sync') and {
            'lcp_venue_cost', 'lcp_catering_cost', 'lcp_uber_day_rate',
            'training_date_start', 'training_date_end', 'duration', 'location'
        }.intersection(vals):
            self._lcp_sync_to_lead_logistics()
        return result

    @api.depends(
        'training_date_start', 'training_date_end', 'duration', 'no_of_student',
        'price', 'payment_method', 'location', 'lcp_vat_rate', 'lcp_clcs_per_seat',
        'lcp_rate_card_per_seat', 'lcp_instructor_source', 'lcp_instructor_md_rate',
        'lcp_vendor_instructor_day', 'lcp_uber_day_rate', 'lcp_per_diem_rate',
        'lcp_per_diem_days', 'lcp_cost_learning_partner', 'lcp_partner_share_pct',
        'lcp_partner_cash_cost', 'lcp_venue_cost', 'lcp_catering_cost',
        'lead_id.training_course_ids', 'lead_id.ticket_ids.price',
        'lead_id.ticket_ids.lcp_training_course_id', 'lead_id.hotel_ids.price',
        'lead_id.hotel_ids.lcp_training_course_id'
    )
    def _compute_lcp_per_training(self):
        super()._compute_lcp_per_training()
        for line in self:
            if line.payment_method != 'cash':
                continue
            operational = (line.lcp_total_costs or 0.0) - (line.lcp_partner_share or 0.0)
            partner_share = line._lcp_cash_partner_invoice()
            revenue = line.price or 0.0
            line.lcp_partner_share = partner_share
            line.lcp_total_costs = operational + partner_share
            line.lcp_nilme_profit = revenue - line.lcp_total_costs
            line.lcp_profit_margin = line.lcp_nilme_profit / revenue if revenue else 0.0


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _lcp_partner_code(self, courses):
        codes = set(courses.mapped('lcp_cost_learning_partner')) - {False}
        if not codes:
            return False
        if len(codes) != 1 or any(not c.lcp_cost_learning_partner for c in courses):
            raise UserError(_('All selected Training LCPs must have the same Learning Partner.'))
        return next(iter(codes))

    def _lcp_partner(self, code):
        if not code:
            return False
        Partner = self.env['res.partner']
        for name in PARTNER_NAMES.get(code, (code,)):
            partner = Partner.search([('name', '=ilike', name), ('active', '=', True)], limit=1)
            if partner:
                return partner.commercial_partner_id
        partner = Partner.search([('name', 'ilike', code), ('active', '=', True)], limit=1)
        if partner:
            return partner.commercial_partner_id
        raise UserError(_('No existing partner was found for Learning Partner "%s".') % code)

    @api.model
    def _lcp_money(self, amount):
        return '$ {:,.2f}'.format(amount or 0.0)

    def _lcp_html_table(self, title, rows):
        body = ''.join(
            '<tr><td style="padding:7px 10px;border:1px solid #cfe5ea;{0}">{1}</td>'
            '<td style="padding:7px 10px;border:1px solid #cfe5ea;text-align:right;white-space:nowrap;{0}">{2}</td></tr>'.format(
                'font-weight:700;background:#eef9fb;' if bold else '', escape(label), value
            ) for label, value, bold in rows
        )
        return (
            '<div style="margin-top:12px;page-break-inside:avoid;">'
            '<div style="font-weight:700;color:#075E68;margin-bottom:6px;">%s</div>'
            '<table style="width:100%%;border-collapse:collapse;font-size:15px;"><tbody>%s</tbody></table></div>'
        ) % (escape(title), body)

    def _lcp_enterone_so_terms(self, courses):
        SaleOrder = self.env['sale.order']
        header = SaleOrder._CLC_TERMS_HEADER if any(c.payment_method == 'clc' for c in courses) else SaleOrder._CASH_TERMS_HEADER
        blocks = [header]
        for course in courses.filtered(lambda c: c.payment_method == 'clc'):
            rate_card = course.lcp_total_rate_card or 0.0
            flight = course.lcp_ticket_total or 0.0
            hotel = course.lcp_hotel_total or 0.0
            instructor = course.lcp_total_instructor_md or 0.0 if course.lcp_instructor_source == 'nil_me' else 0.0
            net = max(rate_card - flight - hotel - instructor, 0.0)
            share_pct = course.lcp_partner_share_pct or 0.0
            nilme_pct = 100.0 - share_pct
            enterone = net * share_pct / 100.0
            nilme = net * nilme_pct / 100.0
            rows = [
                ('Total Rate Card', self._lcp_money(rate_card), True),
                ('Deductible amounts', '', True),
                ('Flight', self._lcp_money(flight), False),
                ('Hotel', self._lcp_money(hotel), False),
            ]
            if instructor:
                rows.append(('NIL ME Instructor', self._lcp_money(instructor), False))
            rows += [
                ('Total', self._lcp_money(net), True),
                (
                    'EnterOne Share %s%%' % ('%g' % share_pct),
                    self._lcp_money(enterone),
                    False,
                ),
                (
                    'NIL ME Share %s%%' % ('%g' % nilme_pct),
                    self._lcp_money(nilme),
                    False,
                ),
                ('NIL ME Invoice', self._lcp_money(nilme + flight + hotel + instructor), True),
            ]
            blocks.append(self._lcp_html_table(course.training_id.display_name or course.name or 'Training', rows))
        return ''.join(blocks)

    def _lcp_koenig_po_terms(self, courses):
        blocks = []
        for course in courses:
            seats = max(course.no_of_student or 0, 0)
            seat_rate = course.lcp_clcs_per_seat or 0.0
            discount = course.lcp_koenig_discount_pct or 0.0
            discounted_seat = course.lcp_koenig_discounted_seat_cost or 0.0
            rows = [
                ('USD / Seat', self._lcp_money(seat_rate), False),
                ('Seats', str(seats), False),
                ('Gross Seat Total', self._lcp_money(seat_rate * seats), False),
                ('Discount', '{:.2f}%'.format(discount), True),
                ('Discounted Seat Cost', self._lcp_money(discounted_seat), False),
                ('Discounted Total', self._lcp_money(discounted_seat * seats), False),
            ]
            if course.lcp_instructor_source == 'nil_me':
                rows.append(('NIL ME Return 55%', self._lcp_money(course.lcp_koenig_nil_return), False))
            rows.append(('Koenig Invoice', self._lcp_money(course.lcp_partner_share), True))
            blocks.append(self._lcp_html_table(course.training_id.display_name or course.name or 'Training', rows))
        return ''.join(blocks)

    def _lcp_sale_company(self, courses):
        self.ensure_one()
        ordering = self.ordering_partner_id.commercial_partner_id
        saudi_cash = bool(ordering and ordering.country_id.code == 'SA' and any(c.payment_method == 'cash' for c in courses))
        if not saudi_cash:
            return self.company_id or self.env.company
        companies = self.env.user.company_ids.filtered(lambda c: c.country_id.code == 'SA')
        if not companies:
            raise UserError(_('Ordering Party is Saudi, but your user has no Saudi company available. No UAE quotation was created.'))
        preferred = companies.filtered(lambda c: 'saudi' in (c.name or '').lower() or 'ksa' in (c.name or '').lower())
        return preferred[:1] or companies[:1]

    def _lcp_sale_tax(self, company, rate):
        if not rate:
            return self.env['account.tax']
        tax = self.env['account.tax'].with_company(company).search([
            ('company_id', '=', company.id), ('type_tax_use', '=', 'sale'),
            ('amount_type', '=', 'percent'), ('amount', '=', rate),
            ('price_include', '=', False), ('active', '=', True),
        ], limit=1)
        if not tax:
            raise UserError(_('No active %s%% Sales VAT tax was found in %s.') % (rate, company.display_name))
        return tax

    def _lcp_sale_lines(self, courses, company):
        lines = []
        for course in courses:
            product = course.training_id
            if not product:
                raise UserError(_('Every Training line must have a Training Name before creating the SO.'))
            price = course.price or 0.0
            vals = {
                'product_id': product.id, 'name': product.display_name or course.name or self.name,
                'product_uom_qty': 1, 'product_uom': product.uom_id.id, 'price_unit': price,
            }
            if course.payment_method == 'cash':
                vat = course.lcp_vat_rate or 0.0
                vals['tax_id'] = [(6, 0, [])]
                if vat:
                    vals['price_unit'] = price / (1.0 + vat / 100.0)
                    vals['tax_id'] = [(6, 0, self._lcp_sale_tax(company, vat).ids)]
            lines.append((0, 0, vals))
        return lines

    def _lcp_instructor_partner(self, instructor):
        partner = getattr(instructor, 'work_contact_id', False) or getattr(instructor, 'address_home_id', False)
        if partner:
            return partner.commercial_partner_id
        partner = self.env['res.partner'].search([('name', '=ilike', instructor.name), ('active', '=', True)], limit=1)
        return partner.commercial_partner_id if partner else self.env['res.partner'].create({
            'name': instructor.name, 'company_type': 'person', 'supplier_rank': 1,
        })

    def _lcp_instructor_course(self):
        courses = self.training_course_ids.filtered('instructor_id')
        if not courses:
            raise UserError(_('Select the Instructor inside the LCP first.'))
        if len(courses) != 1:
            raise UserError(_('Keep one Training Instructor selected at a time before clicking New Instructor PO.'))
        return courses

    @api.model
    def _lcp_is_marco(self, instructor):
        return bool(instructor and 'marco' in (instructor.name or '').lower())

    def _lcp_marco_bill(self, course):
        company = self.company_id or self.env.company
        account = self.env['account.account'].with_company(company).search([
            ('name', 'ilike', 'Incentive'), ('company_ids', 'in', company.id)
        ], limit=1)
        if not account:
            raise UserError(_('No Incentive account was found in %s.') % company.display_name)
        instructor = course.instructor_id
        partner = self._lcp_instructor_partner(instructor)
        rate = course.lcp_instructor_md_rate if course.lcp_instructor_source == 'nil_me' else course.lcp_vendor_instructor_day
        total = course.lcp_total_instructor_md if course.lcp_instructor_source == 'nil_me' else course.lcp_total_vendor_instructor
        if not total:
            raise UserError(_('Marco Instructor Total is zero. Fill the rate first.'))
        customer = self.training_name or self.ordering_partner_id
        training = course.training_id.display_name or course.name or self.name
        description = 'Training: %s | Dates: %s - %s | Customer: %s' % (
            training, course.training_date_start or '', course.training_date_end or '', customer.display_name if customer else ''
        )
        bill = self.env['account.move'].with_company(company).create({
            'move_type': 'in_invoice', 'company_id': company.id, 'partner_id': partner.id,
            'currency_id': (course.lcp_currency_id or self.env.ref('base.USD')).id,
            'invoice_date': fields.Date.context_today(self), 'invoice_origin': self.name,
            'ref': training, 'crm_lead_id': self.id, 'purchase_training_type': 'instructor',
            'instructor_training_course_id': course.id, 'instructor_id': instructor.id,
            'instructor_from': course.training_date_start, 'instructor_to': course.training_date_end,
            'instructor_days': course.lcp_days, 'instructor_daily_rate': rate, 'instructor_total': total,
            'invoice_line_ids': [(0, 0, {'name': description, 'account_id': account.id, 'quantity': 1, 'price_unit': total})],
        })
        return {'type': 'ir.actions.act_window', 'name': _('Marco Incentive Vendor Bill'), 'res_model': 'account.move', 'view_mode': 'form', 'res_id': bill.id, 'target': 'current'}

    @api.onchange('ordering_partner_id')
    def _onchange_lcp_ordering_partner(self):
        for lead in self:
            for course in lead.training_course_ids:
                course._lcp_apply_country_vat()
                course._lcp_autofill_cash_price_if_blank()

    @api.onchange('venue', 'ctrng', 'uber')
    def _onchange_lcp_lead_logistics(self):
        for lead in self:
            onsite = lead.training_course_ids.filtered(lambda c: c.location == 'On site')
            if len(onsite) == 1:
                course = onsite[0]
                course.lcp_venue_cost = lead.venue or 0.0
                course.lcp_catering_cost = lead.ctrng or 0.0
                days = course._lcp_line_days()
                course.lcp_uber_day_rate = (lead.uber or 0.0) / (days + 2) if days > 0 else 0.0

    def write(self, vals):
        result = super().write(vals)
        if 'ordering_partner_id' in vals:
            for lead in self:
                for course in lead.training_course_ids:
                    rate = course._lcp_country_vat_rate()
                    data = {'lcp_vat_rate': rate} if rate is not None else {}
                    if course.payment_method == 'cash' and not course.price:
                        costs = course.lcp_total_costs or 0.0
                        if costs > 0:
                            value_before_vat = (
                                costs
                                * (1.0 + ((course.lcp_markup_pct or 0.0) / 100.0))
                            )
                            data['price'] = (
                                value_before_vat
                                * (1.0 + ((rate if rate is not None else course.lcp_vat_rate) or 0.0) / 100.0)
                            )
                    if data:
                        course.with_context(skip_lcp_logistics_sync=True).write(data)
        if not self.env.context.get('skip_lcp_logistics_sync') and {'venue', 'ctrng', 'uber'}.intersection(vals):
            for lead in self:
                onsite = lead.training_course_ids.filtered(lambda c: c.location == 'On site')
                nonzero = any(vals.get(k) for k in ('venue', 'ctrng', 'uber') if k in vals)
                if len(onsite) > 1:
                    # Form onchanges copy the sums of the onsite LCP lines to
                    # these lead-level summary fields. Saving those sums must
                    # not be mistaken for manually distributing logistics.
                    expected = {
                        'venue': sum(onsite.mapped('lcp_venue_cost')),
                        'ctrng': sum(onsite.mapped('lcp_catering_cost')),
                        'uber': sum(onsite.mapped('lcp_total_uber_estimate')),
                    }
                    is_synced = all(
                        abs((vals[key] or 0.0) - expected[key]) <= 0.01
                        for key in expected if key in vals
                    )
                    if nonzero and not is_synced:
                        raise UserError(_('This Lead has more than one On-site Training. Enter Venue, Catering and Uber in each Training LCP.'))
                    continue
                if len(onsite) == 1:
                    course = onsite[0]
                    data = {}
                    if 'venue' in vals: data['lcp_venue_cost'] = lead.venue or 0.0
                    if 'ctrng' in vals: data['lcp_catering_cost'] = lead.ctrng or 0.0
                    if 'uber' in vals:
                        days = course._lcp_line_days()
                        if lead.uber and days <= 0:
                            raise UserError(_('Set Training dates/duration before entering Uber.'))
                        data['lcp_uber_day_rate'] = (lead.uber or 0.0) / (days + 2) if days > 0 else 0.0
                    if data:
                        course.with_context(skip_lcp_logistics_sync=True).write(data)
        return result

    def action_new_purchase_order(self):
        self.ensure_one()
        for course in self.training_course_ids:
            course._lcp_apply_country_vat(); course._lcp_autofill_cash_price_if_blank()
        courses = self.training_course_ids.filtered(lambda c: c.payment_method == 'cash')
        if not courses:
            return super().action_new_purchase_order()
        code = self._lcp_partner_code(courses)
        if not code:
            return super().action_new_purchase_order()
        partner = self._lcp_partner(code)
        lines = []
        for course in courses:
            product = course.training_id
            if not product:
                raise UserError(_('Every Cash Training must have a Training Name.'))
            lines.append((0, 0, {
                'product_id': product.id, 'name': product.display_name or course.name or self.name,
                'product_qty': 1, 'product_uom': product.uom_po_id.id or product.uom_id.id,
                'price_unit': course.lcp_partner_share or 0.0, 'date_planned': fields.Datetime.now(),
            }))
        return {
            'type': 'ir.actions.act_window', 'name': _('New PO'), 'res_model': 'purchase.order',
            'view_mode': 'form', 'target': 'current', 'context': {
                'default_crm_lead_id': self.id, 'default_origin': self.name,
                'default_partner_id': partner.id, 'default_currency_id': self.env.ref('base.USD').id,
                'default_is_training_order': True, 'default_po_training_type': 'training_vendor',
                'default_payment_method': 'cash', 'default_training_course_ids': [(6, 0, courses.ids)],
                'default_order_line': lines, 'default_term_and_cond': self._lcp_koenig_po_terms(courses) if code == 'Koenig' else '',
                'default_display_training_table': True, 'default_display_total': True,
            }
        }

    def action_new_training_so(self):
        self.ensure_one()
        for course in self.training_course_ids:
            course._lcp_apply_country_vat(); course._lcp_autofill_cash_price_if_blank()
        courses = self.training_course_ids
        code = self._lcp_partner_code(courses) if courses else False
        if not code:
            return super().action_new_training_so()
        partner = self._lcp_partner(code)
        company = self._lcp_sale_company(courses)
        action = super().action_new_training_so()
        context = dict(action.get('context') or {})
        context.update({
            'allowed_company_ids': list(set(self.env.companies.ids + [company.id])),
            'default_company_id': company.id, 'default_partner_id': partner.id,
            'default_order_line': self._lcp_sale_lines(courses, company),
            'default_display_training_table': True, 'default_display_total': True,
        })
        if code == 'EnterOne':
            context['default_term_and_cond'] = self._lcp_enterone_so_terms(courses)
        action['context'] = context
        return action

    def action_new_instructor_purchase_order(self):
        self.ensure_one()
        course = self._lcp_instructor_course()
        instructor = course.instructor_id
        if course.lcp_instructor_source == 'nil_me' and not self._lcp_is_marco(instructor) and 'instructor' not in (instructor.job_id.name or '').lower():
            raise UserError(_('%s is not assigned to an Instructor Job Position.') % instructor.display_name)
        if self._lcp_is_marco(instructor):
            return self._lcp_marco_bill(course)
        if not course.training_date_start or not course.training_date_end:
            raise UserError(_('Set Training Start and Delivery dates first.'))
        rate = course.lcp_instructor_md_rate if course.lcp_instructor_source == 'nil_me' else course.lcp_vendor_instructor_day
        total = course.lcp_total_instructor_md if course.lcp_instructor_source == 'nil_me' else course.lcp_total_vendor_instructor
        if not rate or not total or abs(course._lcp_line_days() * rate - total) > 0.01:
            raise UserError(_('Instructor daily rate/total does not match the LCP Instructor Total.'))
        vendor = self._lcp_instructor_partner(instructor)
        return {
            'type': 'ir.actions.act_window', 'name': _('New Instructor PO'), 'res_model': 'purchase.order',
            'view_mode': 'form', 'target': 'current', 'context': {
                'default_crm_lead_id': self.id, 'default_origin': self.name,
                'default_partner_id': vendor.id, 'default_currency_id': (course.lcp_currency_id or self.env.ref('base.USD')).id,
                'default_is_training_order': True, 'default_po_training_type': 'instructor',
                'default_instructor_training_course_id': course.id, 'default_instructor_id': instructor.id,
                'default_instructor_from': course.training_date_start, 'default_instructor_to': course.training_date_end,
                'default_instructor_daily_rate': rate, 'default_display_total': True,
            }
        }
