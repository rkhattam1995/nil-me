# -*- coding: utf-8 -*-
"""Quotation-only terms. Do not use for New WO, POs, invoices or global defaults."""

from html import escape
import re

from odoo import api, fields, models


# Preserve original legal wording exactly, but never store CLC clause numbers
# as part of the editable text. HTML lists generate the numbers in the editor.
# Online differs only in delivery mode and removal of On-site Catering.
CLC_ONSITE_TERMS = (
    "All NIL Middle East (NIL ME) terms and conditions apply; by accepting this quotation, you are accepting all terms with no exceptions.",
    "Training Location: Instructor-Led – Onsite.",
    "Trainees should use their own laptops for training.",
    "Catering: Not applicable.",
    "Cancellation Policy: Cancellations made at least 2 weeks prior to the start date will incur no charges. Cancellations made within 2 weeks of the start date will incur a 100% cancellation fee.",
    "Participant Changes: Changes or replacements of participant names or email addresses are permitted only if requested at least 2 weeks before the start date.",
    "Purchase Order and Payment: For CLC-based orders, there is no need for an official customer purchase order. Instead, an email accepting the quotation shall be shared with NIL Middle East with the following information included:",
    "All CLC prices are inclusive of VAT. Any other applicable taxes must be paid directly by the buyer to the relevant authorities and must not be deducted from the NIL ME fees.",
    "Schedule Changes: NIL Middle East reserves the right to modify program start dates and schedules. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.",
    "Exams & Vouchers: The price does not include exam costs. NIL ME is not an exam or testing center.",
    "Prices for training do not include students’ costs for tickets, accommodation, visa, etc.",
    "NIL Middle East selects certified instructors based on quality and availability.",
    "Training Language: All training is delivered in English.",
    "Offer Validity: This offer is valid until 15 days from the date of issuance.",
)

# CLC Online has no catering; only the delivery location wording differs.
CLC_ONLINE_TERMS = tuple(
    'Training Location: Instructor-Led – Online.'
    if clause == 'Training Location: Instructor-Led – Onsite.'
    else clause
    for clause in CLC_ONSITE_TERMS
    if clause != 'Catering: Not applicable.'
)

CLC_PAYMENT_SUBITEMS = (
    "SO#",
    "Available CLCs in the SO#",
    "Expiry date of the CLCs",
)

CLC_DISCLAIMER_BULLETS = (
    "Certified Courses kits ((Materials and Labs)) offered, and CLCs redeeming are provided in full cooperation with NIL Middle East’s strategic Partner and CLP “Enterone”.",
    "All classes are delivered by certified instructors.",
)

# Cash Onsite legal text. Ordered clause numbers come from editor lists only.
CASH_ONSITE_TERMS = (
    "All NIL Middle East (NIL ME) terms and conditions apply.",
    "Trainees should use their own laptop for the training.",
    "Training Location: Onsite at customer office in XXXXXXXX. Customers must secure good internet access for the students and the instructor.",
    "Catering included in NIL ME offer.",
    "Cancellation Policy:",
    "Changes or replacements of participant names or email addresses are permitted only if requested at least 2 weeks before the start date.",
    "Schedule Changes: NIL Middle East reserves the right to modify program start dates, cohort schedules, or exam dates without prior notice. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.",
    "Payment:",
    "Schedule changes\nNIL Middle East reserves the right to modify program start dates, cohort schedules, or exam dates without prior notice. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.",
    "Exams & Vouchers: The price does not include exam costs, NIL Middle East is not an official exam testing center and only provides exam vouchers based on separated request.",
    "Prices for training do not include students’ cost of tickets, accommodation, visa, …. Etc.",
    "NIL Middle East selects certified instructors based on quality and availability.",
    "Training Language: All training is delivered in English.",
    "Offer Validity: This offer is valid for 15 days from the date of issuance.",
)


# Native bullet list nested under Cancellation Policy.
CASH_CANCELLATION_BULLETS = (
    "Cancellations made at least 2 weeks prior to the program start date will incur no charges.",
    "Cancellations made within 2 weeks of the start date will incur a 100% cancellation fee.",
)


# Native alphabetic list nested under Payment.
CASH_PAYMENT_SUBITEMS = (
    "Full payment (30%) must be made in advance, due on receipt of the invoice, and 2 weeks before the training start date.",
    "Remainign (70%) should be paid against final invoice after delivery- Net30",
    "All prices are exclusive of taxes. Any applicable taxes must be paid directly by the buyer to the relevant authorities and must not be deducted from the NIL ME fees.",
    "The buyer is responsible for all bank transfer fees and charges related to payments made to the NIL Middle East XXXXXXXX (XXXXXXXX) bank account.",
)


# Native bullet list under Disclaimer.
CASH_DISCLAIMER_BULLETS = (
    "Certified Courses kits ((Materials and Labs)) offered, and CLCs redeeming are provided in full cooperation with NIL Middle East’s strategic Partner and CLP “Enterone”.",
    "All classes are delivered by certified instructors.",
)


# Cash Online: independently preserve the supplied 13 clauses, without Catering.
CASH_ONLINE_TERMS = (
    "All NIL Middle East (NIL ME) terms and conditions apply.",
    "Trainees should use their own laptop for the training.",
    "Training Location: Onsite at customer office in XXXXXXXX. Customers must secure good internet access for the students and the instructor.",
    "Cancellation Policy:",
    "Changes or replacements of participant names or email addresses are permitted only if requested at least 2 weeks before the start date.",
    "Schedule Changes: NIL Middle East reserves the right to modify program start dates, cohort schedules, or exam dates without prior notice. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.",
    "Payment:",
    "Schedule changes\nNIL Middle East reserves the right to modify program start dates, cohort schedules, or exam dates without prior notice. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.",
    "Exams & Vouchers: The price does not include exam costs, NIL Middle East is not an official exam testing center and only provides exam vouchers based on separated request.",
    "Prices for training do not include students’ cost of tickets, accommodation, visa, …. Etc.",
    "NIL Middle East selects certified instructors based on quality and availability.",
    "Training Language: All training is delivered in English.",
    "Offer Validity: This offer is valid for 15 days from the date of issuance.",
)

# The four Cash Online Payment items use the customer's exact wording.
CASH_ONLINE_PAYMENT_BULLETS = (
    "Full payment (30%) must be made in advance, due on receipt of the invoice, and 2 weeks before the training start date.",
    "Remaining (70%) should be paid against final invoice after delivery- Net30",
    "All prices are exclusive of taxes. Any applicable taxes must be paid directly by the buyer to the relevant authorities and must not be deducted from the NIL ME fees.",
    "The buyer is responsible for all bank transfer fees and charges related to payments made to the NIL Middle East XXXXXXXX (XXXXXXXX) bank account.",
)


def _clc_terms_html(clauses, expected_clauses, payment_numbering='lower-alpha'):
    """Use native editor <ol>/<li> numbering, never visible text prefixes.

    Both CLC modes share one editable numbered list, with a native nested
    Payment list (decimal for Online, alphabetic for Onsite) and Disclaimer bullets.
    """
    if len(clauses) != expected_clauses:
        raise ValueError('CLC Terms clause count differs from the template')

    html = [
        '<p><strong>Terms &amp; Conditions:</strong></p>',
        '<ol style="list-style-type:decimal;padding-left:28px;">',
    ]
    payment_sections = 0

    for clause in clauses:
        html.append('<li>%s' % escape(clause))
        if clause.startswith('Purchase Order and Payment:'):
            payment_sections += 1
            if payment_numbering == 'decimal':
                html.append('<ol style="list-style-type:decimal;padding-left:28px;">')
            else:
                html.append('<ol type="a" style="list-style-type:lower-alpha;padding-left:28px;">')
            for text in CLC_PAYMENT_SUBITEMS:
                html.append('<li>%s</li>' % escape(text))
            html.append('</ol>')
        html.append('</li>')

    if payment_sections != 1 or len(CLC_PAYMENT_SUBITEMS) != 3:
        raise ValueError('The CLC Payment sublist must contain three entries')
    if len(CLC_DISCLAIMER_BULLETS) != 2:
        raise ValueError('The CLC Disclaimer must contain two bullet items')

    html.extend([
        '</ol>',
        '<p><strong>Disclaimer:</strong></p>',
        '<ul style="list-style-type:disc;padding-left:28px;">',
    ])
    for text in CLC_DISCLAIMER_BULLETS:
        html.append('<li>%s</li>' % escape(text))
    html.append('</ul>')
    return ''.join(html)


def _clc_online_terms_html():
    return _clc_terms_html(CLC_ONLINE_TERMS, 13, payment_numbering='decimal')


def _clc_onsite_terms_html():
    return _clc_terms_html(CLC_ONSITE_TERMS, 14)


# Native HTML lists are compatible with the existing Terms editor.
_CASH_BOLD_HEADINGS = (
    'Training Location:',
    'Catering',
    'Cancellation Policy:',
    'Schedule Changes:',
    'Payment:',
    'Schedule changes',
    'Exams & Vouchers:',
    'Training Language:',
    'Offer Validity:',
)


def _cash_heading_html(text):
    for heading in _CASH_BOLD_HEADINGS:
        if text.startswith(heading):
            return '<strong>%s</strong>%s' % (
                escape(heading),
                escape(text[len(heading):]).replace('\n', '<br/>'),
            )
    return escape(text).replace('\n', '<br/>')


def _cash_onsite_terms_html():
    """All numbering is native to the editable ordered/unordered lists."""
    if len(CASH_ONSITE_TERMS) != 14:
        raise ValueError('Cash Onsite Terms must have exactly 14 clauses')
    if (len(CASH_CANCELLATION_BULLETS) != 2
            or len(CASH_PAYMENT_SUBITEMS) != 4
            or len(CASH_DISCLAIMER_BULLETS) != 2):
        raise ValueError('Cash Onsite Terms have invalid sublists')

    html = [
        '<p><strong>General Terms &amp; Conditions:</strong></p>',
        '<ol style="list-style-type:decimal;padding-left:28px;">',
    ]
    cancellation_count = 0
    payment_count = 0
    catering_count = 0

    for clause in CASH_ONSITE_TERMS:
        # Color this list item, INCLUDING its automatically generated "4.".
        is_catering = clause == 'Catering included in NIL ME offer.'
        item_style = ' style="color:#ff0000;"' if is_catering else ''
        catering_count += int(is_catering)
        html.append('<li%s>%s' % (item_style, _cash_heading_html(clause)))

        if clause == 'Cancellation Policy:':
            cancellation_count += 1
            html.append('<ul style="list-style-type:disc;padding-left:28px;">')
            for text in CASH_CANCELLATION_BULLETS:
                html.append('<li>%s</li>' % escape(text))
            html.append('</ul>')

        if clause == 'Payment:':
            payment_count += 1
            html.append(
                '<ol type="a" style="list-style-type:lower-alpha;padding-left:28px;">'
            )
            for text in CASH_PAYMENT_SUBITEMS:
                html.append('<li>%s</li>' % escape(text))
            html.append('</ol>')

        html.append('</li>')

    if (cancellation_count != 1 or payment_count != 1
            or catering_count != 1):
        raise ValueError('Cash Onsite special clauses are missing or duplicated')

    html.extend([
        '</ol>',
        '<p><strong>Disclaimer:</strong></p>',
        '<ul style="list-style-type:disc;padding-left:28px;">',
    ])
    for text in CASH_DISCLAIMER_BULLETS:
        html.append('<li>%s</li>' % escape(text))
    html.append('</ul>')
    return ''.join(html)


def _cash_online_terms_html():
    """Native editable numbered main list, with nested bullet lists."""
    if len(CASH_ONLINE_TERMS) != 13:
        raise ValueError('Cash Online Terms must have exactly 13 clauses')
    if (len(CASH_CANCELLATION_BULLETS) != 2
            or len(CASH_ONLINE_PAYMENT_BULLETS) != 4
            or len(CASH_DISCLAIMER_BULLETS) != 2):
        raise ValueError('Cash Online Terms have invalid sublists')

    html = [
        '<p><strong>General Terms &amp; Conditions:</strong></p>',
        '<ol style="list-style-type:decimal;padding-left:28px;">',
    ]
    cancellation_count = 0
    payment_count = 0

    for clause in CASH_ONLINE_TERMS:
        html.append('<li>%s' % _cash_heading_html(clause))

        if clause == 'Cancellation Policy:':
            cancellation_count += 1
            html.append('<ul style="list-style-type:disc;padding-left:28px;">')
            for text in CASH_CANCELLATION_BULLETS:
                html.append('<li>%s</li>' % escape(text))
            html.append('</ul>')

        if clause == 'Payment:':
            payment_count += 1
            html.append('<ul style="list-style-type:disc;padding-left:28px;">')
            for text in CASH_ONLINE_PAYMENT_BULLETS:
                html.append('<li>%s</li>' % escape(text))
            html.append('</ul>')

        html.append('</li>')

    if cancellation_count != 1 or payment_count != 1:
        raise ValueError('Cash Online special clauses are missing or duplicated')

    html.extend([
        '</ol>',
        '<p><strong>Disclaimer:</strong></p>',
        '<ul style="list-style-type:disc;padding-left:28px;">',
    ])
    for text in CASH_DISCLAIMER_BULLETS:
        html.append('<li>%s</li>' % escape(text))
    html.append('</ul>')
    return ''.join(html)


_QUOTATION_TERMS = {
    ('clc', 'On site'): ('CLC Onsite', CLC_ONSITE_TERMS),
    ('clc', 'Online'): ('CLC Online', CLC_ONLINE_TERMS),
    ('cash', 'On site'): ('Cash Onsite', CASH_ONSITE_TERMS),
    ('cash', 'Online'): ('Cash Online', CASH_ONLINE_TERMS),
}


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _nil_terms_for_new_quotation_only(self):
        """Build complete terms from training modes, never from lead-level mode."""
        self.ensure_one()
        modes = []
        for course in self.training_course_ids:
            mode = (course.payment_method, course.location)
            # Never substitute terms from a different payment/delivery mode.
            if mode not in _QUOTATION_TERMS:
                return False
            if mode not in modes:
                modes.append(mode)
        if not modes:
            return False
        sections = []
        for mode in modes:
            _label, terms = _QUOTATION_TERMS[mode]
            if mode == ('cash', 'On site'):
                sections.append(_cash_onsite_terms_html())
                continue
            if mode == ('cash', 'Online'):
                sections.append(_cash_online_terms_html())
                continue
            if mode == ('clc', 'Online'):
                sections.append(_clc_online_terms_html())
                continue
            if mode == ('clc', 'On site'):
                sections.append(_clc_onsite_terms_html())
                continue
        return '<br/><br/>'.join(sections)

    def action_new_quotation(self):
        """Apply quotation terms and default CLC pricelist only to New Quotation."""
        self.ensure_one()
        action = super().action_new_quotation()
        if action.get('res_model') != 'sale.order':
            return action

        context = dict(action.get('context') or {})
        html = self._nil_terms_for_new_quotation_only()
        if html:
            context.update({
                'default_nil_new_quotation_terms': True,
                'default_term_and_cond': html,
            })

        # A CLC-only CRM training quotation must open with its CLC pricelist.
        # Do not override the customer's usual pricelist for Cash/mixed leads.
        courses = self.training_course_ids
        if courses and all(course.payment_method == 'clc' for course in courses):
            company_id = self.company_id.id or self.env.company.id
            pricelists = self.env['product.pricelist'].search([
                ('active', '=', True),
                ('company_id', 'in', [False, company_id]),
                ('name', 'ilike', 'CLC'),
            ])
            clc_pricelists = pricelists.filtered(
                lambda pricelist: re.search(
                    r'\\bCLCS?\\b', pricelist.name or '', re.IGNORECASE
                )
            )
            exact = clc_pricelists.filtered(
                lambda pricelist: (pricelist.name or '').strip().casefold()
                in ('clc', 'clcs')
            )
            clc_pricelist = (exact or clc_pricelists)[:1]
            if clc_pricelist:
                context['default_pricelist_id'] = clc_pricelist.id

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
