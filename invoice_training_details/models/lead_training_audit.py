# -*- coding: utf-8 -*-

from odoo import Command, api, fields, models, _
from odoo.exceptions import AccessError
from odoo.tools import html2plaintext


AUDIT_SKIP_LEAD_FIELDS = {
    'write_date',
    'write_uid',
    'create_date',
    'create_uid',
    'message_ids',
    'message_follower_ids',
    'message_partner_ids',
    'activity_ids',
    'training_audit_count',
    'training_audit_visible',
}


class TrainingCourseAudit(models.Model):
    _inherit = 'training.course.audit'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead',
        readonly=True,
        index=True,
        ondelete='set null',
    )

    @api.model
    def _nil_setup_ruba_access(self):
        """Grant Change Log visibility only to the exact Ruba user."""
        group = self.env.ref(
            'invoice_training_details.group_training_audit_ruba',
            raise_if_not_found=False,
        )
        ruba_user = self.env.ref(
            'base.user_admin',
            raise_if_not_found=False,
        )
        if not group or not ruba_user:
            return True

        members = (
            self.env['res.users']
            .sudo()
            .with_context(active_test=False)
            .search([('groups_id', 'in', group.id)])
        )
        for user in members:
            if user.id != ruba_user.id:
                user.sudo().write({
                    'groups_id': [Command.unlink(group.id)],
                })

        ruba_user.sudo().write({
            'groups_id': [Command.link(group.id)],
        })
        return True


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    def _nil_create_audit(self, values):
        """Attach every Training/LCP line audit entry to its CRM Lead."""
        for rec in self:
            payload = dict(values)
            root = rec.source_training_course_id or rec
            lead = root.lead_id or rec.lead_id
            if lead:
                payload['lead_id'] = lead.id
            super(TrainingCourse, rec)._nil_create_audit(payload)
        return True


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    training_audit_count = fields.Integer(
        string='Change Log',
        compute='_compute_training_audit_count',
    )
    training_audit_visible = fields.Boolean(
        compute='_compute_training_audit_visible',
    )

    @api.model
    def _nil_is_ruba_user(self):
        ruba_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        return bool(ruba_user and self.env.user.id == ruba_user.id)

    @api.depends_context('uid')
    def _compute_training_audit_visible(self):
        allowed = self._nil_is_ruba_user()
        for lead in self:
            lead.training_audit_visible = allowed

    def _nil_lead_audit_value(self, field_name):
        """Human-readable value for any field written on the Lead."""
        self.ensure_one()
        field = self._fields[field_name]
        value = self[field_name]

        if field.type == 'many2one':
            if not value:
                return ''
            name = value.display_name
            return name if isinstance(name, str) else ''

        if field.type in ('many2many', 'one2many'):
            names = []
            for record in value:
                name = record.display_name
                if not isinstance(name, str) or not name.strip():
                    # Some custom line records have no name. Keep a stable
                    # audit label instead of passing False into str.join().
                    name = '%s #%s' % (
                        record._description or record._name,
                        record.id,
                    )
                names.append(name)
            return ', '.join(names)

        if field.type == 'selection':
            try:
                labels = dict(field._description_selection(self.env))
                return str(labels.get(value, value) or '')
            except Exception:
                return str(value or '')

        if field.type == 'html':
            text = html2plaintext(value or '')
            return ' '.join(text.split())

        if field.type == 'binary':
            return '[File attached]' if value else ''

        if field.type == 'boolean':
            return 'Yes' if value else 'No'

        if value in (False, None):
            return ''

        return str(value)

    def _nil_lead_audit_field_names(self, vals):
        names = []
        for name in vals:
            field = self._fields.get(name)
            if not field or name in AUDIT_SKIP_LEAD_FIELDS:
                continue
            # Skip pure computed output fields. Manual/inverse fields still pass.
            if field.compute and not field.inverse:
                continue
            names.append(name)
        return names

    def _nil_create_lead_field_audit(
        self,
        field_name,
        old_value,
        new_value,
    ):
        self.ensure_one()
        if old_value == new_value:
            return True

        field = self._fields[field_name]
        self.env['training.course.audit'].sudo().create({
            'lead_id': self.id,
            'document_model': 'crm.lead',
            'document_name': self.display_name,
            'operation': 'update',
            'field_name': field_name,
            'field_label': field.string or field_name,
            'old_value': old_value,
            'new_value': new_value,
            'changed_by_id': self.env.user.id,
            'changed_at': fields.Datetime.now(),
        })
        return True

    def write(self, vals):
        """
        Audit every real field edit written on the CRM Lead.

        This deliberately includes standard CRM fields, custom fields, Studio
        fields, Students' Details, External/Internal Notes, stage, salesperson,
        ordering/end customer data, pricing and LCP lead-level inputs.
        """
        if self.env.context.get('nil_skip_lead_audit'):
            return super().write(vals)

        tracked_names = self._nil_lead_audit_field_names(vals)
        before = {}
        if tracked_names:
            for lead in self:
                before[lead.id] = {
                    name: lead._nil_lead_audit_value(name)
                    for name in tracked_names
                }

        result = super().write(vals)

        if tracked_names:
            for lead in self:
                for name in tracked_names:
                    old_value = before[lead.id][name]
                    new_value = lead._nil_lead_audit_value(name)
                    lead._nil_create_lead_field_audit(
                        name,
                        old_value,
                        new_value,
                    )

        return result

    def _nil_training_audit_domain(self):
        self.ensure_one()
        source_ids = self.training_course_ids.ids
        return [
            '|',
            ('lead_id', '=', self.id),
            '|',
            '&',
            ('document_model', '=', 'crm.lead'),
            ('document_name', '=', self.display_name),
            ('source_training_course_id', 'in', source_ids or [0]),
        ]

    def _compute_training_audit_count(self):
        Audit = self.env['training.course.audit'].sudo()
        for lead in self:
            if not lead.training_audit_visible:
                lead.training_audit_count = 0
                continue
            lead.training_audit_count = Audit.search_count(
                lead._nil_training_audit_domain()
            )

    def action_view_training_audit(self):
        self.ensure_one()

        if not self._nil_is_ruba_user():
            raise AccessError(_('You are not allowed to view the Change Log.'))

        self.env['training.course.audit'].sudo()._nil_setup_ruba_access()

        action = self.env['ir.actions.actions']._for_xml_id(
            'invoice_training_details.action_training_course_audit'
        )
        action['name'] = _('Change Log - %s') % self.display_name
        action['domain'] = self._nil_training_audit_domain()
        action['context'] = {}
        return action
