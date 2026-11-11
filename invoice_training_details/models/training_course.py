# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class TrainingCourse(models.Model):
    _name = "training.course"
    _description = 'Training Course'

    name = fields.Char(string='Training Name')
    no_of_student = fields.Integer(string='No of Student')
    duration = fields.Char(string='Duration')
    training_date_start = fields.Date(string='Start Date')
    training_date_end = fields.Date(string='Delivery Date')
    price = fields.Float(string='Training Price')

    move_id = fields.Many2one(
        'account.move',
        string='Move'
    )
    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead'
    )
    sale_id = fields.Many2one(
        'sale.order',
        string='Sale Order'
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        index=True,
        copy=False,
        ondelete='set null'
    )

    instructor_id = fields.Many2one(
        'hr.employee',
        string="Instructor"
    )
    descriptions = fields.Char(string='Description')
    training_id = fields.Many2one(
        'product.product',
        string='Training Name'
    )
    poref = fields.Char(string='PO Reference')
    invref = fields.Char(string='Invoice Reference')
    tr_expiry_date = fields.Char(string='Expiry')

    where_location2 = fields.Char(string='Where?')
    location = fields.Selection([
        ('Online', 'Online'),
        ('On site', 'On site')
    ])

    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('clc', 'CLC')
    ], default='cash')

    clcs_qty = fields.Float(string='CLCs Qty')
    default_item_code = fields.Char(
        related='training_id.default_code',
        string='Internal Ref'
    )
    cost_clc = fields.Char(
        related='training_id.product_tmpl_id.cost_clc',
        string="CLCs Cost"
    )
    hyperlink = fields.Char(
        related='training_id.product_tmpl_id.hyperlink',
        string="Hyper Link"
    )

    @api.depends('training_id.display_name', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.training_id.display_name or rec.name or 'Training'

    @api.onchange('training_date_start', 'training_date_end')
    def _onchange_training_dates(self):
        for rec in self:
            if rec.training_date_start and rec.training_date_end:
                duration = (
                    rec.training_date_end - rec.training_date_start
                ).days + 1
                rec.duration = str(duration) + ' days'

