# -*- coding: utf-8 -*-

from odoo import fields, models


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    # Compatibility field for obsolete inherited views that may still exist
    # in the database from an earlier module revision. The reset logic no
    # longer uses this field, but keeping it defined lets Odoo validate and
    # remove/update those stale views safely during module upgrade.
    lcp_input_snapshot = fields.Text(
        string='LCP Input Snapshot',
        copy=False,
    )
