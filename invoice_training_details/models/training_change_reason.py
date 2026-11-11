# -*- coding: utf-8 -*-

from odoo import fields, models


class TrainingCourseAudit(models.Model):
    _inherit = 'training.course.audit'

    # Kept only for backward compatibility with existing database columns and
    # historical audit rows. New changes do not ask for or require a reason.
    change_reason = fields.Text(
        string='Reason',
        readonly=True,
    )


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    # Kept only so older inherited views/database metadata remain compatible.
    # It is no longer displayed and no validation requires it.
    nil_change_reason = fields.Char(
        string='Change Reason',
        copy=False,
    )
