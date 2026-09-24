# -*- coding: utf-8 -*-

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang


class AmPricing(models.Model):
    _name = 'am.pricing'
    _description = 'Account Manager Pricing'
    _order = 'sent_at desc, id desc'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Opportunity',
        required=True,
        ondelete='cascade',
        index=True,
    )
    account_manager_id = fields.Many2one(
        'res.users',
        string='Account Manager',
        required=True,
        index=True,
    )
    sent_by_id = fields.Many2one(
        'res.users',
        string='Sent By',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
    )
    sent_at = fields.Datetime(
        string='Sent At',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )

    # Legacy field kept for compatibility with earlier AM Pricing snapshots.
    # New pricing uses markup_pct on each am.pricing.line instead.
    markup_pct = fields.Float(
        string='Markup %',
        digits=(16, 2),
        readonly=True,
        groups='base.group_system',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        'am.pricing.line',
        'pricing_id',
        string='Trainings',
        readonly=True,
    )
    subtotal = fields.Monetary(
        string='Subtotal Before VAT',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    vat_amount = fields.Monetary(
        string='VAT Amount',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    total = fields.Monetary(
        string='Total Including VAT',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    cash_total = fields.Monetary(
        string='Cash Total',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    clc_total = fields.Integer(
        string='CLC Total',
        compute='_compute_totals',
        store=True,
    )
    has_cash_pricing = fields.Boolean(
        compute='_compute_totals',
        store=True,
    )
    has_clc_pricing = fields.Boolean(
        compute='_compute_totals',
        store=True,
    )

    @api.depends(
        'line_ids.payment_method',
        'line_ids.price_before_vat',
        'line_ids.vat_amount',
        'line_ids.total',
        'line_ids.total_clcs_with_vat',
    )
    def _compute_totals(self):
        for rec in self:
            cash_lines = rec.line_ids.filtered(
                lambda line: line.payment_method == 'cash'
            )
            clc_lines = rec.line_ids.filtered(
                lambda line: line.payment_method == 'clc'
            )
            rec.subtotal = sum(cash_lines.mapped('price_before_vat'))
            rec.vat_amount = sum(cash_lines.mapped('vat_amount'))
            rec.total = sum(cash_lines.mapped('total'))
            rec.cash_total = rec.total
            rec.clc_total = sum(clc_lines.mapped('total_clcs_with_vat'))
            rec.has_cash_pricing = bool(cash_lines)
            rec.has_clc_pricing = bool(clc_lines)

    def _compute_display_name(self):
        for rec in self:
            stamp = fields.Datetime.to_string(rec.sent_at) if rec.sent_at else ''
            rec.display_name = 'AM Pricing - %s' % stamp if stamp else 'AM Pricing'


class AmPricingLine(models.Model):
    _name = 'am.pricing.line'
    _description = 'Account Manager Pricing Line'
    _order = 'id'

    pricing_id = fields.Many2one(
        'am.pricing',
        required=True,
        ondelete='cascade',
        index=True,
    )
    course_id = fields.Many2one(
        'training.course',
        string='Training Source',
        readonly=True,
        ondelete='set null',
        groups='base.group_system',
    )
    training_name = fields.Char(
        string='Training',
        required=True,
        readonly=True,
    )
    delivery_type = fields.Selection(
        [('Online', 'Online'), ('On site', 'On site')],
        string='Delivery Type',
        readonly=True,
    )
    students = fields.Integer(
        string='Students',
        readonly=True,
    )
    payment_method = fields.Selection(
        [('cash', 'Cash'), ('clc', 'CLC')],
        string='Payment Method',
        readonly=True,
    )
    rate_card_per_seat = fields.Monetary(
        string='Rate Card / Seat',
        currency_field='currency_id',
        readonly=True,
    )
    clcs_per_seat = fields.Float(
        string='CLCs / Seat',
        readonly=True,
    )
    total_clcs_with_vat = fields.Integer(
        string='Total CLCs + VAT',
        readonly=True,
    )
    training_value = fields.Monetary(
        string='Training Value',
        currency_field='currency_id',
        readonly=True,
    )
    markup_pct = fields.Float(
        string='Markup %',
        digits=(16, 2),
        readonly=True,
        groups='base.group_system',
    )
    currency_id = fields.Many2one(
        related='pricing_id.currency_id',
        store=True,
        readonly=True,
    )
    price_before_vat = fields.Monetary(
        string='Price Before VAT',
        currency_field='currency_id',
        readonly=True,
    )
    vat_rate = fields.Float(
        string='VAT %',
        digits=(16, 2),
        readonly=True,
    )
    vat_amount = fields.Monetary(
        string='VAT Amount',
        currency_field='currency_id',
        readonly=True,
    )
    total = fields.Monetary(
        string='Total',
        currency_field='currency_id',
        readonly=True,
    )


class AmPricingWizard(models.TransientModel):
    _name = 'am.pricing.wizard'
    _description = 'Send Pricing to Account Manager'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Opportunity',
        required=True,
        readonly=True,
    )
    account_manager_id = fields.Many2one(
        'res.users',
        string='Account Manager',
        required=True,
        domain=[('share', '=', False)],
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        readonly=True,
    )
    line_ids = fields.One2many(
        'am.pricing.wizard.line',
        'wizard_id',
        string='Trainings',
    )
    currency_mismatch = fields.Boolean(
        string='Currency Mismatch',
        compute='_compute_currency_id',
    )
    subtotal = fields.Monetary(
        string='Subtotal Before VAT',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    vat_amount = fields.Monetary(
        string='VAT Amount',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    total = fields.Monetary(
        string='Total Including VAT',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    cash_total = fields.Monetary(
        string='Cash Total',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    clc_total = fields.Integer(
        string='CLC Total',
        compute='_compute_totals',
    )
    has_cash_pricing = fields.Boolean(
        compute='_compute_totals',
    )
    has_clc_pricing = fields.Boolean(
        compute='_compute_totals',
    )

    @api.depends('line_ids.selected', 'line_ids.currency_id', 'line_ids.payment_method')
    def _compute_currency_id(self):
        usd = self.env.ref('base.USD')
        for rec in self:
            selected = rec.line_ids.filtered('selected')
            cash_selected = selected.filtered(
                lambda line: line.payment_method == 'cash'
            )
            currencies = cash_selected.mapped('currency_id').filtered(lambda c: c)
            if not currencies:
                cash_lines = rec.line_ids.filtered(
                    lambda line: line.payment_method == 'cash'
                )
                currencies = cash_lines.mapped('currency_id').filtered(lambda c: c)
            rec.currency_mismatch = len(currencies) > 1
            rec.currency_id = currencies[:1] or usd

    @api.depends(
        'line_ids.selected',
        'line_ids.payment_method',
        'line_ids.price_before_vat',
        'line_ids.vat_amount',
        'line_ids.total',
        'line_ids.total_clcs_with_vat',
        'line_ids.currency_id',
    )
    def _compute_totals(self):
        for rec in self:
            selected = rec.line_ids.filtered('selected')
            cash_lines = selected.filtered(
                lambda line: line.payment_method == 'cash'
            )
            clc_lines = selected.filtered(
                lambda line: line.payment_method == 'clc'
            )
            currencies = cash_lines.mapped('currency_id').filtered(lambda c: c)
            if len(currencies) > 1:
                rec.subtotal = 0.0
                rec.vat_amount = 0.0
                rec.total = 0.0
                rec.cash_total = 0.0
            else:
                rec.subtotal = sum(cash_lines.mapped('price_before_vat'))
                rec.vat_amount = sum(cash_lines.mapped('vat_amount'))
                rec.total = sum(cash_lines.mapped('total'))
                rec.cash_total = rec.total

            rec.clc_total = sum(clc_lines.mapped('total_clcs_with_vat'))
            rec.has_cash_pricing = bool(cash_lines)
            rec.has_clc_pricing = bool(clc_lines)

    def action_send(self):
        self.ensure_one()

        selected = self.line_ids.filtered('selected')
        if not selected:
            raise UserError(_('Select at least one training.'))

        if selected.filtered(lambda line: line.markup_pct < 0):
            raise UserError(_('Markup % cannot be negative.'))

        cash_selected = selected.filtered(
            lambda line: line.payment_method == 'cash'
        )
        currencies = cash_selected.mapped('currency_id').filtered(lambda c: c)
        if len(currencies) > 1:
            raise UserError(_('Selected Cash trainings must use the same currency.'))

        if not self.account_manager_id:
            raise UserError(_('Select an Account Manager.'))

        currency = currencies[:1] or self.env.ref('base.USD')

        line_commands = []
        for line in selected:
            line_commands.append((0, 0, {
                'course_id': line.course_id.id,
                'training_name': line.training_name,
                'delivery_type': line.delivery_type,
                'students': line.students,
                'payment_method': line.payment_method,
                'rate_card_per_seat': line.rate_card_per_seat,
                'clcs_per_seat': line.clcs_per_seat,
                'total_clcs_with_vat': line.total_clcs_with_vat,
                'training_value': line.training_value,
                'markup_pct': line.markup_pct,
                'price_before_vat': line.price_before_vat,
                'vat_rate': line.vat_rate,
                'vat_amount': line.vat_amount,
                'total': line.total,
            }))

        pricing = self.env['am.pricing'].create({
            'lead_id': self.lead_id.id,
            'account_manager_id': self.account_manager_id.id,
            'sent_by_id': self.env.user.id,
            'sent_at': fields.Datetime.now(),
            'currency_id': currency.id,
            'line_ids': line_commands,
        })

        cash_rows = []
        clc_rows = []
        for line in pricing.line_ids:
            delivery = dict(
                line._fields['delivery_type'].selection
            ).get(line.delivery_type, line.delivery_type or '')

            if line.payment_method == 'clc':
                clc_rows.append(
                    '<tr>'
                    '<td style="padding:6px;border:1px solid #ddd;">%s</td>'
                    '<td style="padding:6px;border:1px solid #ddd;">%s</td>'
                    '<td style="padding:6px;border:1px solid #ddd;text-align:center;">%s</td>'
                    '<td style="padding:6px;border:1px solid #ddd;text-align:right;">%g</td>'
                    '<td style="padding:6px;border:1px solid #ddd;text-align:right;"><strong>%s</strong></td>'
                    '</tr>'
                    % (
                        escape(line.training_name or ''),
                        escape(delivery),
                        line.students,
                        line.clcs_per_seat or 0.0,
                        line.total_clcs_with_vat or 0,
                    )
                )
                continue

            cash_rows.append(
                '<tr>'
                '<td style="padding:6px;border:1px solid #ddd;">%s</td>'
                '<td style="padding:6px;border:1px solid #ddd;">%s</td>'
                '<td style="padding:6px;border:1px solid #ddd;text-align:center;">%s</td>'
                '<td style="padding:6px;border:1px solid #ddd;text-align:right;">%s</td>'
                '<td style="padding:6px;border:1px solid #ddd;text-align:right;">%s%%</td>'
                '<td style="padding:6px;border:1px solid #ddd;text-align:right;">%s</td>'
                '<td style="padding:6px;border:1px solid #ddd;text-align:right;"><strong>%s</strong></td>'
                '</tr>'
                % (
                    escape(line.training_name or ''),
                    escape(delivery),
                    line.students,
                    escape(formatLang(
                        self.env,
                        line.price_before_vat,
                        currency_obj=currency,
                    )),
                    ('%g' % (line.vat_rate or 0.0)),
                    escape(formatLang(
                        self.env,
                        line.vat_amount,
                        currency_obj=currency,
                    )),
                    escape(formatLang(
                        self.env,
                        line.total,
                        currency_obj=currency,
                    )),
                )
            )

        pricing_tables = []
        if cash_rows:
            pricing_tables.append(
                '<p><strong>Cash Pricing</strong></p>'
                '<table style="border-collapse:collapse;width:100%%;">'
                '<thead><tr>'
                '<th style="padding:6px;border:1px solid #ddd;text-align:left;">Training</th>'
                '<th style="padding:6px;border:1px solid #ddd;text-align:left;">Delivery Type</th>'
                '<th style="padding:6px;border:1px solid #ddd;">Students</th>'
                '<th style="padding:6px;border:1px solid #ddd;">Price Before VAT</th>'
                '<th style="padding:6px;border:1px solid #ddd;">VAT</th>'
                '<th style="padding:6px;border:1px solid #ddd;">VAT Amount</th>'
                '<th style="padding:6px;border:1px solid #ddd;">Total</th>'
                '</tr></thead><tbody>%s</tbody></table>'
                % ''.join(cash_rows)
            )

        if clc_rows:
            pricing_tables.append(
                '<p><strong>CLC Pricing</strong></p>'
                '<table style="border-collapse:collapse;width:100%%;">'
                '<thead><tr>'
                '<th style="padding:6px;border:1px solid #ddd;text-align:left;">Training</th>'
                '<th style="padding:6px;border:1px solid #ddd;text-align:left;">Delivery Type</th>'
                '<th style="padding:6px;border:1px solid #ddd;">Students</th>'
                '<th style="padding:6px;border:1px solid #ddd;">CLCs / Seat</th>'
                '<th style="padding:6px;border:1px solid #ddd;">Total CLCs + VAT</th>'
                '</tr></thead><tbody>%s</tbody></table>'
                % ''.join(clc_rows)
            )

        notify_users = self.account_manager_id
        if self.lead_id.user_id:
            notify_users |= self.lead_id.user_id

        notify_partners = notify_users.mapped('partner_id').filtered(lambda p: p)
        mention_links = [
            Markup(
                '<a href="#" data-oe-model="res.partner" data-oe-id="%s">@%s</a>'
            ) % (
                partner.id,
                escape(partner.name or ''),
            )
            for partner in notify_partners
        ]
        mentions_html = Markup(', ').join(mention_links)

        totals_html = []
        if pricing.has_cash_pricing:
            totals_html.append(
                '<strong>Cash Total:</strong> %s'
                % escape(formatLang(
                    self.env,
                    pricing.cash_total,
                    currency_obj=currency,
                ))
            )
        if pricing.has_clc_pricing:
            totals_html.append(
                '<strong>CLC Total:</strong> %s CLCs'
                % (pricing.clc_total or 0)
            )

        body = Markup(
            '<p><strong>Pricing ready</strong> for %s</p>'
            '%s'
            '<p>%s</p>'
        ) % (
            mentions_html,
            Markup(''.join(pricing_tables)),
            Markup('<br/>'.join(totals_html)),
        )

        self.lead_id.message_post(
            body=body,
            partner_ids=notify_partners.ids,
            subtype_xmlid='mail.mt_note',
        )

        self.lead_id.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.account_manager_id.id,
            summary=_('Pricing ready for customer'),
            note=_(
                'Pricing was prepared for %s selected training(s). '
                'Open the opportunity and review the AM Pricing tab.'
            ) % len(selected),
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('AM Pricing'),
            'res_model': 'am.pricing',
            'res_id': pricing.id,
            'view_mode': 'form',
            'target': 'current',
        }


class AmPricingWizardLine(models.TransientModel):
    _name = 'am.pricing.wizard.line'
    _description = 'Send Pricing to Account Manager Line'
    _order = 'id'

    wizard_id = fields.Many2one(
        'am.pricing.wizard',
        string='Wizard',
        ondelete='cascade',
        index=True,
    )
    selected = fields.Boolean(
        string='Select',
        default=False,
    )
    course_id = fields.Many2one(
        'training.course',
        string='Training Source',
        readonly=True,
    )
    training_name = fields.Char(
        string='Training',
        readonly=True,
    )
    delivery_type = fields.Selection(
        [('Online', 'Online'), ('On site', 'On site')],
        string='Delivery Type',
        readonly=True,
    )
    students = fields.Integer(
        string='Students',
        readonly=True,
    )
    payment_method = fields.Selection(
        [('cash', 'Cash'), ('clc', 'CLC')],
        string='Payment Method',
        readonly=True,
    )
    rate_card_per_seat = fields.Monetary(
        string='Rate Card / Seat',
        currency_field='currency_id',
        readonly=True,
    )
    clcs_per_seat = fields.Float(
        string='CLCs / Seat',
        readonly=True,
    )
    total_clcs_with_vat = fields.Integer(
        string='Total CLCs + VAT',
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        readonly=True,
    )
    cost_amount = fields.Monetary(
        string='LCP Total Cost',
        currency_field='currency_id',
        readonly=True,
    )
    markup_pct = fields.Float(
        string='Markup %',
        digits=(16, 2),
        default=0.0,
        readonly=True,
    )
    training_value = fields.Monetary(
        string='Training Value',
        currency_field='currency_id',
        readonly=True,
    )
    vat_rate = fields.Float(
        string='VAT %',
        digits=(16, 2),
        readonly=True,
    )
    price_before_vat = fields.Monetary(
        string='Price Before VAT',
        currency_field='currency_id',
        compute='_compute_prices',
    )
    vat_amount = fields.Monetary(
        string='VAT Amount',
        currency_field='currency_id',
        compute='_compute_prices',
    )
    total = fields.Monetary(
        string='Total',
        currency_field='currency_id',
        compute='_compute_prices',
    )

    @api.constrains('markup_pct')
    def _check_markup_pct(self):
        for line in self:
            if line.markup_pct < 0:
                raise ValidationError(_('Markup % cannot be negative.'))

    @api.depends('training_value', 'vat_rate', 'payment_method')
    def _compute_prices(self):
        for line in self:
            training_value = line.training_value or 0.0

            if line.payment_method == 'clc':
                line.price_before_vat = training_value
                line.vat_amount = 0.0
                line.total = training_value
                continue

            vat_rate = line.vat_rate or 0.0
            if vat_rate:
                price_before_vat = training_value / (1.0 + (vat_rate / 100.0))
            else:
                price_before_vat = training_value

            vat_amount = training_value - price_before_vat

            line.price_before_vat = price_before_vat
            line.vat_amount = vat_amount
            line.total = training_value


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    am_pricing_ids = fields.One2many(
        'am.pricing',
        'lead_id',
        string='AM Pricing History',
        readonly=True,
    )

    def action_open_am_pricing_wizard(self):
        self.ensure_one()

        pricing_courses = self.training_course_ids.filtered(
            lambda course: course.payment_method in ('cash', 'clc')
        )
        if not pricing_courses:
            raise UserError(_('This opportunity has no Cash or CLC trainings to send.'))

        pricing_courses.filtered(
            lambda course: course.payment_method == 'clc'
        )._lcp_sync_clc_price_to_rate_card()

        wizard = self.env['am.pricing.wizard'].create({
            'lead_id': self.id,
            'account_manager_id': self.user_id.id or self.env.user.id,
        })

        line_commands = []
        usd = self.env.ref('base.USD')
        for course in pricing_courses:
            currency = course.lcp_currency_id or usd
            line_commands.append((0, 0, {
                'course_id': course.id,
                'training_name': (
                    course.training_id.display_name
                    or course.name
                    or _('Training')
                ),
                'delivery_type': course.location or False,
                'students': course.no_of_student or 0,
                'payment_method': course.payment_method,
                'currency_id': currency.id,
                'rate_card_per_seat': 0.0,
                'clcs_per_seat': (
                    course.lcp_clcs_per_seat or 0.0
                    if course.payment_method == 'clc'
                    else 0.0
                ),
                'total_clcs_with_vat': (
                    course.lcp_total_clcs_with_vat or 0
                    if course.payment_method == 'clc'
                    else 0
                ),
                'cost_amount': (
                    course.lcp_total_costs or 0.0
                    if course.payment_method == 'cash'
                    else 0.0
                ),
                'markup_pct': (
                    course.lcp_markup_pct or 0.0
                    if course.payment_method == 'cash'
                    else 0.0
                ),
                'training_value': (
                    course.price or 0.0
                    if course.payment_method == 'cash'
                    else 0.0
                ),
                'vat_rate': (
                    course.lcp_vat_rate or 0.0
                    if course.payment_method == 'cash'
                    else 0.0
                ),
                'selected': False,
            }))

        wizard.write({'line_ids': line_commands})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Pricing to Account Manager'),
            'res_model': 'am.pricing.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
