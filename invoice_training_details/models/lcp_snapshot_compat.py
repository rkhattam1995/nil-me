# -*- coding: utf-8 -*-

from odoo import fields, models


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    lcp_input_snapshot = fields.Text(
        string='LCP Input Snapshot',
        copy=False,
    )
