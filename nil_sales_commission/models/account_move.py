from datetime import date

from odoo import api, fields, models


COMMISSION_CUTOFF_DATE = date(2026, 5, 31)


class AccountMove(models.Model):
    _inherit = 'account.move'

    exclude_from_commission = fields.Boolean(
        string='Exclude from Commission',
        default=False,
        copy=False,
    )

    def _nil_get_commission_sale_orders(self):
        self.ensure_one()

        invoice = self.sudo()
        invoice_company = invoice.company_id.sudo()

        # IMPORTANT:
        # Search only inside the SAME company as the invoice.
        # This prevents an invoice from NIL ME UAE from accidentally finding
        # an S00xxx Sale Order with the same number in NIL ME Saudi, and vice
        # versa.
        SaleOrder = (
            self.env['sale.order']
            .sudo()
            .with_context(
                allowed_company_ids=[invoice_company.id],
            )
        )

        sale_lines = invoice.invoice_line_ids.sudo().mapped(
            'sale_line_ids'
        ).sudo()

        order_ids = sale_lines.mapped(
            'order_id'
        ).filtered(
            lambda order:
                order.company_id.id == invoice_company.id
        ).ids

        orders = SaleOrder.browse(
            order_ids
        ).sudo()

        origin = (
            invoice.invoice_origin
            or ''
        ).strip()

        if origin:
            origin_names = [
                value.strip()
                for value in origin.split(',')
                if value.strip()
            ]

            if origin_names:
                orders |= SaleOrder.search([
                    ('company_id', '=', invoice_company.id),
                    ('name', 'in', origin_names),
                ])

            if not orders:
                orders |= SaleOrder.search([
                    ('company_id', '=', invoice_company.id),
                    ('name', '=', origin),
                ])

        return orders.sudo()

    def _nil_get_commission_lead(self):
        """
        Best-effort invoice -> Sale Order -> CRM Lead relation.
        The Lead relation never controls whether the invoice appears.
        """
        self.ensure_one()

        leads = self._nil_get_commission_sale_orders().sudo().mapped(
            'opportunity_id'
        ).sudo()

        if leads:
            return leads[:1]

        existing_commission = self.env[
            'nil.sales.commission'
        ].sudo().search([
            ('invoice_id', '=', self.id),
            ('lead_id', '!=', False),
        ], limit=1)

        if existing_commission:
            return existing_commission.lead_id

        return self.env['crm.lead']

    def _nil_get_deal_salesperson(self):
        """
        Salesperson used ONLY to determine the fixed Loudy/Baraa commission.

        Priority:
        1. Current salesperson on CRM Lead
        2. Invoice Salesperson
        3. Sale Order Salesperson
        """
        self.ensure_one()

        invoice = self.sudo()
        lead = invoice._nil_get_commission_lead().sudo()

        if lead and lead.user_id:
            return lead.user_id.sudo()

        if invoice.invoice_user_id:
            return invoice.invoice_user_id.sudo()

        orders = invoice._nil_get_commission_sale_orders().sudo()

        if orders and orders[0].user_id:
            return orders[0].user_id.sudo()

        return self.env['res.users']

    def _nil_sync_sales_commission(self):
        """
        FINAL COMMISSION LOGIC

        Every Customer Invoice dated from 01-Jun-2026 onward:
        1. Ruba Khattam ALWAYS gets 1%.
        2. If deal salesperson is Loudy Abdo, Loudy gets 5%.
        3. If deal salesperson is Baraa Abo Saleh, Baraa gets 2%.
        4. No salesperson filter controls whether the invoice appears.
        5. Commission basis = CRM Lead Total Training Price, NOT invoice value.
        6. Manual commission rows are preserved.
        7. Automatic rows are unique per invoice/type, so repeated backfills
           do not create duplicates.
        """
        all_company_ids = self.env[
            'res.company'
        ].sudo().search([]).ids

        Commission = (
            self.env['nil.sales.commission']
            .sudo()
            .with_context(
                allowed_company_ids=all_company_ids,
            )
        )

        ruba_user = Commission._nil_get_ruba_user()

        for invoice_record in self:
            # All internal commission lookups are cross-company-safe.
            invoice = invoice_record.sudo()

            if invoice.move_type != 'out_invoice':
                continue

            if not invoice.invoice_date:
                continue

            if invoice.invoice_date <= COMMISSION_CUTOFF_DATE:
                continue

            lead = invoice._nil_get_commission_lead()
            deal_salesperson = invoice._nil_get_deal_salesperson()

            training_value = float(
                lead.total_training_price or 0.0
            ) if lead else 0.0

            common_values = {
                'invoice_id': invoice.id,
                'lead_id': lead.id if lead else False,
                'customer_id': (
                    lead.partner_id.id
                    if lead and lead.partner_id
                    else invoice.partner_id.id
                    if invoice.partner_id
                    else False
                ),
                'company_id': invoice.company_id.id,
                'currency_id': (
                    lead.currency_id.id
                    if lead and lead.currency_id
                    else invoice.currency_id.id
                ),
                'training_value': training_value,
                'commission_date': invoice.invoice_date,
            }

            # -------------------------------------------------------------
            # 1) RUBA: ONE automatic 1% row per invoice
            # -------------------------------------------------------------
            auto_ruba = Commission.search([
                ('invoice_id', '=', invoice.id),
                ('auto_key', '=', 'ruba'),
            ], limit=1)

            if not auto_ruba and ruba_user:
                # Adopt an older automatic Ruba row instead of creating a duplicate.
                old_ruba = Commission.search([
                    ('invoice_id', '=', invoice.id),
                    ('auto_key', '=', False),
                    ('salesperson_id', '=', ruba_user.id),
                    ('is_auto_ruba', '=', True),
                ], order='id asc', limit=1)

                if old_ruba:
                    old_ruba.with_context(
                        nil_auto_sync=True,
                        nil_skip_paid_lock=True,
                    ).write({
                        'auto_key': 'ruba',
                        'is_auto_ruba': True,
                    })
                    auto_ruba = old_ruba

            if not auto_ruba:
                ruba_values = dict(common_values)
                ruba_values.update({
                    'salesperson_id': (
                        ruba_user.id
                        if ruba_user
                        else False
                    ),
                    'commission_rate': 1.0,
                    'commission_amount': (
                        training_value * 0.01
                    ),
                    'state': (
                        'excluded'
                        if invoice.exclude_from_commission
                        else 'draft'
                    ),
                    'excluded_by_invoice':
                        bool(invoice.exclude_from_commission),
                    'auto_key': 'ruba',
                    'is_auto_ruba': True,
                })

                auto_ruba = Commission.with_context(
                    nil_auto_sync=True
                ).create(ruba_values)

            elif auto_ruba.state != 'paid':
                ruba_values = dict(common_values)
                ruba_values.update({
                    'salesperson_id': (
                        ruba_user.id
                        if ruba_user
                        else auto_ruba.salesperson_id.id
                    ),
                    'commission_rate': 1.0,
                    'is_auto_ruba': True,
                    'auto_key': 'ruba',
                })

                if invoice.exclude_from_commission:
                    ruba_values.update({
                        'state': 'excluded',
                        'excluded_by_invoice': True,
                    })
                elif auto_ruba.excluded_by_invoice:
                    ruba_values.update({
                        'state': 'draft',
                        'excluded_by_invoice': False,
                    })

                auto_ruba.with_context(
                    nil_auto_sync=True
                ).write(ruba_values)

            # -------------------------------------------------------------
            # 2) LOUDY / BARAA: ONE fixed salesperson row per invoice
            # -------------------------------------------------------------
            fixed_rate = (
                Commission._nil_get_fixed_salesperson_rate(
                    deal_salesperson
                )
            )

            auto_sales = Commission.search([
                ('invoice_id', '=', invoice.id),
                ('auto_key', '=', 'salesperson'),
            ], limit=1)

            if fixed_rate > 0.0 and deal_salesperson:
                if not auto_sales:
                    # Adopt an older exact matching row rather than duplicate it.
                    old_sales = Commission.search([
                        ('invoice_id', '=', invoice.id),
                        ('auto_key', '=', False),
                        ('is_auto_ruba', '=', False),
                        ('salesperson_id', '=', deal_salesperson.id),
                        ('commission_rate', '=', fixed_rate),
                    ], order='id asc', limit=1)

                    if old_sales:
                        old_sales.with_context(
                            nil_auto_sync=True,
                            nil_skip_paid_lock=True,
                        ).write({
                            'auto_key': 'salesperson',
                        })
                        auto_sales = old_sales

                if not auto_sales:
                    sales_values = dict(common_values)
                    sales_values.update({
                        'salesperson_id':
                            deal_salesperson.id,
                        'commission_rate':
                            fixed_rate,
                        'commission_amount': (
                            training_value
                            * (fixed_rate / 100.0)
                        ),
                        'state': (
                            'excluded'
                            if invoice.exclude_from_commission
                            else 'draft'
                        ),
                        'excluded_by_invoice':
                            bool(invoice.exclude_from_commission),
                        'auto_key': 'salesperson',
                        'is_auto_ruba': False,
                    })

                    auto_sales = Commission.with_context(
                        nil_auto_sync=True
                    ).create(sales_values)

                elif auto_sales.state != 'paid':
                    salesperson_changed = (
                        auto_sales.salesperson_id.id
                        != deal_salesperson.id
                    )

                    sales_values = dict(common_values)
                    sales_values.update({
                        'salesperson_id':
                            deal_salesperson.id,
                        'commission_rate':
                            fixed_rate,
                        'auto_key':
                            'salesperson',
                    })

                    if invoice.exclude_from_commission:
                        sales_values.update({
                            'state': 'excluded',
                            'excluded_by_invoice': True,
                        })
                    elif auto_sales.excluded_by_invoice:
                        sales_values.update({
                            'state': 'draft',
                            'excluded_by_invoice': False,
                        })
                    elif (
                        salesperson_changed
                        and auto_sales.state == 'excluded'
                    ):
                        # A different fixed salesperson is now responsible.
                        sales_values['state'] = 'draft'

                    auto_sales.with_context(
                        nil_auto_sync=True
                    ).write(sales_values)

            else:
                # Current deal salesperson is not Loudy/Baraa.
                # Remove only NON-PAID automatic salesperson rows.
                # Manual rows are never touched.
                if auto_sales and auto_sales.state != 'paid':
                    auto_sales.with_context(
                        nil_sync_cleanup=True
                    ).unlink()

            # -------------------------------------------------------------
            # 3) MANUAL rows: update reference/value only, never recipient,
            #    rate, status or accounting decision.
            # -------------------------------------------------------------
            manual_rows = Commission.search([
                ('invoice_id', '=', invoice.id),
                ('auto_key', '=', False),
                ('state', '!=', 'paid'),
            ])

            if manual_rows:
                manual_rows.with_context(
                    nil_auto_sync=True
                ).write(common_values)

        return True

    @api.model
    def _nil_backfill_sales_commissions(self):
        """
        Backfill ALL Customer Invoices from 01-Jun-2026 onward.

        This does not filter invoices by salesperson.
        """
        all_company_ids = self.env[
            'res.company'
        ].sudo().search([]).ids

        Commission = (
            self.env['nil.sales.commission']
            .sudo()
            .with_context(
                allowed_company_ids=all_company_ids,
            )
        )

        Commission._nil_prepare_invoice_commission_migration()

        # Clean old duplicates before replaying any invoice sync.
        # This only archives commission rows, never accounting invoices.
        Commission._nil_deduplicate_invoice_commissions()

        # Explicitly run the backfill across ALL companies/branches,
        # including Saudi, regardless of which company is currently active
        # in the Odoo company selector.
        Move = (
            self.env['account.move']
            .sudo()
            .with_context(
                allowed_company_ids=all_company_ids,
            )
        )

        invoices = Move.search([
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '>', COMMISSION_CUTOFF_DATE),
        ])

        invoices._nil_sync_sales_commission()
        # Final idempotent safety pass after syncing older invoices.
        Commission._nil_deduplicate_invoice_commissions()
        return True

    def action_post(self):
        result = super().action_post()
        self._nil_sync_sales_commission()
        return result

    def write(self, vals):
        result = super().write(vals)

        tracked_fields = {
            'state',
            'invoice_date',
            'invoice_user_id',
            'partner_id',
            'currency_id',
            'invoice_origin',
            'exclude_from_commission',
        }

        if tracked_fields.intersection(vals):
            self.filtered(
                lambda move:
                    move.move_type == 'out_invoice'
            )._nil_sync_sales_commission()

        return result

    def button_draft(self):
        result = super().button_draft()

        self.filtered(
            lambda move:
                move.move_type == 'out_invoice'
        )._nil_sync_sales_commission()

        return result

    def button_cancel(self):
        result = super().button_cancel()

        self.filtered(
            lambda move:
                move.move_type == 'out_invoice'
        )._nil_sync_sales_commission()

        return result
