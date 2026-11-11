# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        if (
            'training_course_ids' in vals
            and not self.env.context.get('nil_training_unlock')
        ):
            for move in self:
                if (
                    move.move_type in ('out_invoice', 'out_refund')
                    and move.state == 'posted'
                ):
                    raise UserError(_(
                        'Training details are locked because customer invoice %s is already posted.'
                    ) % move.display_name)

        return super().write(vals)
