# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import ValidationError


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    @api.depends('lcp_instructor_source')
    def _compute_lcp_allowed_instructor_ids(self):
        Employee = self.env['hr.employee']
        for line in self:
            domain = [('active', '=', True)]
            if line.lcp_instructor_source == 'nil_me':
                domain.append(('job_id.name', '=ilike', 'Instructor'))
            line.lcp_allowed_instructor_ids = Employee.search(domain)

    @api.onchange('lcp_instructor_source')
    def _onchange_lcp_instructor_source_restrict_employee(self):
        for line in self:
            if (
                line.lcp_instructor_source == 'nil_me'
                and line.instructor_id
                and (line.instructor_id.job_id.name or '').strip().lower() != 'instructor'
            ):
                line.instructor_id = False

    @api.constrains('lcp_instructor_source', 'instructor_id')
    def _check_nilme_instructor_job_position(self):
        for line in self:
            if (
                line.lcp_instructor_source == 'nil_me'
                and line.instructor_id
                and (line.instructor_id.job_id.name or '').strip().lower() != 'instructor'
            ):
                raise ValidationError(_(
                    'When Instructor From is NIL ME, the selected employee must have Job Position "Instructor".'
                ))
