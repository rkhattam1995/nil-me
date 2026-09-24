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

    @api.depends(
        'line_ids.price_before_vat',
        'line_ids.vat_amount',
        'line_ids.total',
    )
    def _compute_totals(self):
        for rec in self:
            rec.subtotal = sum(rec.line_ids.mapped('price_before_vat'))
            rec.vat_amount = sum(rec.line_ids.mapped('vat_amount'))
            rec.total = sum(rec.line_ids.mapped('total'))

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
    description = fields.Text(
        string='Description',
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
    markup_pct = fields.Float(
        string='Markup %',
        digits=(16, 2),
        default=0.0,
        required=True,
        help='Selling Price Before VAT = LCP Total Cost x (1 + Markup %).',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        'am.pricing.wizard.line',
        'wizard_id',
        string='Cash Trainings',
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

    @api.onchange('markup_pct')
    def _onchange_markup_pct(self):
        self.line_ids._compute_prices()

    @api.constrains('markup_pct')
    def _check_markup_pct(self):
        for rec in self:
            if rec.markup_pct < 0:
                raise ValidationError(_('Markup % cannot be negative.'))

    @api.depends(
        'line_ids.selected',
        'line_ids.price_before_vat',
        'line_ids.vat_amount',
        'line_ids.total',
    )
    def _compute_totals(self):
        for rec in self:
            selected = rec.line_ids.filtered('selected')
            rec.subtotal = sum(selected.mapped('price_before_vat'))
            rec.vat_amount = sum(selected.mapped('vat_amount'))
            rec.total = sum(selected.mapped('total'))

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)

        if self.env.context.get('active_model') != 'crm.lead':
            return vals

        lead = self.env['crm.lead'].browse(self.env.context.get('active_id')).exists()
        if not lead:
            return vals

        cash_courses = lead.training_course_ids.filtered(
            lambda course: course.payment_method == 'cash'
        )
        if not cash_courses:
            raise UserError(_('This opportunity has no Cash trainings to send.'))

        currencies = cash_courses.mapped('lcp_currency_id').filtered(lambda c: c)
        if not currencies:
            currency = self.env.ref('base.USD')
        else:
            currency = currencies[0]

        vals.update({
            'lead_id': lead.id,
            'account_manager_id': lead.user_id.id or self.env.user.id,
            'currency_id': currency.id,
            'markup_pct': 0.0,
            'line_ids': [
                (0, 0, {
                    'selected': False,
                    'course_id': course.id,
                    'training_name': (
                        course.training_id.display_name
                        or course.name
                        or _('Training')
                    ),
                    'description': (
                        course.descriptions
                        or course.training_id.description_sale
                        or ''
                    ),
                    'delivery_type': course.location or False,
                    'students': course.no_of_student or 0,
                    'cost_amount': course.lcp_total_costs or 0.0,
                    'vat_rate': course.lcp_vat_rate or 0.0,
                    'currency_id': (
                        course.lcp_currency_id.id
                        if course.lcp_currency_id
                        else currency.id
                    ),
                })
                for course in cash_courses
            ],
        })
        return vals

    def action_send(self):
        self.ensure_one()

        if self.markup_pct < 0:
            raise UserError(_('Markup % cannot be negative.'))

        selected = self.line_ids.filtered('selected')
        if not selected:
            raise UserError(_('Select at least one Cash training.'))

        currencies = selected.mapped('currency_id')
        if len(currencies) > 1:
            raise UserError(_('Selected trainings must use the same currency.'))

        if not self.account_manager_id:
            raise UserError(_('Select an Account Manager.'))

        selected_currency = currencies[:1]
        pricing = self.env['am.pricing'].create({
            'lead_id': self.lead_id.id,
            'account_manager_id': self.account_manager_id.id,
            'sent_by_id': self.env.user.id,
            'sent_at': fields.Datetime.now(),
            'markup_pct': self.markup_pct,
            'currency_id': selected_currency.id,
            'line_ids': [
                (0, 0, {
                    'course_id': line.course_id.id,
                    'training_name': line.training_name,
                    'description': line.description,
                    'delivery_type': line.delivery_type,
                    'students': line.students,
                    'price_before_vat': line.price_before_vat,
                    'vat_rate': line.vat_rate,
                    'vat_amount': line.vat_amount,
                    'total': line.total,
                })
                for line in selected
            ],
        })

        currency = selected_currency
        rows = []
        for line in pricing.line_ids:
            delivery = dict(line._fields['delivery_type'].selection).get(
                line.delivery_type,
                line.delivery_type or ''
            )
            rows.append(
                '<tr>'
                '<td style="padding:6px;border:1px solid #ddd;">%s</td>'
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
                    escape(line.description or ''),
                    escape(delivery),
                    line.students,
                    escape(formatLang(self.env, line.price_before_vat, currency_obj=currency)),
                    ('%g' % (line.vat_rate or 0.0)),
                    escape(formatLang(self.env, line.vat_amount, currency_obj=currency)),
                    escape(formatLang(self.env, line.total, currency_obj=currency)),
                )
            )

        body = Markup(
            '<p><strong>Pricing ready for Account Manager</strong></p>'
            '<p>Account Manager: %s</p>'
            '<table style="border-collapse:collapse;width:100%%;">'
            '<thead><tr>'
            '<th style="padding:6px;border:1px solid #ddd;text-align:left;">Training</th>'
            '<th style="padding:6px;border:1px solid #ddd;text-align:left;">Description</th>'
            '<th style="padding:6px;border:1px solid #ddd;text-align:left;">Delivery Type</th>'
            '<th style="padding:6px;border:1px solid #ddd;">Students</th>'
            '<th style="padding:6px;border:1px solid #ddd;">Price Before VAT</th>'
            '<th style="padding:6px;border:1px solid #ddd;">VAT</th>'
            '<th style="padding:6px;border:1px solid #ddd;">VAT Amount</th>'
            '<th style="padding:6px;border:1px solid #ddd;">Total</th>'
            '</tr></thead><tbody>%s</tbody></table>'
            '<p><strong>Subtotal:</strong> %s<br/>'
            '<strong>VAT:</strong> %s<br/>'
            '<strong>Total:</strong> %s</p>'
        ) % (
            escape(self.account_manager_id.name),
            Markup(''.join(rows)),
            escape(formatLang(self.env, pricing.subtotal, currency_obj=currency)),
            escape(formatLang(self.env, pricing.vat_amount, currency_obj=currency)),
            escape(formatLang(self.env, pricing.total, currency_obj=currency)),
        )

        self.lead_id.message_post(
            body=body,
            partner_ids=[self.account_manager_id.partner_id.id],
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
        required=True,
        ondelete='cascade',
    )
    selected = fields.Boolean(string='Select', default=False)
    course_id = fields.Many2one(
        'training.course',
        string='Training Source',
        required=True,
        readonly=True,
    )
    training_name = fields.Char(string='Training', readonly=True)
    description = fields.Text(string='Description', readonly=True)
    delivery_type = fields.Selection(
        [('Online', 'Online'), ('On site', 'On site')],
        string='Delivery Type',
        readonly=True,
    )
    students = fields.Integer(string='Students', readonly=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        readonly=True,
    )
    cost_amount = fields.Monetary(
        string='LCP Total Cost',
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

    @api.depends('cost_amount', 'vat_rate', 'wizard_id.markup_pct')
    def _compute_prices(self):
        for line in self:
            markup = line.wizard_id.markup_pct or 0.0
            price_before_vat = (
                (line.cost_amount or 0.0)
                * (1.0 + (markup / 100.0))
            )
            vat_amount = price_before_vat * (line.vat_rate or 0.0) / 100.0
            line.price_before_vat = price_before_vat
            line.vat_amount = vat_amount
            line.total = price_before_vat + vat_amount


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

        if not self.training_course_ids.filtered(
            lambda course: course.payment_method == 'cash'
        ):
            raise UserError(_('This opportunity has no Cash trainings to send.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Pricing to Account Manager'),
            'res_model': 'am.pricing.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'crm.lead',
                'active_id': self.id,
            },
        }
