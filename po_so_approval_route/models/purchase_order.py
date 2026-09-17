# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    po_order_approval_route = fields.Selection(related='company_id.po_order_approval_route',
                                               string="Use Approval Route", readonly=True)

    team_id = fields.Many2one(
        comodel_name="purchase.team",
        string="Purchase Team",
        domain="[('company_id', '=', company_id)]",
        readonly=False,
        ondelete="restrict",
    )

    approver_ids = fields.One2many(
        comodel_name="purchase.order.approver", inverse_name="order_id", string="Approvers", readonly=True)

    current_approver = fields.Many2one(
        comodel_name="purchase.order.approver", string="Approver",
        compute="_compute_approver", store=True, compute_sudo=True)

    next_approver = fields.Many2one(
        comodel_name="purchase.order.approver", string="Next Approver",
        compute="_compute_approver", store=True, compute_sudo=True)

    is_current_approver = fields.Boolean(
        string="Is Current Approver", compute="_compute_is_current_approver"
    )

    lock_amount_total = fields.Boolean(
        string="Lock Amount Total", compute="_compute_lock_amount_total"
    )

    amount_total = fields.Monetary(tracking=True)

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'amount_total' in init_values and self.amount_total != init_values.get('amount_total'):
            self._check_lock_amount_total()
        return super(PurchaseOrder, self)._track_subtype(init_values)

    def button_approve(self, force=False):
        for order in self:
            if not order.team_id:
                super(PurchaseOrder, order).button_approve(force)
            elif order.current_approver:
                if order.current_approver.user_id == self.env.user or self.env.is_superuser():
                    order.current_approver.state = 'approved'
                    order.message_post(body=_('PO approved by %s') % self.env.user.name)
                    if order.next_approver:
                        order.send_to_approve()
                    else:
                        partner = order.user_id.partner_id if order.user_id else order.create_uid.partner_id
                        order.message_post(
                            body=_('Purchase Order "%s" was approved.') % order.name,
                            partner_ids=[partner.id],
                            subtype_id=self.env.ref('mail.mt_note').id
                        )
                        return super(PurchaseOrder, order).button_approve(force)

    def button_confirm(self):
        for order in self:
            if order.state not in ['draft', 'sent']:
                continue

            if not order.team_id:
                super(PurchaseOrder, order).button_confirm()
            else:
                order.generate_approval_route()
                if order.next_approver:
                    order.write({'state': 'to approve'})
                    order.send_to_approve()
                else:
                    super(PurchaseOrder, order).button_approve()

            order._add_supplier_to_product()
            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])
        return True

    def generate_approval_route(self):
        for order in self:
            if not order.team_id:
                continue
            if order.approver_ids:
                order.approver_ids.unlink()
            for team_approver in order.team_id.approver_ids:
                custom_condition = order.compute_custom_condition(team_approver)
                if not custom_condition:
                    continue

                min_amount = team_approver.company_currency_id._convert(
                    team_approver.min_amount,
                    order.currency_id,
                    order.company_id,
                    order.date_order or fields.Date.today())
                if min_amount > order.amount_total:
                    continue
                max_amount = team_approver.company_currency_id._convert(
                    team_approver.max_amount,
                    order.currency_id,
                    order.company_id,
                    order.date_order or fields.Date.today())
                if max_amount and max_amount < order.amount_total:
                    continue

                self.env['purchase.order.approver'].create({
                    'sequence': team_approver.sequence,
                    'team_id': team_approver.team_id.id,
                    'user_id': team_approver.user_id.id,
                    'role': team_approver.role,
                    'min_amount': team_approver.min_amount,
                    'max_amount': team_approver.max_amount,
                    'lock_amount_total': team_approver.lock_amount_total,
                    'order_id': order.id,
                    'team_approver_id': team_approver.id,
                })

    def compute_custom_condition(self, team_approver):
        self.ensure_one()
        localdict = {'PO': self, 'USER': self.env.user}
        if not team_approver.custom_condition_code:
            return True
        try:
            safe_eval(team_approver.custom_condition_code, localdict, mode='exec', nocopy=True)
            return bool(localdict['result'])
        except Exception as e:
            raise UserError(_('Wrong condition code defined for %s. Error: %s') % (team_approver.display_name, e))

    @api.depends('approver_ids.state')
    def _compute_approver(self):
        for order in self:
            next_approvers = order.approver_ids.filtered(lambda a: a.state == "to approve")
            order.next_approver = next_approvers[0] if next_approvers else False

            current_approvers = order.approver_ids.filtered(lambda a: a.state == "pending")
            order.current_approver = current_approvers[0] if current_approvers else False

    @api.depends('current_approver')
    def _compute_is_current_approver(self):
        for order in self:
            order.is_current_approver = ((order.current_approver and order.current_approver.user_id == self.env.user)
                                         or self.env.is_superuser())

    @api.depends('approver_ids.state', 'approver_ids.lock_amount_total')
    def _compute_lock_amount_total(self):
        for order in self:
            order.lock_amount_total = len(order.approver_ids.filtered(
                lambda a: a.state == "approved" and a.lock_amount_total
            )) > 0

    def send_to_approve(self):
        for order in self:
            if order.state != 'to approve' and not order.team_id:
                continue

            if not order.next_approver:
                raise UserError(_("There are no approvers in the selected PO team."))

            order.sudo().next_approver.state = 'pending'
            current_approver_partner = order.current_approver.user_id.partner_id
            if current_approver_partner not in order.message_partner_ids:
                order.message_subscribe([current_approver_partner.id])
            order.message_post(
                body=_("You have been requested to approve the purchase order %s.") % order.name,
                partner_ids=[current_approver_partner.id],
                subtype_id=self.env.ref('mail.mt_note').id
            )

    def _check_lock_amount_total(self):
        msg = _('Sorry, you are not allowed to change Amount Total of PO. ')
        for order in self:
            if order.state in ('draft', 'sent'):
                continue
            if order.lock_amount_total:
                reason = _('It is locked after received approval. ')
                raise UserError(msg + "\n\n" + reason)
            if order.team_id.lock_amount_total:
                reason = _('It is locked after generated approval route. ')
                suggestion = _('To make changes, cancel and reset PO to draft. ')
                raise UserError(msg + "\n\n" + reason + "\n\n" + suggestion)
