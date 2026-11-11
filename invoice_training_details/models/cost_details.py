from odoo import models, fields, api


class CostDetails(models.Model):
    _name = 'cost.details'
    _description = 'Cost Details'

    cos_lead_id = fields.Many2one(
        'crm.lead',
        string="Lead",
        ondelete='cascade'
    )

    name = fields.Char(string="Cost Name")
    description = fields.Text(string="Description")
    price = fields.Float(string="Price")

    # Partner Share
    # Manual in all cases except:
    # CLC + EnterOne = 20% automatically after deducting:
    # Instructor + Hotel + Airfare
    training_vendor = fields.Float(
        string="Partner Share"
    )

    # Logistics Cost
    total_price_all = fields.Float(
        string="Logistics Cost",
        compute='_compute_total'
    )

    # Total Costs
    margin1 = fields.Float(
        string="Total Costs",
        compute='_compute_margin1'
    )

    # Partner Rate
    rate_card = fields.Float(
        string="Partner Rate"
    )

    # Instructor Cost
    ins_time = fields.Float(
        string="Instructor"
    )

    # NIL ME Share
    nilme_share = fields.Float(
        string="NIL ME Share $",
        compute='_compute_nilme_share'
    )

    # Learning Partner
    learning_partner = fields.Selection([
        ('Koenig', 'Koenig'),
        ('Mira', 'Mira'),
        ('EnterOne', 'EnterOne'),
        ('NIL LTD', 'NIL LTD'),
        ('NIL SA', 'NIL SA')
    ], string='Learning Partner')

    # Cost
    cost = fields.Float(
        string="Cost",
        compute='_compute_total'
    )

    # Margin %
    margin = fields.Float(
        string="Margin (%)",
        compute='_compute_margin'
    )

    # Sales Commission
    # 5% of FULL Training Value
    sales_commission = fields.Float(
        string="Sales Commission (5%)",
        compute='_compute_sales_commission'
    )

    # Helper only
    # Reads Payment Method from Training lines
    is_clc = fields.Boolean(
        string="Is CLC",
        compute='_compute_is_clc'
    )


    # =========================================================
    # PAYMENT METHOD CHECK
    # =========================================================

    @api.depends(
        'cos_lead_id.training_course_ids.payment_method'
    )
    def _compute_is_clc(self):

        for rec in self:

            if not rec.cos_lead_id:
                rec.is_clc = False
                continue

            methods = (
                rec.cos_lead_id
                .training_course_ids
                .mapped('payment_method')
            )

            rec.is_clc = bool(
                methods
                and all(
                    method == 'clc'
                    for method in methods
                )
            )


    # =========================================================
    # HELPERS
    # =========================================================

    def _get_ticket_total(self):

        self.ensure_one()

        if not self.cos_lead_id:
            return 0.0

        return sum(
            self.cos_lead_id.ticket_ids.mapped('price')
        )


    def _get_hotel_total(self):

        self.ensure_one()

        if not self.cos_lead_id:
            return 0.0

        return sum(
            self.cos_lead_id.hotel_ids.mapped('price')
        )


    def _get_uber_cost(self):

        self.ensure_one()

        if not self.cos_lead_id:
            return 0.0

        return float(
            self.cos_lead_id.uber or 0.0
        )


    def _get_clc_shared_costs(self):
        """
        CLC costs deducted BEFORE partner split:

        Instructor
        + Hotel
        + Airfare

        Uber is NOT included.
        Uber is deducted ONLY from NIL ME Share afterwards.
        """

        self.ensure_one()

        airfare = (
            self._get_ticket_total()
        )

        hotel = (
            self._get_hotel_total()
        )

        instructor = (
            self.ins_time or 0.0
        )

        return (
            airfare
            + hotel
            + instructor
        )


    def _get_cash_direct_costs(self):
        """
        Cash Costs =
            Logistics
            + Instructor
        """

        self.ensure_one()

        return (
            (self.total_price_all or 0.0)
            + (self.ins_time or 0.0)
        )


    def _is_enterone_clc(self):

        self.ensure_one()

        return (
            self.is_clc
            and self.learning_partner == 'EnterOne'
        )


    def _get_effective_partner_share(self):
        """
        CLC + EnterOne:

        Amount to Split =
            Total Training Price
            - Instructor
            - Hotel
            - Airfare

        EnterOne Share =
            20% of Amount to Split

        Uber is NOT included before the split.

        All other cases:
            Partner Share is manual.
        """

        self.ensure_one()

        # CLC + EnterOne
        if self._is_enterone_clc():

            total_training_price = (
                self.cos_lead_id.total_training_price
                or 0.0
            )

            shared_costs = (
                self._get_clc_shared_costs()
            )

            amount_to_split = (
                total_training_price
                - shared_costs
            )

            if amount_to_split > 0:

                return (
                    amount_to_split * 0.20
                )

            return 0.0

        # Cash or other partners
        return (
            self.training_vendor or 0.0
        )


    # =========================================================
    # LOGISTICS COST
    # =========================================================

    @api.depends(
        'cos_lead_id.ticket_ids.price',
        'cos_lead_id.hotel_ids.price',
        'cos_lead_id.cost_details_ids.price',
        'cos_lead_id.instructor_logistics',
        'cos_lead_id.venue',
        'cos_lead_id.ctrng',
        'cos_lead_id.uber',
        'ins_time'
    )
    def _compute_total(self):

        for rec in self:

            lead = rec.cos_lead_id

            if not lead:

                rec.total_price_all = 0.0
                rec.cost = 0.0

                continue

            ticket_total = sum(
                lead.ticket_ids.mapped('price')
            )

            hotel_total = sum(
                lead.hotel_ids.mapped('price')
            )

            cost_details_total = sum(
                lead.cost_details_ids.mapped('price')
            )

            instructor_logistics = float(
                lead.instructor_logistics or 0.0
            )

            venue = float(
                lead.venue or 0.0
            )

            catering = float(
                lead.ctrng or 0.0
            )

            uber = float(
                lead.uber or 0.0
            )

            total = (
                ticket_total
                + hotel_total
                + cost_details_total
                + instructor_logistics
                + venue
                + catering
                + uber
            )

            rec.total_price_all = total
            rec.cost = total


    # =========================================================
    # ENTERONE PARTNER SHARE
    # =========================================================

    @api.onchange(
        'learning_partner',
        'is_clc',
        'ins_time',
        'cos_lead_id.total_training_price'
    )
    def _onchange_enterone_partner_share(self):

        for rec in self:

            if rec._is_enterone_clc():

                total_training_price = (
                    rec.cos_lead_id.total_training_price
                    or 0.0
                )

                shared_costs = (
                    rec._get_clc_shared_costs()
                )

                amount_to_split = (
                    total_training_price
                    - shared_costs
                )

                if amount_to_split > 0:

                    rec.training_vendor = (
                        amount_to_split * 0.20
                    )

                else:

                    rec.training_vendor = 0.0


    # =========================================================
    # TOTAL COSTS
    # =========================================================

    @api.depends(
        'training_vendor',
        'total_price_all',
        'ins_time',
        'learning_partner',
        'is_clc',
        'cos_lead_id.total_training_price',
        'cos_lead_id.ticket_ids.price',
        'cos_lead_id.hotel_ids.price',
        'cos_lead_id.uber'
    )
    def _compute_margin1(self):

        for record in self:

            partner_share = (
                record._get_effective_partner_share()
            )

            # CLC
            if record.is_clc:

                shared_costs = (
                    record._get_clc_shared_costs()
                )

                uber = (
                    record._get_uber_cost()
                )

                record.margin1 = (
                    shared_costs
                    + partner_share
                    + uber
                )

            # Cash
            else:

                direct_costs = (
                    record._get_cash_direct_costs()
                )

                record.margin1 = (
                    direct_costs
                    + partner_share
                )


    # =========================================================
    # NIL ME SHARE
    # =========================================================

    @api.depends(
        'margin1',
        'training_vendor',
        'total_price_all',
        'ins_time',
        'learning_partner',
        'is_clc',
        'cos_lead_id.total_training_price',
        'cos_lead_id.ticket_ids.price',
        'cos_lead_id.hotel_ids.price',
        'cos_lead_id.uber'
    )
    def _compute_nilme_share(self):

        for record in self:

            total_training_price = (
                record.cos_lead_id.total_training_price
                or 0.0
            )

            # =================================================
            # CLC
            # =================================================

            if record.is_clc:

                shared_costs = (
                    record._get_clc_shared_costs()
                )

                uber = (
                    record._get_uber_cost()
                )

                amount_to_split = (
                    total_training_price
                    - shared_costs
                )

                # CLC + EnterOne
                if record.learning_partner == 'EnterOne':

                    if amount_to_split > 0:

                        record.nilme_share = (
                            (amount_to_split * 0.80)
                            - uber
                        )

                    else:

                        record.nilme_share = (
                            amount_to_split
                            - uber
                        )

                # CLC + Other Partner
                else:

                    record.nilme_share = (
                        amount_to_split
                        - (record.training_vendor or 0.0)
                        - uber
                    )

            # =================================================
            # CASH
            # =================================================

            else:

                record.nilme_share = (
                    total_training_price
                    - (record.margin1 or 0.0)
                )


    # =========================================================
    # MARGIN %
    # =========================================================

    @api.depends(
        'nilme_share',
        'cos_lead_id.total_training_price'
    )
    def _compute_margin(self):

        for record in self:

            total_training_price = (
                record.cos_lead_id.total_training_price
                or 0.0
            )

            if total_training_price:

                record.margin = (
                    (record.nilme_share or 0.0)
                    / total_training_price
                )

            else:

                record.margin = 0.0


    # =========================================================
    # SALES COMMISSION
    # =========================================================

    @api.depends(
        'cos_lead_id.total_training_price'
    )
    def _compute_sales_commission(self):

        for record in self:

            total_training_price = (
                record.cos_lead_id.total_training_price
                or 0.0
            )

            record.sales_commission = (
                total_training_price * 0.05
            )


    # =========================================================
    # QUOTATION CONTEXT
    # =========================================================

    def _prepare_opportunity_quotation_context(self):

        return {

            'default_cos_lead_id':
                self.cos_lead_id.id,

            'default_name':
                self.name,

            'default_description':
                self.description,

            'default_price':
                self.price,

            'default_training_vendor':
                self.training_vendor,

            'default_total_price_all':
                self.total_price_all,

            'default_margin1':
                self.margin1,

            'default_rate_card':
                self.rate_card,

            'default_ins_time':
                self.ins_time,

            'default_nilme_share':
                self.nilme_share,

            'default_learning_partner':
                self.learning_partner,

            'default_cost':
                self.cost,

            'default_margin':
                self.margin,

            'default_sales_commission':
                self.sales_commission,
        }
