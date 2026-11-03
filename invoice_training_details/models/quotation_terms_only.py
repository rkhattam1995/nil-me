# -*- coding: utf-8 -*-
"""Quotation-only terms. Do not use for New WO, POs, invoices or global defaults."""

from html import escape
import re

from odoo import api, fields, models


# Legal wording is intentionally copied without proofreading or alterations.
# CLC Online differs only in delivery mode and removal of On-site Catering.
# Its numbered clauses are renumbered sequentially without rewriting text.
CLC_ONSITE_TERMS = "1. All NIL Middle East (NIL ME) terms and conditions apply; by accepting this quotation, you are accepting all terms with no exceptions.\n2. Training Location: Instructor-Led – Onsite.\n3. Trainees should use their own laptops for training.\n4. Catering: Not applicable.\n5. Cancellation Policy: Cancellations made at least 2 weeks prior to the start date will incur no charges. Cancellations made within 2 weeks of the start date will incur a 100% cancellation fee.\n6. Participant Changes: Changes or replacements of participant names or email addresses are permitted only if requested at least 2 weeks before the start date.\n7. Purchase Order and Payment: For CLC-based orders, there is no need for an official customer purchase order. Instead, an email accepting the quotation shall be shared with NIL Middle East with the following information included:\na. SO#\nb. Available CLCs in the SO#\nc. Expiry date of the CLCs\n8. All CLC prices are inclusive of VAT. Any other applicable taxes must be paid directly by the buyer to the relevant authorities and must not be deducted from the NIL ME fees.\n9. Schedule Changes: NIL Middle East reserves the right to modify program start dates and schedules. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.\n10. Exams & Vouchers: The price does not include exam costs. NIL ME is not an exam or testing center.\n11. Prices for training do not include students’ costs for tickets, accommodation, visa, etc.\n12. NIL Middle East selects certified instructors based on quality and availability.\n13. Training Language: All training is delivered in English.\n14. Offer Validity: This offer is valid until 15 days from the date of issuance.\n\nDisclaimer: \n-\tCertified Courses kits ((Materials and Labs)) offered, and CLCs redeeming are provided in full cooperation with NIL Middle East’s strategic Partner and CLP “Enterone”.\n-\tAll classes are delivered by certified instructors."

CASH_ONSITE_TERMS = "General Terms & Conditions:\n1. All NIL Middle East (NIL ME) terms and conditions apply.\n2. Trainees should use their own laptop for the training.\n3. Training Location: Onsite at customer office in XXXXXXXX. Customers must secure good internet access for the students and the instructor.\n4. Catering included in NIL ME offer.\n5. Cancellation Policy:\n• Cancellations made at least 2 weeks prior to the program start date will incur no charges.\n• Cancellations made within 2 weeks of the start date will incur a 100% cancellation fee.\n6. Changes or replacements of participant names or email addresses are permitted only if requested at least 2 weeks before the start date.\n7. Schedule Changes: NIL Middle East reserves the right to modify program start dates, cohort schedules, or exam dates without prior notice. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.\n8. Payment:\na. Full payment (30%) must be made in advance, due on receipt of the invoice, and 2 weeks before the training start date.\nb. Remainign (70%) should be paid against final invoice after delivery- Net30\nc. All prices are exclusive of taxes. Any applicable taxes must be paid directly by the buyer to the relevant authorities and must not be deducted from the NIL ME fees.\nd. The buyer is responsible for all bank transfer fees and charges related to payments made to the NIL Middle East XXXXXXXX (XXXXXXXX) bank account.\n9. Schedule changes\nNIL Middle East reserves the right to modify program start dates, cohort schedules, or exam dates without prior notice. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.\n10. Exams & Vouchers: The price does not include exam costs, NIL Middle East is not an official exam testing center and only provides exam vouchers based on separated request.\n11. Prices for training do not include students’ cost of tickets, accommodation, visa, …. Etc.\n12. NIL Middle East selects certified instructors based on quality and availability.\n13. Training Language: All training is delivered in English.\n14. Offer Validity: This offer is valid for 15 days from the date of issuance.\n\nDisclaimer:\n- Certified Courses kits ((Materials and Labs)) offered, and CLCs redeeming are provided in full cooperation with NIL Middle East’s strategic Partner and CLP “Enterone”.\n- All classes are delivered by certified instructors."


def _clc_online_terms():
    lines = []
    for line in CLC_ONSITE_TERMS.split('\n'):
        if line == '4. Catering: Not applicable.':
            continue
        if line == '2. Training Location: Instructor-Led – Onsite.':
            line = '2. Training Location: Instructor-Led – Online.'
        match = re.match(r'^(\d+)\. (.*)$', line)
        if match and int(match.group(1)) >= 5:
            line = '%s. %s' % (int(match.group(1)) - 1, match.group(2))
        lines.append(line)
    return '\n'.join(lines)


CLC_ONLINE_TERMS = _clc_online_terms()

_QUOTATION_TERMS = {
    ('clc', 'On site'): ('CLC Onsite', CLC_ONSITE_TERMS),
    ('clc', 'Online'): ('CLC Online', CLC_ONLINE_TERMS),
    ('cash', 'On site'): ('Cash Onsite', CASH_ONSITE_TERMS),
}


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _nil_terms_for_new_quotation_only(self):
        """Build complete terms from training modes, never from lead-level mode."""
        self.ensure_one()
        modes = []
        for course in self.training_course_ids:
            mode = (course.payment_method, course.location)
            # Cash Online was not provided. Never silently use the On-site text.
            if mode not in _QUOTATION_TERMS:
                return False
            if mode not in modes:
                modes.append(mode)
        if not modes:
            return False
        sections = []
        for mode in modes:
            _label, terms = _QUOTATION_TERMS[mode]
            # Keep every word, punctuation mark, line break and explicit typo.
            # Render line breaks as <br/> for both HTML forms and quotation PDFs.
            body = escape(terms).replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
            sections.append('<span>%s</span>' % body.replace('\n', '<br/>'))
        return '<br/><br/>'.join(sections)

    def action_new_quotation(self):
        """Apply terms only when CRM's standard New Quotation button is used."""
        self.ensure_one()
        action = super().action_new_quotation()
        if action.get('res_model') != 'sale.order':
            return action
        html = self._nil_terms_for_new_quotation_only()
        if html:
            context = dict(action.get('context') or {})
            context.update({
                'default_nil_new_quotation_terms': True,
                'default_term_and_cond': html,
            })
            action['context'] = context
        return action


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    nil_new_quotation_terms = fields.Boolean(
        string='Quotation Terms Set From New Quotation',
        default=False,
        copy=False,
    )

    @api.onchange('payment_method')
    def _onchange_payment_method_terms(self):
        # The preexisting onchange prepends an Instructor/Customer header.
        # Suppress it only for the precise New Quotation records, leaving
        # Work Orders, purchase orders and all other documents untouched.
        for order in self:
            if not order.nil_new_quotation_terms:
                super(SaleOrder, order)._onchange_payment_method_terms()

    def _prepare_invoice(self):
        self.ensure_one()
        values = super()._prepare_invoice()
        if self.nil_new_quotation_terms:
            # The custom sale.order logic normally forwards these terms to
            # account.move. This content belongs ONLY to the quotation.
            values.pop('term_and_cond', None)
        return values
