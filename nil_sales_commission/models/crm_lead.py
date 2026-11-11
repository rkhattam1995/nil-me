from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    commission_ids = fields.One2many(
        'nil.sales.commission',
        'lead_id',
        string='Sales Commissions',
        groups='nil_sales_commission.group_nil_commission_manager',
    )

    commission_count = fields.Integer(
        string='Commission Count',
        compute='_compute_commission_count',
        compute_sudo=True,
        groups='nil_sales_commission.group_nil_commission_manager',
    )

    def _compute_commission_count(self):
        Commission = self.env['nil.sales.commission'].sudo()

        for lead in self:
            lead.commission_count = Commission.search_count([
                ('lead_id', '=', lead.id),
                ('auto_key', '!=', 'ruba'),
                ('is_auto_ruba', '=', False),
                '|',
                ('salesperson_id', '=', False),
                ('salesperson_id.name', 'not ilike', 'Ruba Khattam'),
            ])

    @api.model_create_multi
    def create(self, vals_list):

        leads = super().create(vals_list)

        leads._nil_sync_invoice_commissions_from_lead()

        return leads

    def write(self, vals):

        result = super().write(vals)

        # Any Lead edit refreshes all related pending commission rows.
        self._nil_sync_invoice_commissions_from_lead()

        return result

    def _nil_get_related_commission_invoices(self):
        """
        Find every invoice related to these CRM Leads.

        Sources:
        1. Sale Orders where opportunity_id = this Lead.
        2. Standard Sale Order invoice_ids relation.
        3. invoice_origin matching the Sale Order number.
        4. Existing commission rows already linked to the Lead.
        """
        if not self:
            return self.env['account.move']

        SaleOrder = self.env[
            'sale.order'
        ].sudo()

        AccountMove = self.env[
            'account.move'
        ].sudo()

        Commission = self.env[
            'nil.sales.commission'
        ].sudo()

        sale_orders = SaleOrder.search([
            ('opportunity_id', 'in', self.ids),
        ])

        invoices = sale_orders.mapped(
            'invoice_ids'
        )

        # Fallback for older/custom invoices that have invoice_origin
        # but no invoice_line -> sale_line relation.
        for order in sale_orders:

            invoices |= AccountMove.search([
                ('move_type', '=', 'out_invoice'),
                ('invoice_origin', 'ilike', order.name),
            ])

        existing_commissions = Commission.search([
            ('lead_id', 'in', self.ids),
            ('invoice_id', '!=', False),
        ])

        invoices |= existing_commissions.mapped(
            'invoice_id'
        )

        return invoices

    def _nil_sync_invoice_commissions_from_lead(self):
        """
        Refresh commission rows using CURRENT Lead values.

        Invoice stays fixed:
        - invoice number
        - invoice date
        - invoice untaxed value
        - currency

        Lead stays dynamic:
        - salesperson
        - customer
        - commission rate
        - commission amount

        Rates:
        - Ruba Khattam = 1%
        - Loudy Abdo = 5%
        - Baraa Abo Saleh = 2%
        """
        invoices = (
            self._nil_get_related_commission_invoices()
        )

        if invoices:
            invoices._nil_sync_sales_commission()

        return True

    def action_view_sales_commission(self):

        self.ensure_one()

        action = self.env[
            'ir.actions.actions'
        ]._for_xml_id(
            'nil_sales_commission.action_sales_commission'
        )

        action['domain'] = [
            ('lead_id', '=', self.id),
            ('auto_key', '!=', 'ruba'),
            ('is_auto_ruba', '=', False),
            '|',
            ('salesperson_id', '=', False),
            ('salesperson_id.name', 'not ilike', 'Ruba Khattam')
        ]

        action['context'] = {
            'default_lead_id':
                self.id,

            'default_salesperson_id':
                self.user_id.id
                if self.user_id
                else False,

            'default_customer_id':
                self.partner_id.id
                if self.partner_id
                else False,
        }

        commissions = self.commission_ids.filtered(
            lambda row: (
                row.auto_key != 'ruba'
                and not row.is_auto_ruba
                and self.env['nil.sales.commission']._nil_normalize_name(
                    row.salesperson_id.name
                ) != 'ruba khattam'
            )
        )

        if len(commissions) == 1:

            action['views'] = [
                (False, 'form')
            ]

            action['res_id'] = (
                commissions.id
            )

        return action
