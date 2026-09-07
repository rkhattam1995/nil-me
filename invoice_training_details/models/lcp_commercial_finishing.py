# -*- coding: utf-8 -*-

from html import escape

from odoo import api, fields, models


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    def _lcp_sync_clc_price_to_rate_card(self):
        """CLC Training Price must always equal Total Rate Card."""
        for line in self.filtered(lambda rec: rec.payment_method == 'clc'):
            total_rate_card = (
                (line.lcp_rate_card_per_seat or 0.0)
                * max(line.no_of_student or 0, 0)
            )
            if abs((line.price or 0.0) - total_rate_card) > 0.01:
                line.with_context(skip_lcp_clc_price_sync=True).write({
                    'price': total_rate_card,
                })

    @api.onchange('payment_method', 'no_of_student', 'lcp_rate_card_per_seat')
    def _onchange_lcp_clc_price_to_rate_card(self):
        for line in self:
            if line.payment_method == 'clc':
                line.price = (
                    (line.lcp_rate_card_per_seat or 0.0)
                    * max(line.no_of_student or 0, 0)
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_lcp_clc_price_sync'):
            records._lcp_sync_clc_price_to_rate_card()
        return records

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get('skip_lcp_clc_price_sync'):
            self._lcp_sync_clc_price_to_rate_card()
        return result


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    students_details = fields.Html(string="Students' Details")

    def _lcp_html_table(self, title, rows):
        """Compact table matching the Training table palette."""
        rendered_rows = []
        for row in rows:
            if len(row) == 4:
                label, value, shaded, merged = row
            else:
                label, value, shaded = row
                merged = False

            background = 'background:#EAF9FC;' if shaded else 'background:#fff;'
            if merged:
                rendered_rows.append(
                    '<tr><td colspan="2" style="padding:8px 11px;border:1px solid #cfe5ea;'
                    'font-family:Arial,Helvetica,sans-serif;font-size:16px;font-weight:700;'
                    'text-align:center;white-space:nowrap;{0}">{1}</td></tr>'.format(
                        background,
                        escape(label),
                    )
                )
            else:
                rendered_rows.append(
                    '<tr>'
                    '<td style="padding:8px 11px;border:1px solid #cfe5ea;'
                    'font-family:Arial,Helvetica,sans-serif;font-size:16px;font-weight:700;'
                    'white-space:nowrap;{0}">{1}</td>'
                    '<td style="padding:8px 11px;border:1px solid #cfe5ea;'
                    'font-family:Arial,Helvetica,sans-serif;font-size:16px;font-weight:400;'
                    'text-align:right;white-space:nowrap;{0}">{2}</td>'
                    '</tr>'.format(
                        background,
                        escape(label),
                        value,
                    )
                )

        title_html = ''
        if title:
            title_html = (
                '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;'
                'font-weight:700;color:#075E68;margin-bottom:6px;">%s</div>'
                % escape(title)
            )

        return (
            '<div style="margin-top:12px;page-break-inside:avoid;'
            'font-family:Arial,Helvetica,sans-serif;font-size:16px;">'
            '%s'
            '<table style="width:auto;display:inline-table;border-collapse:collapse;'
            'table-layout:auto;font-family:Arial,Helvetica,sans-serif;font-size:16px;'
            'font-weight:400;"><tbody>%s</tbody></table>'
            '</div>'
        ) % (title_html, ''.join(rendered_rows))

    def _lcp_enterone_so_terms(self, courses):
        self.ensure_one()
        end_customer = self.training_name.display_name if self.training_name else ''
        blocks = [
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;'
            'font-weight:400;line-height:1.45;margin-bottom:10px;">'
            '<strong>End Customer:</strong> %s'
            '</div>' % escape(end_customer)
        ]

        for course in courses.filtered(lambda c: c.payment_method == 'clc'):
            online = course.location == 'Online'
            total_revenue = course.lcp_total_rate_card or 0.0
            flight = 0.0 if online else (course.lcp_ticket_total or 0.0)
            hotel = 0.0 if online else (course.lcp_hotel_total or 0.0)
            instructor = (
                (course.lcp_total_instructor_md or 0.0)
                if course.lcp_instructor_source == 'nil_me'
                else 0.0
            )
            net = max(total_revenue - flight - hotel - instructor, 0.0)
            enterone = net * 0.20
            nilme = net * 0.80
            nilme_invoice = nilme + flight + hotel + instructor

            rows = [
                ('Total Revenue', self._lcp_money(total_revenue), True),
                ('Deductible Amounts', '', True, True),
            ]
            if not online:
                rows.extend([
                    ('Flight', self._lcp_money(flight), False),
                    ('Hotel', self._lcp_money(hotel), False),
                ])
            if instructor:
                rows.append((
                    'NIL ME Instructor',
                    self._lcp_money(instructor),
                    False,
                ))
            rows.extend([
                ('Total', self._lcp_money(net), True),
                ('EnterOne Share 20%', self._lcp_money(enterone), False),
                ('NIL ME Share 80%', self._lcp_money(nilme), False),
                ('NIL ME Invoice', self._lcp_money(nilme_invoice), True),
            ])
            blocks.append(self._lcp_html_table('', rows))

        blocks.append(
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;'
            'font-weight:400;line-height:1.45;margin-top:14px;">'
            '<strong>Participants\' Details:</strong>'
            '</div>'
        )
        if self.students_details:
            blocks.append(
                '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;'
                'line-height:1.45;margin-top:6px;">%s</div>'
                % self.students_details
            )

        return ''.join(blocks)

    def _lcp_sale_lines(self, courses, company):
        lines = super()._lcp_sale_lines(courses, company)

        # EnterOne CLC SO amount = NIL ME 80% share of the remaining Rate Card
        # + NIL ME instructor + flight + hotel.
        for course, command in zip(courses, lines):
            if not (
                course.payment_method == 'clc'
                and course.lcp_cost_learning_partner == 'EnterOne'
            ):
                continue

            online = course.location == 'Online'
            rate_card = course.lcp_total_rate_card or 0.0
            flight = 0.0 if online else (course.lcp_ticket_total or 0.0)
            hotel = 0.0 if online else (course.lcp_hotel_total or 0.0)
            instructor = (
                (course.lcp_total_instructor_md or 0.0)
                if course.lcp_instructor_source == 'nil_me'
                else 0.0
            )
            remaining = max(rate_card - flight - hotel - instructor, 0.0)
            nilme_invoice = (
                (remaining * 0.80)
                + instructor
                + flight
                + hotel
            )
            command[2]['price_unit'] = nilme_invoice

        return lines


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    bank_details = fields.Html(default=False)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if 'bank_details' in fields_list:
            vals['bank_details'] = False
        return vals
