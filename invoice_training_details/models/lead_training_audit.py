# -*- coding: utf-8 -*-

from hashlib import sha256

from odoo import Command, api, fields, models, _
from odoo.exceptions import AccessError


AUDIT_SKIP_LEAD_FIELDS = {
    'id',
    'display_name',
    '__last_update',
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
            return ('%s [#%s]' % (name, value.id)) if isinstance(name, str) else ('#%s' % value.id)

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
                names.append('%s [#%s]' % (name, record.id))
            return ', '.join(names)

        if field.type == 'selection':
            try:
                labels = dict(field._description_selection(self.env))
                return str(labels.get(value, value) or '')
            except Exception:
                return str(value or '')

        if field.type == 'html':
            # Keep markup: changing formatting is itself a real edit.
            return str(value or '')

        if field.type == 'binary':
            return 'Attachment SHA256: %s' % sha256(str(value).encode('utf-8')).hexdigest() if value else ''

        if field.type == 'boolean':
            return 'Yes' if value else 'No'

        if value is False or value is None:
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
        operation='update',
    ):
        self.ensure_one()
        if old_value == new_value:
            return True

        field = self._fields[field_name]
        self.env['training.course.audit'].sudo().create({
            'lead_id': self.id,
            'document_model': 'crm.lead',
            'document_name': self.display_name,
            'operation': operation,
            'field_name': field_name,
            'field_label': field.string or field_name,
            'old_value': old_value,
            'new_value': new_value,
            'changed_by_id': self.env.user.id,
            'changed_at': fields.Datetime.now(),
        })
        return True

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        if self.env.context.get('nil_skip_lead_audit'):
            return leads
        Audit = self.env['training.course.audit'].sudo()
        for lead, vals in zip(leads, vals_list):
            Audit.create({
                'lead_id': lead.id,
                'document_model': 'crm.lead',
                'document_name': lead.display_name,
                'operation': 'create',
                'field_label': 'Lead Created',
                'field_name': 'crm.lead',
                'old_value': '',
                'new_value': lead.display_name,
                'changed_by_id': self.env.user.id,
                'changed_at': fields.Datetime.now(),
            })
            for name in lead._nil_lead_audit_field_names(vals):
                new_value = lead._nil_lead_audit_value(name)
                if new_value:
                    lead._nil_create_lead_field_audit(
                        name, '', new_value, operation='create',
                    )
        return leads

    def unlink(self):
        if not self.env.context.get('nil_skip_lead_audit'):
            Audit = self.env['training.course.audit'].sudo()
            for lead in self:
                for name in lead._nil_lead_audit_field_names(lead._fields):
                    value = lead._nil_lead_audit_value(name)
                    if value:
                        lead._nil_create_lead_field_audit(
                            name, value, '', operation='delete',
                        )
                Audit.create({
                    'lead_id': lead.id,
                    'document_model': 'crm.lead',
                    'document_name': lead.display_name,
                    'operation': 'delete',
                    'field_name': 'crm.lead',
                    'field_label': 'Lead Deleted',
                    'old_value': lead.display_name,
                    'new_value': '',
                    'changed_by_id': self.env.user.id,
                    'changed_at': fields.Datetime.now(),
                })
        return super().unlink()

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

# All manually editable details linked to a Lead must have field-level history,
# not only changes to the parent One2many list. This also captures changes made
# from a separate form (without opening the CRM lead).
_RELATED_AUDIT_SKIP = {
    'id', 'display_name', 'write_uid', 'write_date',
    'create_uid', 'create_date', '__last_update',
    'message_ids', 'message_follower_ids', 'activity_ids',
}


def _nil_related_value(record, name):
    field = record._fields[name]
    value = record[name]
    if field.type == 'many2one':
        return ('%s [#%s]' % (value.display_name, value.id)) if value else ''
    if field.type in ('many2many', 'one2many'):
        return ', '.join(
            '%s [#%s]' % (entry.display_name or entry._description or entry._name, entry.id)
            for entry in value
        )
    if field.type == 'selection':
        try:
            labels = dict(field._description_selection(record.env))
            return str(labels.get(value, value) or '')
        except Exception:
            return str(value or '')
    if field.type == 'boolean':
        return 'Yes' if value else 'No'
    if field.type == 'html':
        return str(value or '')
    if field.type == 'binary':
        return ('Attachment SHA256: %s' % sha256(str(value).encode('utf-8')).hexdigest()) if value else ''
    return '' if value is False or value is None else str(value)


class _NilRelatedAuditMixin:
    """Track each real create/edit/delete on an attached CRM detail record."""

    _nil_audit_parent_field = None

    def _nil_related_audit_lead(self):
        self.ensure_one()
        return self[self._nil_audit_parent_field] if self._nil_audit_parent_field else self.env['crm.lead']

    def _nil_related_audit_names(self, names):
        result = []
        for name in names:
            field = self._fields.get(name)
            if (not field or name in _RELATED_AUDIT_SKIP
                    or (field.compute and not field.inverse)):
                continue
            result.append(name)
        return result

    def _nil_related_audit_label(self):
        self.ensure_one()
        return '%s [#%s]' % (self._description or self._name, self.id)

    def _nil_related_audit_event(self, lead, operation, name, old, new):
        if not lead:
            return
        self.env['training.course.audit'].sudo().create({
            'lead_id': lead.id,
            'document_model': 'crm.lead',
            'document_name': lead.display_name,
            'operation': operation,
            'field_name': '%s.%s' % (self._name, name or 'record'),
            'field_label': '%s / %s' % (
                self._nil_related_audit_label(),
                self._fields[name].string if name else 'Record',
            ),
            'old_value': old,
            'new_value': new,
            'changed_by_id': self.env.user.id,
            'changed_at': fields.Datetime.now(),
        })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get('nil_skip_lead_audit'):
            return records
        for rec, vals in zip(records, vals_list):
            lead = rec._nil_related_audit_lead()
            if not lead:
                continue
            rec._nil_related_audit_event(
                lead, 'create', None, '', rec._nil_related_audit_label(),
            )
            for name in rec._nil_related_audit_names(vals):
                value = _nil_related_value(rec, name)
                if value:
                    rec._nil_related_audit_event(lead, 'create', name, '', value)
        return records

    def write(self, vals):
        if self.env.context.get('nil_skip_lead_audit'):
            return super().write(vals)
        names = self._nil_related_audit_names(vals)
        before = {}
        for rec in self:
            before[rec.id] = (
                rec._nil_related_audit_lead(),
                {name: _nil_related_value(rec, name) for name in names},
            )
        result = super().write(vals)
        for rec in self:
            old_lead, old_values = before[rec.id]
            new_lead = rec._nil_related_audit_lead()
            leads = [new_lead] if new_lead else []
            if old_lead and old_lead not in leads:
                leads.append(old_lead)
            for name in names:
                old, new = old_values[name], _nil_related_value(rec, name)
                if old != new:
                    for lead in leads:
                        rec._nil_related_audit_event(lead, 'update', name, old, new)
        return result

    def unlink(self):
        if not self.env.context.get('nil_skip_lead_audit'):
            for rec in self:
                lead = rec._nil_related_audit_lead()
                if not lead:
                    continue
                for name in rec._nil_related_audit_names(rec._fields):
                    old = _nil_related_value(rec, name)
                    if old:
                        rec._nil_related_audit_event(lead, 'delete', name, old, '')
                rec._nil_related_audit_event(
                    lead, 'delete', None, rec._nil_related_audit_label(), '',
                )
        return super().unlink()


class NilLeadAuditCostDetails(_NilRelatedAuditMixin, models.Model):
    _inherit = 'cost.details'
    _nil_audit_parent_field = 'cos_lead_id'


class NilLeadAuditProfessionalServices(_NilRelatedAuditMixin, models.Model):
    _inherit = 'pro.service'
    _nil_audit_parent_field = 'pro_lead_id'


class NilLeadAuditTickets(_NilRelatedAuditMixin, models.Model):
    _inherit = 'ticket.ticket'
    _nil_audit_parent_field = 'ticket_lead_id'


class NilLeadAuditHotels(_NilRelatedAuditMixin, models.Model):
    _inherit = 'hotel.hotel'
    _nil_audit_parent_field = 'hotel_lead_id'


class NilLeadAuditAmPricing(_NilRelatedAuditMixin, models.Model):
    _inherit = 'am.pricing'
    _nil_audit_parent_field = 'lead_id'


class NilLeadAuditAmPricingLine(_NilRelatedAuditMixin, models.Model):
    _inherit = 'am.pricing.line'

    def _nil_related_audit_lead(self):
        self.ensure_one()
        return self.pricing_id.lead_id
