# -*- coding: utf-8 -*-

from odoo import api, models, fields


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    is_training_order = fields.Boolean(
        string='Is Training Order'
    )

    training_name = fields.Char(
        string='Training Name'
    )

    service_name = fields.Char(
        string='Service Name'
    )

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

    training_course_ids = fields.One2many(
        'training.course',
        'purchase_order_id',
        string='Training Courses'
    )

    pro_service_ids = fields.One2many(
        'pro.service',
        'purchase_order_id',
        string='Professional Services'
    )

    instructor_id = fields.Many2one(
        'hr.employee',
        string="Instructor"
    )

    descriptions = fields.Char(
        string='Description'
    )

    training_id = fields.Many2one(
        'product.template',
        string='Training Name'
    )

    train_language = fields.Char(
        string='Training Language'
    )

    location = fields.Selection([
        ('Cisco U', 'Cisco U'),
        ('ILT', 'ILT'),
        ('VILT', 'VILT')
    ], string='Location')

    where_location = fields.Char(
        string='Where?'
    )

    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('clc', 'CLC')
    ], default='cash')

    half_advance_payment_before = fields.Monetary(
        string='Advance Payment (50%)'
    )

    half_payment_after = fields.Monetary(
        string='Balance Payment (50%)'
    )

    ticket_ids = fields.One2many(
        'ticket.ticket',
        'purchase_order_id',
        string='Tickets'
    )

    hotel_ids = fields.One2many(
        'hotel.hotel',
        'purchase_order_id',
        string='Hotels'
    )

    total_price_all = fields.Float(
        string="Total Amount",
        compute='_compute_total'
    )

    visa = fields.Boolean(
        string="Visa"
    )

    start_date = fields.Date(
        string="From Date"
    )

    end_date = fields.Date(
        string="To Date"
    )

    book_details_id = fields.Many2many(
        'ir.attachment',
        'doc_attach_purchase_order',
        'doc_id',
        'attach_order_id',
        string="Booking Details",
        help='You can attach the copy of your document',
        copy=False
    )

    training_vendor = fields.Char(
        string="Training Vendor"
    )

    training_type = fields.Char(
        string="Training Type"
    )

    display_training_table = fields.Boolean(
        string='Display Training Table in PDF'
    )

    display_signature = fields.Boolean(
        string='Display Signature in PDF'
    )

    display_stamp = fields.Boolean(
        string='Display Stamp in PDF'
    )

    display_ksa_qr = fields.Boolean(
        string='Display KSA QR in PDF'
    )

    display_instructor = fields.Boolean(
        string='Display Instructor in PDF'
    )

    display_location = fields.Boolean(
        string='Display Location in PDF'
    )

    display_downpayment = fields.Boolean(
        string='Display Downpayment in PDF'
    )

    display_total = fields.Boolean(
        string='Display Total Amount in PDF'
    )

    display_due_amount = fields.Boolean(
        string='Display Due Amount in PDF'
    )

    display_where = fields.Boolean(
        string="Display Where?"
    )

    display_description = fields.Boolean(
        string="Display Description"
    )

    clcs_qty = fields.Float(
        string='CLCs Qty'
    )

    po_reference = fields.Char(
        string='PO#'
    )

    tr_expiry_date = fields.Date(
        string='Expiry Date'
    )

    bank_details = fields.Html(
        string='Bank Details',
        default=(
            'We kindly request you to transfer OR deposit cheque payment '
            'to below bank account details </br> '
            'Account Name: NIL Data Communications Middle East DMCC '
            'Emirates Islamic Bank JLT Branch - Dubai- UAE </br> '
            'Swiftcode: MEBLAEAD </br> '
            'Account Currency: USD </br> '
            'IBAN: AE690340003528215597102'
        )
    )

    term_and_cond = fields.Html(
        string='Term and conditions',
        default=(
            '<strong>CLC Order</strong></br>'
            '<strong>Instructor from:</strong></br>'
            '<strong>CLCs Utilized:</strong></br></br>'
            '1. PO Reference #: PCD-006-2024 </br> '
            '2. PO Amendment PCD-006-2024 </br> '
            '3. End customer name: Saudi Authority for Data and Artificial Intelligence, Saudi Arabia. </br>'
            '4. The invoice amount does not include VAT or Withholding taxes - '
            'it must be paid by Taqnia Cyber if any, without any charging or '
            'deduction from the invoice amount. '
            '5. Taqnia Cyber will pay the taxes to KSA authorities directly.</br> '
            '6. Taqnia Cyber must bear Money transfers or bank charges on payment.</br>'
        )
    )

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

    @api.depends(
        'ticket_ids.price',
        'hotel_ids.price',
        'cost'
    )
    def _compute_total(self):
        for rec in self:
            ticket_total = (
                sum(ticket.price for ticket in rec.ticket_ids)
                if rec.ticket_ids else 0
            )

            hotel_total = (
                sum(hotel.price for hotel in rec.hotel_ids)
                if rec.hotel_ids else 0
            )

            rec.total_price_all = (
                ticket_total +
                hotel_total +
                rec.cost
            )

    @api.depends('pro_service_ids.price')
    def _compute_service_price(self):
        for rec in self:
            rec.total_service_price = (
                sum(rec.pro_service_ids.mapped('price'))
                if rec.pro_service_ids else 0
            )

    @api.depends('training_course_ids.price')
    def _compute_training_price(self):
        for rec in self:
            rec.total_training_price = (
                sum(rec.training_course_ids.mapped('price'))
                if rec.training_course_ids else 0
            )

    def action_sync_training_lines(self):
        self.ensure_one()

        order_lines = []

        for course in self.training_course_ids:
            order_lines.append((0, 0, {
                'product_id': course.training_id.id,
                'name': course.training_id.name,
                'product_qty': 1,
                'price_unit': course.price,
                'date_planned': (
                    self.date_order or fields.Date.today()
                ),
            }))

        self.order_line = False
        self.write({
            'order_line': order_lines
        })

        return True

    def action_sync_service_lines(self):
        self.ensure_one()

        order_lines = []

        for service in self.pro_service_ids:
            order_lines.append((0, 0, {
                'product_id': service.training_id.id,
                'name': service.training_id.name,
                'product_qty': 1,
                'price_unit': service.price,
                'date_planned': (
                    self.date_order or fields.Date.today()
                ),
            }))

        self.order_line = False
        self.write({
            'order_line': order_lines
        })

        return True
