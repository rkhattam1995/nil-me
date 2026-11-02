# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import UserError

class Lead(models.Model):
    _inherit = 'crm.lead'
    # Override the currency_id field to set a default value of USD
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency', 
        default=lambda self: self.env.ref('base.USD')  # Automatically set to USD
    )
    training_name = fields.Many2one('res.partner',string='End Customer')
    venue = fields.Float(string='Venue')
    service_name = fields.Char(string='Service Name')
    total_training_price = fields.Float(
        string='Total Training Price',
        default=0.0,
    )
    total_service_price = fields.Float(string='Total Service Price', compute="_compute_service_price", store=True)
    half_advance_payment_before = fields.Float(string='Advance payment amount 50% (paid)')
    half_payment_after = fields.Float(string='50% Amount after Training Delivery (Not Yet Paid)')
    training_course_ids = fields.One2many('training.course', 'lead_id', string='Training Courses')
    pro_service_ids = fields.One2many('pro.service','pro_lead_id',string='Professional Services')
    end_customer = fields.Char(string='End Client')
    cisco_am = fields.Char(string='Cisco Account Manager')
    cost_details_ids = fields.One2many('cost.details', 'cos_lead_id', string="Costs Details")
    ticket_ids = fields.One2many('ticket.ticket','ticket_lead_id',string='Tickets')
    hotel_ids = fields.One2many('hotel.hotel','hotel_lead_id',string='Hotels')
    total_price_all = fields.Float(string="Total Logistics",compute='_compute_total')
    visa = fields.Boolean(string="Visa")
    start_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    book_details_id = fields.Many2many('ir.attachment', 'doc_attach_rel4', 'doc_id', 'attach_id5',
                                         string="Booking Details",
                                         help='You can attach the copy of your document', copy=False)
    details = fields.Html(string="Details")
    cost = fields.Float(string="Cost")
    ins_time = fields.Float(string="Instructor")
    margin1 = fields.Float(string="Total Costs", compute='_compute_margin1')
    nilme_share = fields.Float(string="NIL ME Share $", compute='_compute_nilme_share')


    # Add extra fields
    instructor_id = fields.Many2one('hr.employee',string="Instructor")
    descriptions = fields.Char(string='Description')
    

    ordering_partner_id = fields.Many2one('res.partner',string='Ordering Partner')
    training_id = fields.Many2one('product.template',string='Training Name')
    location = fields.Selection([('Online','Online'),('On site','On site')])
    payment_method = fields.Selection([('cash','Cash'),('clc','CLC')],default='cash')
    has_cash_training = fields.Boolean(
        string='Has Cash Training',
        compute='_compute_has_cash_training'
    )
    has_training = fields.Boolean(
        string='Has Training',
        compute='_compute_has_training'
    )
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'crm_lead_id',
        string='Purchase Orders'
    )
    purchase_order_count = fields.Integer(
        string='Purchase Orders',
        compute='_compute_purchase_order_count'
    )
    clcs_qty = fields.Float(string='CLCs Qty')
    learnig_partner = fields.Selection([('Koenig','Koenig'),('Mira','Mira'),('EnterOne','EnterOne'),('NIL LTD','NIL LTD'),('NIL SA','NIL SA')])
    con_per = fields.Char(string='Contact Person')

    # Extra information tab
    clcs_qty = fields.Float(string='Customer CLCs Qty')
    so_no = fields.Char(string='SO#')
    tr_expiry_date = fields.Date(string='Expiry Date')
    poref = fields.Char(string='PO Ref:')
    invref = fields.Char(string='Invoice Ref:')

    # Logistics tab
    instructor_logistics = fields.Char(string='Instructor Logistics')
    uber = fields.Float(string='Uber')
    ctrng = fields.Float(string='Catering')  # Now it's manually editable

    @api.depends('training_course_ids.payment_method')
    def _compute_has_cash_training(self):
        for lead in self:
            lead.has_cash_training = any(
                course.payment_method == 'cash'
                for course in lead.training_course_ids
            )

    @api.depends('training_course_ids')
    def _compute_has_training(self):
        for lead in self:
            lead.has_training = bool(lead.training_course_ids)

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for lead in self:
            lead.purchase_order_count = len(lead.purchase_order_ids)

    def action_new_purchase_order(self):
        """Open a new PO for the Cash training lines of this opportunity."""
        self.ensure_one()

        cash_courses = self.training_course_ids.filtered(
            lambda course: course.payment_method == 'cash'
        )
        if not cash_courses:
            raise UserError(_(
                'New PO is available only when at least one training line '
                'has Cash as its payment method.'
            ))

        purchase_lines = []
        for course in cash_courses:
            product = course.training_id
            if not product:
                raise UserError(_(
                    'Every Cash training line must have a Training Name '
                    'before creating the PO.'
                ))

            description_lines = [
                product.display_name or course.name or self.name,
                'Number of Students: %s' % (course.no_of_student or 0),
            ]

            if course.duration:
                description_lines.append(
                    'Duration: %s' % course.duration
                )
            if course.training_date_start:
                description_lines.append(
                    'Start Date: %s' % course.training_date_start
                )
            if course.training_date_end:
                description_lines.append(
                    'Delivery Date: %s' % course.training_date_end
                )
            if course.location:
                description_lines.append(
                    'Location: %s' % course.location
                )
            if course.where_location2:
                description_lines.append(
                    'Where: %s' % course.where_location2
                )
            if course.descriptions:
                description_lines.append(
                    'Description: %s' % course.descriptions
                )

            purchase_lines.append((0, 0, {
                'product_id': product.id,
                'name': '\n'.join(description_lines),
                'product_qty': 1,
                'product_uom': (
                    product.uom_po_id.id
                    or product.uom_id.id
                ),
                'price_unit': course.price,
                'date_planned': fields.Datetime.now(),
            }))

        return {
            'type': 'ir.actions.act_window',
            'name': _('New PO'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_crm_lead_id': self.id,
                'default_origin': self.name,
                'default_partner_id': (
                    self.partner_id.id
                    or self.ordering_partner_id.id
                    or False
                ),
                'default_currency_id': self.currency_id.id or False,
                'default_is_training_order': True,
                'default_po_training_type': 'training_vendor',
                'default_payment_method': 'cash',
                'default_training_course_ids': [(6, 0, cash_courses.ids)],
                'default_order_line': purchase_lines,
                'default_instructor_id': self.instructor_id.id or False,
                'default_descriptions': self.descriptions,
                'default_training_id': self.training_id.id or False,
                'default_start_date': self.start_date,
                'default_end_date': self.to_date,
                'default_po_reference': self.poref,
                'default_tr_expiry_date': self.tr_expiry_date,
            },
        }

    def action_new_instructor_purchase_order(self):
        """
        Open a Purchase Order dedicated to buying instructor time.

        This is intentionally independent from Cash/CLC. Instructor time can
        be purchased for either payment method.

        If the Lead has exactly one training line, preload it. If it has more
        than one, the user chooses the relevant training line on the PO.
        """
        self.ensure_one()

        courses = self.training_course_ids
        if not courses:
            raise UserError(_('Add at least one Training line before creating an Instructor PO.'))

        default_course = courses if len(courses) == 1 else self.env['training.course']
        instructor = default_course.instructor_id if default_course else self.instructor_id

        return {
            'type': 'ir.actions.act_window',
            'name': _('New Instructor PO'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_crm_lead_id': self.id,
                'default_origin': self.name,
                'default_currency_id': self.currency_id.id or False,
                'default_is_training_order': True,
                'default_po_training_type': 'instructor',
                'default_instructor_training_course_id': default_course.id or False,
                'default_instructor_id': instructor.id or False,
                'default_instructor_from': default_course.training_date_start or False,
                'default_instructor_to': default_course.training_date_end or False,
                # Vendor is intentionally left for the user to choose.
                # The instructor's HR contact is not always the payable vendor.
                'default_partner_id': False,
            },
        }

    def action_view_purchase_orders(self):
        """Show all purchase orders linked to this opportunity."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('crm_lead_id', '=', self.id)],
            'context': {
                'default_crm_lead_id': self.id,
                'default_partner_id': (
                    self.partner_id.id
                    or self.ordering_partner_id.id
                    or False
                ),
            },
        }

    def action_create_cost_line(self):
        """ Automatically create a new cost line when called """
        for lead in self:
            self.env['cost.details'].create({
                'cos_lead_id': lead.id,
                'name': 'New Cost Line',
                'currency_id': lead.env.company.currency_id.id,
                'training_vendor': 0.0,
                'total_price_all': 0.0,
                'clc_cost': 0.0,
                'rate_card': 0.0,
                'nilme_share': 0.0,
                'learning_partner': lead.learnig_partner,  # Include the learning_partner field
                'price': 0.0,  # Set a default value for the mandatory price field
            })

    @api.depends('ticket_ids.price', 'hotel_ids.price', 'cost_details_ids.price', 'instructor_logistics', 'venue', 'ctrng', 'uber')
    def _compute_total(self):
        for rec in self:
            ticket_total = sum(ticket.price for ticket in rec.ticket_ids) if rec.ticket_ids else 0
            hotel_total = sum(hotel.price for hotel in rec.hotel_ids) if rec.hotel_ids else 0
            cost_details_total = sum(cost.price for cost in rec.cost_details_ids) if rec.cost_details_ids else 0
            instructor_logistics = float(rec.instructor_logistics) if rec.instructor_logistics else 0
            venue = rec.venue if rec.venue else 0
            uber = rec.uber if rec.uber else 0
            ctrng = rec.ctrng if rec.ctrng else 0

            rec.total_price_all = ticket_total + hotel_total + cost_details_total + instructor_logistics + venue + uber + ctrng

    @api.depends('pro_service_ids.price')
    def _compute_service_price(self):
        for rec in self:
            if rec.pro_service_ids:
                rec.total_service_price = sum(rec.pro_service_ids.mapped('price'))
            else:
                rec.total_service_price = 0

    def _prepare_opportunity_quotation_context(self):
        quotation_context = super()._prepare_opportunity_quotation_context()
        quotation_context.update({
            'default_training_name': self.training_name,
            'default_training_course_ids': [(6, 0, self.training_course_ids.ids)],
            'default_pro_service_ids': [(6, 0, self.pro_service_ids.ids)],
            'default_cos_details_ids': [(6, 0, self.cost_details_ids.ids)],
            'default_clcs_qty': self.clcs_qty,
            'default_so_no': self.so_no,
            'default_tr_expiry_date': self.tr_expiry_date,
            'default_instructor_logistics': self.instructor_logistics,
            'default_ctrng': self.ctrng,
            'default_descriptions': self.descriptions,
            'default_ordering_partner': self.ordering_partner_id.id,
            'default_instructor_id': self.instructor_id.id,
            'default_training_id': self.training_id.id,
            'default_location': self.location,
            'default_learnig_partner': self.learnig_partner,
            'default_uber': self.uber,
            'default_payment_method': self.payment_method,
            'default_clcs_qty': self.clcs_qty,
            'default_cost_details_ids': [(6, 0, self.cost_details_ids.ids)],  # Pass related Cost Details
            'default_poref': self.poref,
            'default_invref': self.invref,
            'default_uber' : self.uber,
            'default_ins_time': self.ins_time,
            # Add ticket and hotel details
            'default_ticket_ids': [(6, 0, self.ticket_ids.ids)],
            'default_hotel_ids': [(6, 0, self.hotel_ids.ids)],
        })
        return quotation_context

    def action_new_training_so(self):
        """
        Open a new quotation from the Training Lead, but assign the SO
        salesperson to the user who clicks the New SO button.

        When this SO is later invoiced, SaleOrder._prepare_invoice below
        restores the invoice salesperson from the original CRM Lead.
        """
        self.ensure_one()

        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_crm.sale_action_quotations_new"
        )

        quotation_context = self._prepare_opportunity_quotation_context()
        quotation_context.update({
            'default_user_id': self.env.user.id,
            'default_is_training_so': True,
            'search_default_opportunity_id': self.id,
        })

        action['context'] = quotation_context
        return action


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_training_so = fields.Boolean(
        string='Training SO',
        default=False,
        copy=False
    )

    def _prepare_invoice(self):
        """
        For SOs created from the special New SO button:
        - SO Salesperson = user who created the SO.
        - Customer Invoice Salesperson = salesperson on the original CRM Lead.

        Normal quotations/SOs keep Odoo's standard behavior.
        """
        self.ensure_one()
        invoice_vals = super()._prepare_invoice()

        if (
            self.is_training_so
            and self.opportunity_id
            and self.opportunity_id.user_id
        ):
            lead_salesperson_id = self.opportunity_id.user_id.id
            invoice_vals.update({
                'invoice_user_id': lead_salesperson_id,
                'user_id': lead_salesperson_id,
            })

        return invoice_vals


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_training_order = fields.Boolean(
        string='Is Training Order'
    )

    po_training_type = fields.Selection(
        [
            ('training_vendor', 'Training Vendor'),
            ('instructor', 'Instructor'),
        ],
        string='Training PO Type',
        default='training_vendor',
        required=True
    )

    instructor_training_course_id = fields.Many2one(
        'training.course',
        string='Training',
        copy=False,
        ondelete='set null'
    )
    instructor_id = fields.Many2one(
        'hr.employee',
        string='Instructor'
    )
    instructor_from = fields.Date(
        string='Instructor From'
    )
    instructor_to = fields.Date(
        string='Instructor To'
    )
    instructor_days = fields.Integer(
        string='No. of Days',
        compute='_compute_instructor_fee',
        store=True
    )
    instructor_daily_rate = fields.Monetary(
        string='Daily Rate',
        currency_field='currency_id'
    )
    instructor_total = fields.Monetary(
        string='Instructor Total',
        compute='_compute_instructor_fee',
        store=True,
        currency_field='currency_id'
    )

    training_course_ids = fields.One2many(
        'training.course',
        'purchase_order_id',
        string='Training Courses'
    )

    term_and_cond = fields.Html(
        string='Terms and Conditions'
    )

    total_training_price = fields.Monetary(
        string='Total Training Price',
        compute='_compute_po_training_price',
        store=True
    )

    display_training_table = fields.Boolean(
        string='Display Training Table'
    )
    display_signature = fields.Boolean(
        string='Display Signature'
    )
    display_stamp = fields.Boolean(
        string='Display Stamp'
    )
    display_instructor = fields.Boolean(
        string='Display Instructor'
    )
    display_location = fields.Boolean(
        string='Display Location'
    )
    display_total = fields.Boolean(
        string='Display Total Amount'
    )
    display_where = fields.Boolean(
        string='Display Where?'
    )
    display_description = fields.Boolean(
        string='Display Description'
    )

    crm_lead_id = fields.Many2one(
        'crm.lead',
        string='CRM Opportunity',
        index=True,
        copy=False,
        ondelete='set null'
    )

    end_customer_id = fields.Many2one(
        'res.partner',
        string='End Customer',
        related='crm_lead_id.training_name',
        store=True,
        readonly=True
    )

    @api.depends('instructor_from', 'instructor_to', 'instructor_daily_rate')
    def _compute_instructor_fee(self):
        for order in self:
            days = 0
            if order.instructor_from and order.instructor_to:
                delta = (order.instructor_to - order.instructor_from).days + 1
                days = max(delta, 0)
            order.instructor_days = days
            order.instructor_total = days * (order.instructor_daily_rate or 0.0)

    @api.onchange('instructor_training_course_id')
    def _onchange_instructor_training_course_id(self):
        for order in self:
            course = order.instructor_training_course_id
            if not course:
                continue
            order.instructor_id = course.instructor_id
            order.instructor_from = course.training_date_start
            order.instructor_to = course.training_date_end

    @api.constrains('instructor_from', 'instructor_to', 'po_training_type')
    def _check_instructor_dates(self):
        for order in self:
            if (
                order.po_training_type == 'instructor'
                and order.instructor_from
                and order.instructor_to
                and order.instructor_to < order.instructor_from
            ):
                raise UserError(_('Instructor To date cannot be before Instructor From date.'))

    def _prepare_instructor_fee_line_vals(self):
        self.ensure_one()
        course = self.instructor_training_course_id
        product = course.training_id if course else False

        if not product or not self.instructor_days:
            return False

        description = ['Instructor Fee']
        description.append('Training: %s' % (product.display_name or course.name or ''))
        if self.instructor_id:
            description.append('Instructor: %s' % self.instructor_id.name)
        if self.instructor_from:
            description.append('From: %s' % self.instructor_from)
        if self.instructor_to:
            description.append('To: %s' % self.instructor_to)
        description.append('Days: %s' % self.instructor_days)

        return {
            'product_id': product.id,
            'name': '\\n'.join(description),
            'product_qty': self.instructor_days,
            'product_uom': product.uom_po_id.id or product.uom_id.id,
            'price_unit': self.instructor_daily_rate or 0.0,
            'date_planned': fields.Datetime.now(),
            'is_instructor_fee_line': True,
        }

    def _sync_instructor_fee_line(self):
        """
        Keep one accounting PO line equal to:
            quantity = instructor days
            unit price = daily rate

        This is the amount that later flows to the Vendor Bill.
        """
        PurchaseLine = self.env['purchase.order.line']

        for order in self:
            fee_lines = order.order_line.filtered(
                lambda line: line.is_instructor_fee_line
            )

            if order.po_training_type != 'instructor':
                if fee_lines:
                    fee_lines.unlink()
                continue

            vals = order._prepare_instructor_fee_line_vals()
            if not vals:
                continue

            if fee_lines:
                fee_lines[0].write(vals)
                if len(fee_lines) > 1:
                    fee_lines[1:].unlink()
            else:
                vals['order_id'] = order.id
                PurchaseLine.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._sync_instructor_fee_line()
        return orders

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get('skip_instructor_fee_sync'):
            relevant = {
                'po_training_type',
                'instructor_training_course_id',
                'instructor_id',
                'instructor_from',
                'instructor_to',
                'instructor_daily_rate',
            }
            if relevant.intersection(vals):
                self.with_context(skip_instructor_fee_sync=True)._sync_instructor_fee_line()
        return result

    @api.depends('training_course_ids.price')
    def _compute_po_training_price(self):
        for order in self:
            order.total_training_price = sum(
                order.training_course_ids.mapped('price')
            )

    def _prepare_invoice(self):
        """
        Carry all training/instructor details from the PO to its Vendor Bill.

        Training Vendor PO:
        - Copy every PO training row to independent account.move training rows.

        Instructor PO:
        - Copy the selected training as one independent bill training row.
        - Copy instructor dates, days, daily rate and total.
        """
        self.ensure_one()
        invoice_vals = super()._prepare_invoice()

        training_lines = []

        if self.po_training_type == 'instructor':
            course = self.instructor_training_course_id
            if course:
                training_lines.append((0, 0, {
                    'name': course.name,
                    'no_of_student': 0,
                    'duration': (
                        '%s days' % self.instructor_days
                        if self.instructor_days else course.duration
                    ),
                    'training_date_start': self.instructor_from or course.training_date_start,
                    'training_date_end': self.instructor_to or course.training_date_end,
                    # For the Vendor Bill's internal training details, this is
                    # the payable instructor total, not the customer selling price.
                    'price': self.instructor_total,
                    'lead_id': course.lead_id.id or self.crm_lead_id.id or False,
                    'instructor_id': self.instructor_id.id or course.instructor_id.id or False,
                    'descriptions': course.descriptions,
                    'training_id': course.training_id.id or False,
                    'poref': course.poref,
                    'invref': course.invref,
                    'tr_expiry_date': course.tr_expiry_date,
                    'where_location2': course.where_location2,
                    'location': course.location,
                    'payment_method': course.payment_method,
                    'clcs_qty': course.clcs_qty,
                }))
        else:
            for training in self.training_course_ids:
                training_lines.append((0, 0, {
                    'name': training.name,
                    'no_of_student': training.no_of_student,
                    'duration': training.duration,
                    'training_date_start': training.training_date_start,
                    'training_date_end': training.training_date_end,
                    'price': training.price,
                    'lead_id': training.lead_id.id or self.crm_lead_id.id or False,
                    'instructor_id': training.instructor_id.id or False,
                    'descriptions': training.descriptions,
                    'training_id': training.training_id.id or False,
                    'poref': training.poref,
                    'invref': training.invref,
                    'tr_expiry_date': training.tr_expiry_date,
                    'where_location2': training.where_location2,
                    'location': training.location,
                    'payment_method': training.payment_method,
                    'clcs_qty': training.clcs_qty,
                }))

        invoice_vals.update({
            'crm_lead_id': self.crm_lead_id.id or False,
            'source_purchase_order_id': self.id,
            'purchase_training_type': self.po_training_type,
            'training_course_ids': training_lines,
            'term_and_cond': self.term_and_cond,
            'display_training_table': self.display_training_table,
            'display_signature': self.display_signature,
            'display_stamp': self.display_stamp,
            'display_instructor': self.display_instructor,
            'display_location': self.display_location,
            'display_total': self.display_total,
            'display_where': self.display_where,
            'display_description': self.display_description,
            'instructor_training_course_id': self.instructor_training_course_id.id or False,
            'instructor_id': self.instructor_id.id or False,
            'instructor_from': self.instructor_from,
            'instructor_to': self.instructor_to,
            'instructor_days': self.instructor_days,
            'instructor_daily_rate': self.instructor_daily_rate,
            'instructor_total': self.instructor_total,
        })

        return invoice_vals



class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    is_instructor_fee_line = fields.Boolean(
        string='Instructor Fee Line',
        default=False,
        copy=False,
        index=True
    )

class HotelHotel(models.Model):
    _name = 'hotel.hotel'
    _description='Hotels'
    
    hotel_lead_id = fields.Many2one('crm.lead',string="Lead")
    hotel_order_id = fields.Many2one('sale.order',string="Order")
    hotel_id = fields.Many2one('hotel.description',string="Hotel")
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    nights = fields.Char(string="Nights",compute='_compute_nights')
    location = fields.Char(string="Location")
    pax = fields.Char(string="PAX")
    des = fields.Char(string="Description")
    room_type = fields.Char(string="Room Type")
    currency_id = fields.Many2one('res.currency',string="Currency",required=True)
    price_without_tax = fields.Monetary(string="Price",required=True,default=0.0)
    tax = fields.Monetary(string="Taxes",required=True,default=0.0)
    price = fields.Monetary(string="Price with Tax",compute='_compute_total',inverse='_inverse_total')
    
    @api.constrains('hotel_lead_id', 'lcp_training_course_id')
    def _check_hotel_row_limit(self):
        # The two-row restriction is per training, not per opportunity.
        # A Lead with several On-site trainings needs separate hotel rows.
        for lead in self.mapped('hotel_lead_id'):
            hotels = self.search([('hotel_lead_id', '=', lead.id)])
            by_training = {}
            for hotel in hotels:
                course_id = hotel.lcp_training_course_id.id or False
                by_training[course_id] = by_training.get(course_id, 0) + 1
            if any(count > 2 for count in by_training.values()):
                raise UserError(_('Only two hotel rows are allowed per Training.'))

    @api.depends('price_without_tax', 'tax')
    def _compute_total(self):
        for rec in self:
            rec.price = rec.price_without_tax + rec.tax

    def _inverse_total(self):
        # Preserve existing tax amounts and the total consumed by LCP.
        for rec in self:
            rec.price_without_tax = rec.price - rec.tax

    @api.depends('date_from', 'date_to')
    def _compute_nights(self):
        for rec in self:
            rec.nights = str(max((rec.date_to - rec.date_from).days, 0)) if rec.date_from and rec.date_to else '0'
class TicketTicket(models.Model):
    _name = 'ticket.ticket'
    _description='Tickets'   
    
    ticket_lead_id = fields.Many2one('crm.lead',string="Lead")
    ticket_order_id = fields.Many2one('sale.order',string="Order")
    airline_id = fields.Many2one('airline.airline',string="Airlines")
    origin_id = fields.Many2one('loca.loca',string="Origin")
    destination_id = fields.Many2one('loca.loca',string="Destination")
    date = fields.Date(string="Date")
    duration = fields.Char(string="Duration")
    time_from = fields.Float(string="Availabe Time From")
    time_to = fields.Float(string="Availabe Time To")
    stop = fields.Char(string="Stop")
    class_type_id = fields.Many2one('flight.class.type',string="Class Type")
    currency_id = fields.Many2one('res.currency',string="Currency",required=True)
    price = fields.Monetary(string="Price with Taxes",required=True)
    
    @api.constrains('ticket_lead_id', 'lcp_training_course_id')
    def _check_ticket_row_limit(self):
        # Each On-site course may have its own outbound/return ticket rows.
        for lead in self.mapped('ticket_lead_id'):
            flights = self.search([('ticket_lead_id', '=', lead.id)])
            by_training = {}
            for ticket in flights:
                course_id = ticket.lcp_training_course_id.id or False
                by_training[course_id] = by_training.get(course_id, 0) + 1
            if any(count > 2 for count in by_training.values()):
                raise UserError(_('Only two flight rows are allowed per Training.'))

class AirlineAirline(models.Model):
    _name = 'airline.airline'
    _description= 'Airlines'
    
    name = fields.Char(string="Airline",required=True)
    
class LocaLoca(models.Model):
    _name = 'loca.loca'
    _description= 'Locations'
    
    name = fields.Char(string="Location",required=True)

class FlightClassType(models.Model):
    _name = 'flight.class.type'
    _description= 'Classes'
    
    name = fields.Char(string="Class Type",required=True)
    
    
class HotelDescription(models.Model):
    _name = 'hotel.description'
    _description= 'Hotel Description'
    
    name = fields.Char(string="Hotel",required=True)
    
class ProductProduct(models.Model):
    _inherit = 'product.product'

    
    cost_clc = fields.Char(string="CLCs Cost")
    hyperlink = fields.Char(string="Hyper Link")
    
    
class ProductProduct(models.Model):
    _inherit = 'product.template'

    
    cost_clc = fields.Char(string="CLCs Cost")
    hyperlink = fields.Char(string="Hyper Link")

