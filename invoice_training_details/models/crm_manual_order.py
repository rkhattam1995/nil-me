# -*- coding: utf-8 -*-

from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    sequence = fields.Integer(
        string='Manual Order',
        default=10,
        index=True,
        copy=False,
    )
