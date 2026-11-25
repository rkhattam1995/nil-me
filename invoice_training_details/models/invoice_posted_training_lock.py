# -*- coding: utf-8 -*-

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError


# Same fields exposed for ordinary editing in the invoice Training tree.
# Never grant permission to change ownership, source or frozen LCP snapshots.
POSTED_TRAINING_EDIT_FIELDS = frozenset({
    'training_id', 'instructor_id', 'location', 'where_location2',
    'payment_method', 'no_of_student', 'duration',
    'training_date_start', 'training_date_end', 'price',
})


class AccountMove(models.Model):
    _inherit = 'account.move'

    nil_can_edit_posted_training = fields.Boolean(
        compute='_compute_nil_can_edit_posted_training',
        store=False,
    )

    @api.model
    def _nil_is_posted_training_editor(self):
        # Reuse the exact account identity already used by the private
        # Change Log setup. Membership alone or Settings admin is not enough.
        owner = self.env.ref('base.user_admin', raise_if_not_found=False)
        return bool(
            owner and self.env.uid == owner.id
            and self.env.user.has_group(
                'invoice_training_details.group_training_audit_ruba'
            )
        )

    @api.depends_context('uid')
    def _compute_nil_can_edit_posted_training(self):
        allowed = self._nil_is_posted_training_editor()
        for move in self:
            move.nil_can_edit_posted_training = allowed

    def _nil_can_update_posted_training_commands(self, commands):
        self.ensure_one()
        if not self._nil_is_posted_training_editor():
            return False
        # Only updates to existing rows belonging to this invoice.
        return all(
            isinstance(cmd, (tuple, list)) and len(cmd) == 3
            and cmd[0] == Command.UPDATE
            and cmd[1] in self.training_course_ids.ids
            and isinstance(cmd[2], dict)
            and set(cmd[2]) <= POSTED_TRAINING_EDIT_FIELDS
            for cmd in commands
        )

    def write(self, vals):
        if (
            'training_course_ids' in vals
            and not self.env.context.get('nil_training_unlock')
        ):
            for move in self:
                if (
                    move.move_type in ('out_invoice', 'out_refund')
                    and move.state == 'posted'
                    and not move._nil_can_update_posted_training_commands(
                        vals['training_course_ids']
                    )
                ):
                    raise UserError(_(
                        'Training details are locked because customer invoice %s is already posted.'
                    ) % move.display_name)

        return super().write(vals)
