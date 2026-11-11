# -*- coding: utf-8 -*-
"""Per-field CRM Change Log for records edited inside Lead detail tables.

Only explicit, persisted user edits are tracked. Computed fields, chatter and
system bookkeeping are excluded to avoid recursion and audit noise.
"""
from hashlib import sha256

from odoo import api, fields, models
from odoo.tools import html2plaintext

_SAFE_TYPES = {
    'char', 'text', 'html', 'boolean', 'integer', 'float', 'monetary',
    'date', 'datetime', 'selection', 'many2one', 'many2many',
}
_SKIP = {
    'id', 'display_name', '__last_update', 'write_date', 'write_uid',
    'create_date', 'create_uid', 'message_ids', 'activity_ids',
    'message_follower_ids', 'message_partner_ids',
}


def _fields_to_log(rec, values):
    result = []
    for name in values:
        field = rec._fields.get(name)
        if (name in _SKIP or not field or field.type not in _SAFE_TYPES
                or not field.store or field.compute or field.related):
            continue
        result.append(name)
    return result


def _value(rec, name):
    field = rec._fields[name]
    data = rec[name]
    if field.type == 'many2one':
        if not data:
            return ''
        return '%s (#%s)' % (data.display_name or data._description or data._name, data.id)
    if field.type == 'many2many':
        return ', '.join(
            '%s (#%s)' % (entry.display_name or entry._name, entry.id)
            for entry in data
        )
    if field.type == 'selection':
        try:
            label = dict(field._description_selection(rec.env))
            return str(label.get(data, data) or '')
        except (ValueError, TypeError, KeyError):
            return str(data or '')
    if field.type == 'boolean':
        return 'Yes' if data else 'No'
    if field.type == 'html':
        if not data:
            return ''
        plain = ' '.join(html2plaintext(data).split())
        fingerprint = sha256(str(data).encode('utf-8')).hexdigest()[:12]
        return '%s [HTML fingerprint: %s]' % (plain, fingerprint)
    if data is False or data is None:
        return ''
    return str(data)


def _lead_of(rec, parent_field):
    if parent_field == 'pricing_id.lead_id':
        return rec.pricing_id.lead_id
    return rec[parent_field]


def _record_label(rec):
    label = rec.display_name or rec._description or rec._name
    return '%s (#%s)' % (label, rec.id)


def _event(rec, lead, operation, name, before, after):
    if not lead:
        return
    label = rec._fields[name].string or name if name else 'Record'
    rec.env['training.course.audit'].sudo().create({
        'lead_id': lead.id,
        'document_model': 'crm.lead',
        'document_name': lead.display_name,
        'operation': operation,
        'field_name': '%s.%s' % (rec._name, name or 'record'),
        'field_label': '%s / %s' % (_record_label(rec), label),
        'old_value': before if before != '' else '(empty)',
        'new_value': after if after != '' else '(empty)',
        'changed_by_id': rec.env.user.id,
        'changed_at': fields.Datetime.now(),
    })


def _created(records, values_list, parent_field):
    if records.env.context.get('nil_skip_lead_audit'):
        return
    for rec, values in zip(records, values_list):
        lead = _lead_of(rec, parent_field)
        if not lead:
            continue
        _event(rec, lead, 'create', None, '(not created)', 'Created: %s' % _record_label(rec))
        for name in _fields_to_log(rec, values):
            _event(rec, lead, 'create', name, '', _value(rec, name))


def _written(records, values, parent_field, delegate):
    if records.env.context.get('nil_skip_lead_audit'):
        return delegate(values)
    before = {}
    for rec in records:
        names = _fields_to_log(rec, values)
        before[rec.id] = (
            _lead_of(rec, parent_field),
            names,
            {name: _value(rec, name) for name in names},
        )
    result = delegate(values)
    for rec in records:
        old_lead, names, old_values = before[rec.id]
        new_lead = _lead_of(rec, parent_field)
        targets = []
        if old_lead:
            targets.append(old_lead)
        if new_lead and (not old_lead or new_lead.id != old_lead.id):
            targets.append(new_lead)
        for name in names:
            after = _value(rec, name)
            old = old_values[name]
            if old == after:
                continue
            for lead in targets:
                _event(rec, lead, 'update', name, old, after)
    return result


def _deleted(records, parent_field):
    if records.env.context.get('nil_skip_lead_audit'):
        return
    for rec in records:
        lead = _lead_of(rec, parent_field)
        if not lead:
            continue
        for name in _fields_to_log(rec, rec._fields):
            value = _value(rec, name)
            if value and value not in ('No', '0', '0.0'):
                _event(rec, lead, 'delete', name, value, '(deleted)')
        _event(rec, lead, 'delete', None, 'Deleted: %s' % _record_label(rec), '(deleted)')


class NilCostDetailsAudit(models.Model):
    _inherit = 'cost.details'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _created(records, vals_list, 'cos_lead_id')
        return records

    def write(self, vals):
        return _written(self, vals, 'cos_lead_id', super().write)

    def unlink(self):
        _deleted(self, 'cos_lead_id')
        return super().unlink()


class NilProfessionalServicesAudit(models.Model):
    _inherit = 'pro.service'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _created(records, vals_list, 'pro_lead_id')
        return records

    def write(self, vals):
        return _written(self, vals, 'pro_lead_id', super().write)

    def unlink(self):
        _deleted(self, 'pro_lead_id')
        return super().unlink()


class NilTicketAudit(models.Model):
    _inherit = 'ticket.ticket'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _created(records, vals_list, 'ticket_lead_id')
        return records

    def write(self, vals):
        return _written(self, vals, 'ticket_lead_id', super().write)

    def unlink(self):
        _deleted(self, 'ticket_lead_id')
        return super().unlink()


class NilHotelAudit(models.Model):
    _inherit = 'hotel.hotel'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _created(records, vals_list, 'hotel_lead_id')
        return records

    def write(self, vals):
        return _written(self, vals, 'hotel_lead_id', super().write)

    def unlink(self):
        _deleted(self, 'hotel_lead_id')
        return super().unlink()


class NilAmPricingAudit(models.Model):
    _inherit = 'am.pricing'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _created(records, vals_list, 'lead_id')
        return records

    def write(self, vals):
        return _written(self, vals, 'lead_id', super().write)

    def unlink(self):
        _deleted(self, 'lead_id')
        return super().unlink()


class NilAmPricingLineAudit(models.Model):
    _inherit = 'am.pricing.line'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _created(records, vals_list, 'pricing_id.lead_id')
        return records

    def write(self, vals):
        return _written(self, vals, 'pricing_id.lead_id', super().write)

    def unlink(self):
        _deleted(self, 'pricing_id.lead_id')
        return super().unlink()
