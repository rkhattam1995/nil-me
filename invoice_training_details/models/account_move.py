# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import qrcode
from io import BytesIO

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .sync_utils import sync_commands


class AccountMove(models.Model):
    _inherit = "account.move"

    crm_lead_id = fields.Many2one(
        'crm.lead',
        string='CRM Opportunity',
        index=True,
        copy=False,
        ondelete='set null'
    )

    source_purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Source Purchase Order',
        index=True,
        copy=False,
        ondelete='set null'
    )
    purchase_training_type = fields.Selection(
        [
            ('training_vendor', 'Training Vendor'),
            ('instructor', 'Instructor'),
        ],
        string='Training PO Type',
        copy=False
    )
    instructor_training_course_id = fields.Many2one(
        'training.course',
        string='Training',
        copy=False,
        ondelete='set null'
    )
    instructor_from = fields.Date(string='Instructor From', copy=False)
    instructor_to = fields.Date(string='Instructor To', copy=False)
    instructor_days = fields.Integer(string='No. of Days', copy=False)
    instructor_daily_rate = fields.Monetary(
        string='Daily Rate',
        currency_field='currency_id',
        copy=False
    )
    instructor_total = fields.Monetary(
        string='Instructor Total',
        currency_field='currency_id',
        copy=False
    )

    training_name = fields.Char(string='Training Name')
    service_name = fields.Char(string='Service Name')
    total_training_price = fields.Monetary(
        string='Total Training Price',
        compute="_compute_training_price",
        store=True
    )
    total_service_price = fields.Float(
        string='Total Service Price',
        compute="_compute_service_price",
        store=True
    )
    half_advance_payment_before = fields.Monetary(
        string='Advance payment amount 50% (paid)'
    )
    half_payment_after = fields.Monetary(
        string='50% Amount after Training Delivery (Not Yet Paid)'
    )
    training_course_ids = fields.One2many(
        'training.course',
        'move_id',
        string='Training Courses'
    )
    pro_service_ids = fields.One2many(
        'pro.service',
        'pro_move_id',
        string='Professional Services'
    )
    invoice_payment_am = fields.Monetary(
        string="Amount Paid",
        compute='_compute_am_paid'
    )
    invoice_payment_per = fields.Float(
        string="Amount Paid Percentage %",
        compute='_compute_am_paid_per'
    )

    display_training_table = fields.Boolean(
        string='Display Training Table',
        help='Display training table in training invoice PDF.'
    )
    display_signature = fields.Boolean(
        string='Display Signature',
        help='Display signature in training invoice PDF.'
    )
    display_stamp = fields.Boolean(
        string='Display Stamp',
        help='Display stamp in training invoice PDF.'
    )
    display_ksa_qr = fields.Boolean(
        string='Display KSA QR',
        help='Display KSA QR in training invoice PDF.'
    )
    display_instructor = fields.Boolean(
        string='Display Instructor',
        help='Display instructor in training invoice PDF.'
    )
    display_location = fields.Boolean(
        string='Display Location',
        help='Display location in training invoice PDF.'
    )
    display_downpayment = fields.Boolean(
        string='Display Downpayment',
        help='Display downpayment in training invoice PDF.'
    )
    display_total = fields.Boolean(
        string='Display Total Amount',
        help='Display total amount in training invoice PDF.'
    )
    display_due_amount = fields.Boolean(
        string='Display Due Amount',
        help='Display due amount in training invoice PDF.'
    )
    display_where = fields.Boolean(string="Display Where?")
    display_description = fields.Boolean(string="Display Description")
    instructor_logistics = fields.Char(string="Instructor Logistics")

    instructor_id = fields.Many2one('hr.employee', string="Instructor")
    descriptions = fields.Char(string='Description')
    training_id = fields.Many2one(
        'product.template',
        string='Training Name'
    )
    train_language = fields.Char(string='Training Language')
    location = fields.Selection([
        ('Cisco U', 'Cisco U'),
        ('ILT', 'ILT'),
        ('VILT', 'VILT')
    ])
    where_location = fields.Char(string='Where?')
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('clc', 'CLC')
    ], default='cash')

    clcs_qty = fields.Float(string='CLCs Qty')
    so_no = fields.Char(string='SO#')
    tr_expiry_date = fields.Date(string='Expiry Date')
    ctrng = fields.Float(string='Catering')

    ks_qr_code = fields.Binary(
        "KSA QR Code",
        compute="_compute_ksa_qr_code"
    )
    bank_details = fields.Html(string='Bank Details')
    term_and_cond = fields.Html(string='Term and conditions')
    currency_total = fields.Float(
        string="Total in Currency",
        compute='_compute_cur_tot'
    )
    training_vendor = fields.Char(string="Training Vendor")
    training_type = fields.Char(string="Training Type")

    @api.depends('amount_total', 'currency_id')
    def _compute_cur_tot(self):
        for rec in self:
            if rec.amount_total and rec.currency_id:
                rec.currency_total = (
                    float(rec.amount_total) /
                    float(rec.currency_id.rate)
                )
            else:
                rec.currency_total = 0

    @api.depends('amount_total', 'amount_residual')
    def _compute_am_paid(self):
        for rec in self:
            if rec.amount_total:
                rec.invoice_payment_am = (
                    rec.amount_total - rec.amount_residual
                )
            else:
                rec.invoice_payment_am = 0

    @api.depends('invoice_payment_am', 'amount_total')
    def _compute_am_paid_per(self):
        for rec in self:
            if rec.invoice_payment_am > 0 and rec.amount_total > 0:
                rec.invoice_payment_per = (
                    rec.invoice_payment_am /
                    rec.amount_total
                ) * 100
            else:
                rec.invoice_payment_per = 0

    def generate_ksa_qr_code(
        self,
        seller_name,
        vat_number,
        invoice_date,
        total_amount,
        vat_amount
    ):
        def encode_tlv(tag, value):
            value_bytes = value.encode('utf-8')
            return bytes([tag, len(value_bytes)]) + value_bytes

        qr_data = (
            encode_tlv(1, seller_name) +
            encode_tlv(2, vat_number) +
            encode_tlv(3, invoice_date) +
            encode_tlv(4, str(total_amount)) +
            encode_tlv(5, str(vat_amount))
        )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L
        )
        qr.add_data(base64.b64encode(qr_data).decode('utf-8'))
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_code_image = base64.b64encode(
            buffer.getvalue()
        ).decode('utf-8')
        buffer.close()
        return qr_code_image

    @api.depends('partner_id', 'invoice_date', 'amount_total', 'amount_tax')
    def _compute_ksa_qr_code(self):
        for move in self:
            if (
                move.move_type in ['out_invoice', 'out_refund'] and
                move.company_id.vat
            ):
                move.ks_qr_code = self.generate_ksa_qr_code(
                    move.company_id.name,
                    move.company_id.vat,
                    move.invoice_date.strftime('%Y-%m-%d %H:%M:%S')
                    if move.invoice_date else '',
                    move.amount_total,
                    move.amount_tax
                )
            else:
                move.ks_qr_code = False

    @api.depends('pro_service_ids.price')
    def _compute_service_price(self):
        for rec in self:
            if rec.pro_service_ids:
                rec.total_service_price = sum(
                    rec.pro_service_ids.mapped('price')
                )
            else:
                rec.total_service_price = 0

    @api.depends('training_course_ids.price')
    def _compute_training_price(self):
        for rec in self:
            if rec.training_course_ids:
                rec.total_training_price = sum(
                    rec.training_course_ids.mapped('price')
                )
            else:
                rec.total_training_price = 0

    def synch_order(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Synchronize only a draft invoice.'))
        if any(line.sale_line_ids or line.purchase_line_id for line in self.invoice_line_ids):
            raise UserError(_('This invoice is linked to a sale or purchase order. Update it through its source order to preserve invoiced quantities and prices.'))
        items = []
        for course in self.training_course_ids:
            if not course.training_id:
                raise UserError(_('Select a product for every training before synchronizing.'))
            items.append((course, {
                'product_id': course.training_id.id,
                'quantity': 1,
                'price_unit': course.price,
            }))
        self.write({'invoice_line_ids': sync_commands(self.invoice_line_ids, items, 'nil_sync_training_id')})
        return True


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    nil_sync_training_id = fields.Many2one('training.course', copy=False, ondelete='set null', index=True)
