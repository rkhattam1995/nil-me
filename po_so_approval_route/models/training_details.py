from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TrainingDetails(models.Model):
    _name = 'purchase.training.details'
    _description = 'Training Details for Purchase Orders'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', required=True, ondelete='cascade')
    training_id = fields.Many2one('training.training', string='Training', required=True)
    instructor_id = fields.Many2one('res.partner', string='Instructor', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    location = fields.Char(string='Location', required=True)
    number_of_participants = fields.Integer(string='Number of Participants', required=True)
    training_cost = fields.Float(string='Training Cost', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.training.details') or _('New')
        return super(TrainingDetails, self).create(vals_list)

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("End date must be greater than start date")) 