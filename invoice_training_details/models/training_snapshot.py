# -*- coding: utf-8 -*-

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError

from .sync_utils import sync_commands


BASE_TRAINING_FIELDS = {
    'name',
    'no_of_student',
    'duration',
    'training_date_start',
    'training_date_end',
    'price',
    'instructor_id',
    'descriptions',
    'training_id',
    'poref',
    'invref',
    'tr_expiry_date',
    'where_location2',
    'location',
    'payment_method',
    'clcs_qty',
}

COPYABLE_FIELD_TYPES = {
    'boolean',
    'integer',
    'float',
    'monetary',
    'char',
    'text',
    'html',
    'selection',
    'date',
    'datetime',
    'many2one',
}


class TrainingCourseAudit(models.Model):
    _name = 'training.course.audit'
    _description = 'Training Course Change Audit'
    _order = 'changed_at desc, id desc'

    training_course_id = fields.Many2one(
        'training.course',
        string='Training Record',
        ondelete='set null',
        index=True,
        readonly=True,
    )
    source_training_course_id = fields.Many2one(
        'training.course',
        string='Original Training Record',
        ondelete='set null',
        index=True,
        readonly=True,
    )
    document_model = fields.Char(
        string='Document Model',
        readonly=True,
        index=True,
    )
    document_name = fields.Char(
        string='Document',
        readonly=True,
        index=True,
    )
    operation = fields.Selection(
        [
            ('create', 'Created'),
            ('update', 'Updated'),
            ('delete', 'Deleted'),
        ],
        string='Action',
        required=True,
        readonly=True,
        index=True,
    )
    field_name = fields.Char(
        string='Technical Field',
        readonly=True,
    )
    field_label = fields.Char(
        string='Field',
        readonly=True,
    )
    old_value = fields.Text(
        string='Old Value',
        readonly=True,
    )
    new_value = fields.Text(
        string='New Value',
        readonly=True,
    )
    changed_by_id = fields.Many2one(
        'res.users',
        string='Changed By',
        required=True,
        readonly=True,
        index=True,
    )
    changed_at = fields.Datetime(
        string='Changed At',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        index=True,
    )

    @api.model
    def _nil_setup_ruba_access(self):
        """Grant the private audit group only to the exact Ruba Khattam user."""
        group = self.env.ref(
            'invoice_training_details.group_training_audit_ruba',
            raise_if_not_found=False,
        )
        if not group:
            return True

        users = (
            self.env['res.users']
            .sudo()
            .with_context(active_test=False)
            .search([('name', 'ilike', 'Ruba Khattam')])
        )

        for user in users:
            normalized = ' '.join((user.name or '').split()).casefold()
            if normalized == 'ruba khattam':
                user.sudo().write({
                    'groups_id': [Command.link(group.id)],
                })
                break

        return True


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    source_training_course_id = fields.Many2one(
        'training.course',
        string='Original Training Record',
        copy=False,
        readonly=True,
        ondelete='set null',
        index=True,
        help=(
            'Original CRM training line from which this document-specific '
            'snapshot was copied.'
        ),
    )

    @api.model
    def _nil_snapshot_field_names(self):
        names = set(BASE_TRAINING_FIELDS)

        # Copy manual/stored LCP inputs automatically, but never computed or
        # related LCP result fields. This keeps document copies independent
        # while preserving the commercial inputs that were true at creation.
        for name, field in self._fields.items():
            if not name.startswith('lcp_'):
                continue
            if name == 'lcp_so_no':
                continue
            if field.type not in COPYABLE_FIELD_TYPES:
                continue
            if not field.store or field.compute or field.related:
                continue
            names.add(name)

        return [
            name
            for name in sorted(names)
            if name in self._fields
            and self._fields[name].type in COPYABLE_FIELD_TYPES
        ]

    def _nil_snapshot_vals(self):
        self.ensure_one()
        values = {}

        for name in self._nil_snapshot_field_names():
            field = self._fields[name]
            value = self[name]
            values[name] = value.id if field.type == 'many2one' else value

        root = self.source_training_course_id or self
        values['source_training_course_id'] = root.id
        return values

    @api.model
    def _nil_snapshot_commands(self, courses):
        return [
            Command.create(course._nil_snapshot_vals())
            for course in courses
        ]

    def _nil_posted_customer_invoice(self):
        self.ensure_one()
        move = self.move_id
        if (
            move
            and move.move_type in ('out_invoice', 'out_refund')
            and move.state == 'posted'
        ):
            return move
        return self.env['account.move']

    @api.model
    def _nil_target_posted_customer_invoice(self, vals):
        move_id = vals.get('move_id')
        if not move_id:
            return self.env['account.move']

        move = self.env['account.move'].browse(move_id)
        if (
            move.exists()
            and move.move_type in ('out_invoice', 'out_refund')
            and move.state == 'posted'
        ):
            return move
        return self.env['account.move']

    def _nil_check_training_unlocked(self, vals=None):
        if self.env.context.get('nil_training_unlock'):
            return True

        target_move = (
            self._nil_target_posted_customer_invoice(vals or {})
            if vals
            else self.env['account.move']
        )
        if target_move:
            raise UserError(_(
                'Training details are locked because customer invoice %s '
                'is already posted.'
            ) % target_move.display_name)

        for rec in self:
            move = rec._nil_posted_customer_invoice()
            if move:
                raise UserError(_(
                    'Training details are locked because customer invoice %s '
                    'is already posted.'
                ) % move.display_name)

        return True

    def _nil_audit_document(self):
        self.ensure_one()
        if self.move_id:
            return 'account.move', self.move_id.display_name
        if self.sale_id:
            return 'sale.order', self.sale_id.display_name
        if self.purchase_order_id:
            return 'purchase.order', self.purchase_order_id.display_name
        if self.lead_id:
            return 'crm.lead', self.lead_id.display_name
        return 'training.course', self.display_name

    def _nil_audit_value(self, field_name):
        self.ensure_one()
        field = self._fields[field_name]
        value = self[field_name]

        if field.type == 'many2one':
            return value.display_name if value else ''
        if value in (False, None):
            return ''
        return str(value)

    def _nil_audit_summary(self):
        self.ensure_one()
        parts = []
        for name in (
            'training_id',
            'no_of_student',
            'training_date_start',
            'training_date_end',
            'payment_method',
            'price',
        ):
            if name in self._fields:
                value = self._nil_audit_value(name)
                if value:
                    parts.append('%s: %s' % (self._fields[name].string, value))
        return ' | '.join(parts)

    def _nil_create_audit(self, values):
        if self.env.context.get('nil_skip_training_audit'):
            return True

        Audit = self.env['training.course.audit'].sudo()
        current_user_id = self.env.user.id

        for rec in self:
            document_model, document_name = rec._nil_audit_document()
            payload = dict(values)
            payload.update({
                'training_course_id': rec.id,
                'source_training_course_id': (
                    rec.source_training_course_id.id
                    if rec.source_training_course_id
                    else rec.id
                ),
                'document_model': document_model,
                'document_name': document_name,
                'changed_by_id': current_user_id,
                'changed_at': fields.Datetime.now(),
            })
            Audit.with_context(nil_skip_training_audit=True).create(payload)

        return True

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('nil_training_unlock'):
            for vals in vals_list:
                move = self._nil_target_posted_customer_invoice(vals)
                if move:
                    raise UserError(_(
                        'Training details are locked because customer invoice %s '
                        'is already posted.'
                    ) % move.display_name)

        records = super().create(vals_list)

        if not self.env.context.get('nil_skip_training_audit'):
            for rec in records:
                rec._nil_create_audit({
                    'operation': 'create',
                    'field_name': False,
                    'field_label': 'Training Details',
                    'old_value': '',
                    'new_value': rec._nil_audit_summary(),
                })

        return records

    def write(self, vals):
        self._nil_check_training_unlocked(vals)

        tracked_names = set(self._nil_snapshot_field_names())
        changed_names = sorted(tracked_names.intersection(vals))

        before = {}
        if changed_names and not self.env.context.get('nil_skip_training_audit'):
            for rec in self:
                before[rec.id] = {
                    name: rec._nil_audit_value(name)
                    for name in changed_names
                }

        result = super().write(vals)

        if changed_names and not self.env.context.get('nil_skip_training_audit'):
            for rec in self:
                for name in changed_names:
                    old_value = before[rec.id][name]
                    new_value = rec._nil_audit_value(name)
                    if old_value == new_value:
                        continue
                    rec._nil_create_audit({
                        'operation': 'update',
                        'field_name': name,
                        'field_label': rec._fields[name].string or name,
                        'old_value': old_value,
                        'new_value': new_value,
                    })

        return result

    def unlink(self):
        self._nil_check_training_unlocked()

        if not self.env.context.get('nil_skip_training_audit'):
            for rec in self:
                rec._nil_create_audit({
                    'operation': 'delete',
                    'field_name': False,
                    'field_label': 'Training Details',
                    'old_value': rec._nil_audit_summary(),
                    'new_value': '',
                })

        return super().unlink()


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _prepare_opportunity_quotation_context(self):
        context = super()._prepare_opportunity_quotation_context()
        context['default_training_course_ids'] = (
            self.env['training.course']._nil_snapshot_commands(
                self.training_course_ids
            )
        )
        return context

    def action_new_purchase_order(self):
        self.ensure_one()
        action = super().action_new_purchase_order()

        if action.get('res_model') == 'purchase.order':
            courses = self.training_course_ids.filtered(
                lambda course: course.payment_method == 'cash'
            )
            context = dict(action.get('context') or {})
            context['default_training_course_ids'] = (
                self.env['training.course']._nil_snapshot_commands(courses)
            )
            action['context'] = context

        return action

    def action_new_training_so(self):
        self.ensure_one()
        action = super().action_new_training_so()

        if action.get('res_model') == 'sale.order':
            context = dict(action.get('context') or {})
            context['default_training_course_ids'] = (
                self.env['training.course']._nil_snapshot_commands(
                    self.training_course_ids
                )
            )
            action['context'] = context

        return action


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _prepare_invoice(self):
        self.ensure_one()
        values = super()._prepare_invoice()
        values['training_course_ids'] = (
            self.env['training.course']._nil_snapshot_commands(
                self.training_course_ids
            )
        )
        return values

    def synch_order(self):
        self._check_nil_sync_draft()
        items = []

        for course in self.training_course_ids:
            if not course.training_id:
                raise UserError(_(
                    'Select a product for every training before synchronizing.'
                ))

            source = course.source_training_course_id or course
            lead = source.lead_id

            if lead and course.lcp_cost_learning_partner:
                values = lead._lcp_sale_lines(
                    course,
                    self.company_id,
                )[0][2]
            else:
                values = {
                    'product_id': course.training_id.id,
                    'name': course.training_id.display_name,
                    'product_uom_qty': 1,
                    'price_unit': course.price,
                }

            items.append((course, values))

        self.write({
            'order_line': sync_commands(
                self.order_line,
                items,
                'nil_sync_training_id',
            )
        })
        return True
