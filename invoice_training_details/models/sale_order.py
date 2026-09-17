# -*- coding: utf-8 -*-

import re

from odoo import api, models, fields, _
from odoo.exceptions import UserError
from .sync_utils import sync_commands


class SaleOrder(models.Model):
    _inherit = "sale.order"

    training_name = fields.Char(string='Training Name')
    service_name = fields.Char(string='Service Name')
    total_training_price = fields.Monetary(string='Total Training Price', compute="_compute_training_price", store=True)
    total_service_price = fields.Float(string='Total Servicr Price', compute="_compute_service_price", store=True)
    half_advance_payment_before = fields.Monetary(string='Advance payment amount 50% (paid)')
    half_payment_after = fields.Monetary(string='50% Amount after Training Delivery (Not Yet Paid)')
    training_course_ids = fields.One2many('training.course', 'sale_id', string='Training Courses')
    pro_service_ids = fields.One2many('pro.service', 'pro_sale_id', string='Professional Services')
    
    #Add extera
    instructor_id = fields.Many2one('hr.employee',string="Instructor")
    descriptions = fields.Char(string='Description')
    # ordering_partner_id = fields.Many2one('res.partner',string='Ordering Partner')
    training_id = fields.Many2one('product.template',string='Training Name')
    location = fields.Selection([('Cisco U','Cisco U'),('ILT','ILT'),('VILT','VILT')])
    where_location = fields.Char(string='Where?')
    payment_method = fields.Selection([('cash','Cash'),('clc','CLC')],default='cash')
    
    display_training_table = fields.Boolean(string='Display Training Table', help='display traning table in training invoice PDF.')
    display_signature = fields.Boolean(string='Display Signature', help='display signature in training invoice PDF.')
    display_stamp = fields.Boolean(string='Display Stamp', help='display Stamp in training invoice PDF.')
    display_ksa_qr = fields.Boolean(string='Display KSA QR', help='display KSA Qr in training invoice PDF.')
    
    display_instructor = fields.Boolean(string='Display Instructor', help='display Instructor in training invoice PDF.')
    display_location = fields.Boolean(string='Display Location', help='display Location in training invoice PDF.')
    display_downpayment = fields.Boolean(string='Display Downpayment', help='display Downpayment in training invoice PDF.')
    display_total = fields.Boolean(string='Display Total Amount', help='display Total amount in training invoice PDF.')
    display_due_amount = fields.Boolean(string='Display Due Amount', help='display Due in training invoice PDF.')
    display_where = fields.Boolean(string="Display Where?")
    display_description = fields.Boolean(string="Display Description")
    
    # 
    ticket_ids = fields.One2many('ticket.ticket','ticket_order_id',string='Tickets')
    hotel_ids = fields.One2many('hotel.hotel','hotel_order_id',string='Hotels')
    total_price_all = fields.Float(string="Total Amount",compute='_compute_total')
    visa = fields.Boolean(string="Visa")
    start_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    book_details_id = fields.Many2many('ir.attachment', 'doc_attach_order', 'doc_id', 'attach_order_id',
                                         string="Booking Details",
                                         help='You can attach the copy of your document', copy=False)
    details = fields.Html(string="Details")
    cost = fields.Float(string="Cost")
    currency_total = fields.Float(string="Total in Currency",compute='_compute_cur_tot')

    
    training_vendor = fields.Char(string="Training Vendor")
    training_type = fields.Char(string="Training Type")
    
    
    @api.depends('amount_total', 'currency_id')
    def _compute_cur_tot(self):
        total = 0
        for rec in self:
            if rec.amount_total and rec.currency_id:
                rec.currency_total = float(rec.amount_total) / float(rec.currency_id.rate)
                # round(rec.currency_total,2)
            # raise ValidationError(rec.currency_total)
            else:
                rec.currency_total = 0
                
    def _compute_total(self):
        ticket_total =0
        hotel_toal=0
        cost = 0
        for rec in self:
            if rec.ticket_ids and rec.hotel_ids:
                for ticket in rec.ticket_ids:
                    ticket_total+=ticket.price
                for hotel in rec.hotel_ids:
                    hotel_toal+=hotel.price
                rec.total_price_all = ticket_total + hotel_toal + rec.cost
            else:
                rec.total_price_all = 0
    
    # extra information tab
    clcs_qty = fields.Float(string='CLCs Qty')
    so_no = fields.Char(string='SO#')
    tr_expiry_date = fields.Date(string='Expiry Date')

    # logistics tab
    instructor_logistics = fields.Char(string='Instructor Logistics')
    ctrng = fields.Float(string='Catering')  # Now it's manually editable
    
    bank_details = fields.Html(
        string='Bank Details',
        default='''
            <div>
                <strong>Bank Details:</strong><br/>
                We kindly request you to transfer OR deposit cheque payment to below bank account details:<br/>
                <strong>Account Name:</strong> NIL Data Communications Middle East DMCC<br/>
                <strong>Bank Name:</strong> Emirates Islamic Bank<br/>
                <strong>Bank Branch:</strong> JLT – Dubai- UAE<br/>
                <strong>Swift code:</strong> MEBLAEAD<br/>
                <strong>Account Currency:</strong> USD<br/>
                <strong>IBAN:</strong> AE690340003528215597102
            </div>
        '''
    )

    _CASH_TERMS_HEADER = (
        '<div class="o_order_terms_header">'
        '<strong>Instructor From:</strong><br/>'
        '<strong>End Customer:</strong><br/>'
        '<strong>Candidate Details:</strong><br/>'
        '</div>'
    )

    _CLC_TERMS_HEADER = (
        '<div class="o_order_terms_header">'
        '<strong>Instructor From:</strong><br/>'
        '<strong>End Customer:</strong><br/>'
        '<strong>Candidate Details:</strong><br/>'
        '<strong>#of CLCs Utilized:</strong><br/>'
        '</div>'
    )

    term_and_cond = fields.Html(
        string='Term and conditions',
        default=lambda self: self._default_term_and_cond()
    )

    @api.model
    def _default_term_and_cond(self):
        return self._CASH_TERMS_HEADER

    @api.model
    def _remove_order_terms_header(self, value):
        return re.sub(
            r'<div[^>]*class=["\'][^"\']*o_order_terms_header[^"\']*["\'][^>]*>.*?</div>',
            '',
            value or '',
            flags=re.IGNORECASE | re.DOTALL
        ).strip()

    @api.onchange('payment_method')
    def _onchange_payment_method_terms(self):
        for rec in self:
            existing_terms = rec._remove_order_terms_header(rec.term_and_cond)

            if rec.payment_method == 'clc':
                header = rec._CLC_TERMS_HEADER
            else:
                header = rec._CASH_TERMS_HEADER

            rec.term_and_cond = header + existing_terms
    
    @api.depends('pro_service_ids.price')
    def _compute_service_price(self):
        for rec in self:
            if rec.pro_service_ids:
                rec.total_service_price = sum(rec.pro_service_ids.mapped('price'))
            
            else:
                rec.total_service_price = 0
                
    @api.depends('training_course_ids.price')
    def _compute_training_price(self):
        for rec in self:
            if rec.training_course_ids:
                rec.total_training_price = sum(rec.training_course_ids.mapped('price'))
            else:
                rec.total_training_price = 0
                
    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        vals.update({
            'training_name': self.training_name,
            'half_advance_payment_before': self.half_advance_payment_before,
            'half_payment_after': self.half_payment_after,
            'training_course_ids': [(6, 0, self.training_course_ids.ids)],
            'pro_service_ids': [(6, 0, self.pro_service_ids.ids)],
            'clcs_qty': self.clcs_qty,
            'so_no': self.so_no,
            'tr_expiry_date': self.tr_expiry_date,
            'instructor_logistics': self.instructor_logistics,
            'ctrng': self.ctrng,
            # 'descriptions': self.descriptions,
            # 'ordering_partner_id': self.ordering_partner_id.id,
            # 'where_location': self.where_location,
            
            'instructor_id': self.instructor_id.id,
            'training_id': self.training_id.id,
            # 'train_language': self.train_language,
            # 'location': self.location,
            # 'payment_method': self.payment_method,
            'clcs_qty': self.clcs_qty,
            'service_name': self.service_name,
            'bank_details': self.bank_details,
            'term_and_cond': self.term_and_cond,
            
            'training_vendor': self.training_vendor,
            'training_type': self.training_type,
            
        })
        return vals
        
    # ks_qr_code = fields.Binary("KSA QR Code", compute="_compute_ksa_qr_code")

    # def generate_ksa_qr_code(self, seller_name, vat_number, invoice_date, total_amount, vat_amount):
    #     # Encode data in TLV format
    #     def encode_tlv(tag, value):
    #         value_bytes = value.encode('utf-8')
    #         return bytes([tag, len(value_bytes)]) + value_bytes

    #     qr_data = (
    #         encode_tlv(1, seller_name) +
    #         encode_tlv(2, vat_number) +
    #         encode_tlv(3, invoice_date) +
    #         encode_tlv(4, str(total_amount)) +
    #         encode_tlv(5, str(vat_amount))
    #     )

    #     # Generate QR code
    #     qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
    #     qr.add_data(base64.b64encode(qr_data).decode('utf-8'))
    #     qr.make(fit=True)

    #     # Convert QR code to image
    #     img = qr.make_image(fill_color="black", back_color="white")
    #     buffer = BytesIO()
    #     img.save(buffer, format="PNG")
    #     qr_code_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
    #     buffer.close()
    #     return qr_code_image

    # @api.depends('partner_id', 'date', 'amount_total', 'amount_tax')
    # def _compute_ksa_qr_code(self):
    #     for move in self:
    #         if move.move_type in ['out_invoice', 'out_refund'] and move.company_id.vat:
    #             move.ks_qr_code = self.generate_ksa_qr_code(
    #                 move.company_id.name,
    #                 move.company_id.vat,
    #                 move.invoice_date.strftime('%Y-%m-%d %H:%M:%S') if move.invoice_date else '',
    #                 move.amount_total,
    #                 move.amount_tax
    #             )
    #         else:
    #             move.ks_qr_code = False

    @api.depends('training_course_ids.price')
    def _compute_training_price(self):
        for rec in self:
            rec.total_training_price = sum(rec.training_course_ids.mapped('price'))
            
    def _check_nil_sync_draft(self):
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            raise UserError(_('Synchronize only a draft quotation.'))

    def synch_order(self):
        self._check_nil_sync_draft()
        items = []
        for course in self.training_course_ids:
            if not course.training_id:
                raise UserError(_('Select a product for every training before synchronizing.'))
            if course.lead_id and course.lcp_cost_learning_partner:
                # Reuse the same pricing/tax rules as New SO, including EnterOne CLC.
                vals = course.lead_id._lcp_sale_lines(course, self.company_id)[0][2]
            else:
                vals = {
                    'product_id': course.training_id.id,
                    'name': course.training_id.display_name,
                    'product_uom_qty': 1,
                    'price_unit': course.price,
                }
            items.append((course, vals))
        self.write({'order_line': sync_commands(self.order_line, items, 'nil_sync_training_id')})
        return True

    def synch_pro_order(self):
        self._check_nil_sync_draft()
        items = []
        for service in self.pro_service_ids:
            if not service.training_id:
                raise UserError(_('Select a product for every service before synchronizing.'))
            items.append((service, {
                'product_id': service.training_id.id,
                'name': service.training_id.display_name,
                'product_uom_qty': 1,
                'price_unit': service.price,
            }))
        self.write({'order_line': sync_commands(self.order_line, items, 'nil_sync_service_id')})
        return True


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    nil_sync_training_id = fields.Many2one('training.course', copy=False, ondelete='set null', index=True)
    nil_sync_service_id = fields.Many2one('pro.service', copy=False, ondelete='set null', index=True)
