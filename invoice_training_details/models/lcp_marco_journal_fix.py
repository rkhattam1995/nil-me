# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _lcp_marco_bill(self, course):
        """Create Marco's incentive as a balanced Journal Entry.

        Debit: Incentive expense account.
        Credit: the company's USD bank account.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        usd = self.env.ref('base.USD')

        incentive_account = self.env['account.account'].with_company(company).search([
            ('name', 'ilike', 'Incentive'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not incentive_account:
            raise UserError(_(
                'No Incentive account was found in %s.'
            ) % company.display_name)

        bank_journals = self.env['account.journal'].with_company(company).search([
            ('company_id', '=', company.id),
            ('type', '=', 'bank'),
            ('active', '=', True),
            ('default_account_id', '!=', False),
        ])
        usd_bank_journals = bank_journals.filtered(
            lambda journal: (
                journal.currency_id == usd
                or journal.default_account_id.currency_id == usd
            )
        )

        if len(usd_bank_journals) > 1:
            named_usd = usd_bank_journals.filtered(
                lambda journal: (
                    'usd' in (journal.name or '').lower()
                    or 'usd' in (journal.code or '').lower()
                    or '$' in (journal.name or '')
                )
            )
            if len(named_usd) == 1:
                usd_bank_journals = named_usd

        if not usd_bank_journals:
            raise UserError(_(
                'No active USD bank journal with a default bank account was found in %s.'
            ) % company.display_name)
        if len(usd_bank_journals) > 1:
            raise UserError(_(
                'More than one USD bank journal was found in %s: %s. '
                'The Marco entry was not created to avoid crediting the wrong bank.'
            ) % (
                company.display_name,
                ', '.join(usd_bank_journals.mapped('display_name')),
            ))

        bank_journal = usd_bank_journals[0]
        bank_account = bank_journal.default_account_id

        instructor = course.instructor_id
        partner = self._lcp_instructor_partner(instructor)

        rate = (
            course.lcp_instructor_md_rate
            if course.lcp_instructor_source == 'nil_me'
            else course.lcp_vendor_instructor_day
        ) or 0.0
        total = (
            course.lcp_total_instructor_md
            if course.lcp_instructor_source == 'nil_me'
            else course.lcp_total_vendor_instructor
        ) or 0.0
        if total <= 0:
            raise UserError(_('Marco Instructor Total is zero. Fill the rate first.'))

        move_date = course.training_date_end or course.training_date_start
        if not move_date:
            raise UserError(_('Set the Training date before creating Marco Incentive Journal Entry.'))

        company_currency = company.currency_id
        company_amount = usd._convert(
            total,
            company_currency,
            company,
            move_date,
        )

        customer = self.training_name or self.ordering_partner_id
        training = course.training_id.display_name or course.name or self.name
        description = 'Training: %s | Dates: %s - %s | Customer: %s' % (
            training,
            course.training_date_start or '',
            course.training_date_end or '',
            customer.display_name if customer else '',
        )

        debit_line = {
            'name': description,
            'account_id': incentive_account.id,
            'partner_id': partner.id,
            'debit': company_amount,
            'credit': 0.0,
        }
        credit_line = {
            'name': description,
            'account_id': bank_account.id,
            'partner_id': partner.id,
            'debit': 0.0,
            'credit': company_amount,
        }

        if incentive_account.account_type in ('asset_receivable', 'liability_payable'):
            debit_line['date_maturity'] = fields.Date.end_of(move_date, 'month')

        if usd != company_currency:
            debit_line.update({
                'currency_id': usd.id,
                'amount_currency': total,
            })
            credit_line.update({
                'currency_id': usd.id,
                'amount_currency': -total,
            })

        move = self.env['account.move'].with_company(company).create({
            'move_type': 'entry',
            'company_id': company.id,
            'journal_id': bank_journal.id,
            'date': move_date,
            'ref': training,
            'crm_lead_id': self.id,
            'purchase_training_type': 'instructor',
            'instructor_training_course_id': course.id,
            'instructor_id': instructor.id,
            'instructor_from': course.training_date_start,
            'instructor_to': course.training_date_end,
            'instructor_days': course.lcp_days,
            'instructor_daily_rate': rate,
            'instructor_total': total,
            'line_ids': [
                (0, 0, debit_line),
                (0, 0, credit_line),
            ],
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Marco Incentive Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'target': 'current',
        }
