# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Legacy fields kept only so old records/views from previous versions can
    # load safely. The SO approval workflow itself is disabled.
    so_order_approval_route = fields.Selection(
        related='company_id.so_order_approval_route',
        string="Use Approval Route",
        readonly=True,
    )

    state = fields.Selection(
        selection_add=[('to approve', 'Under Approval')],
        ondelete={'to approve': 'set default'},
    )

    team_custom_id = fields.Many2one(
        comodel_name="sale.team.custom",
        string="Sale Team",
        domain="[('company_id', '=', company_id)]",
        ondelete="restrict",
    )

    approver_ids = fields.One2many(
        comodel_name="sale.order.approver",
        inverse_name="order_id",
        string="Approvers",
        readonly=True,
    )

    current_approver = fields.Many2one(
        comodel_name="sale.order.approver",
        string="Approver",
        compute="_compute_approver",
        store=True,
        compute_sudo=True,
    )

    next_approver = fields.Many2one(
        comodel_name="sale.order.approver",
        string="Next Approver",
        compute="_compute_approver",
        store=True,
        compute_sudo=True,
    )

    is_current_approver = fields.Boolean(
        string="Is Current Approver",
        compute="_compute_is_current_approver",
    )

    lock_amount_total = fields.Boolean(
        string="Lock Amount Total",
        compute="_compute_lock_amount_total",
    )

    @api.depends('approver_ids.state')
    def _compute_approver(self):
        for order in self:
            order.next_approver = False
            order.current_approver = False

    @api.depends('current_approver')
    def _compute_is_current_approver(self):
        for order in self:
            order.is_current_approver = False

    @api.depends('approver_ids.state', 'approver_ids.lock_amount_total')
    def _compute_lock_amount_total(self):
        for order in self:
            order.lock_amount_total = False

    def _can_be_confirmed(self):
        self.ensure_one()
        return self.state in {'draft', 'sent', 'to approve'}

    def action_confirm(self):
        """Always use the standard Odoo confirmation flow."""
        return super().action_confirm()

    def button_approve(self, force=False):
        """Compatibility for old buttons/records: confirm immediately."""
        return self.action_confirm()
