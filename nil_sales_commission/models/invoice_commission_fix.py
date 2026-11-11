# -*- coding: utf-8 -*-

from odoo import api, models

from .account_move import COMMISSION_CUTOFF_DATE


# =====================================================================
# FIXED SALESPERSON RATES
# =====================================================================

class SalesCommission(models.Model):
    _inherit = 'nil.sales.commission'

    @api.model
    def _nil_get_fixed_salesperson_rate(self, salesperson):
        """
        Fixed salesperson commission rates.

        Loudy Al Abdo = 5%
        Baraa Abo Saleh = 2%
        """
        if not salesperson:
            return 0.0

        normalized_name = self._nil_normalize_name(
            salesperson.name
        )

        if normalized_name == 'loudy al abdo':
            return 5.0

        if normalized_name == 'baraa abo saleh':
            return 2.0

        return super()._nil_get_fixed_salesperson_rate(
            salesperson
        )


# =====================================================================
# INVOICE COMMISSION SYNC
# =====================================================================

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _nil_commission_credit_notes(self):
        """
        Posted credit notes reversing this exact customer invoice.
        """
        self.ensure_one()

        if self.move_type != 'out_invoice':
            return self.env['account.move']

        return self.env['account.move'].sudo().search([
            ('move_type', '=', 'out_refund'),
            ('state', '=', 'posted'),
            ('reversed_entry_id', '=', self.id),
            ('company_id', '=', self.company_id.id),
        ])

    def _nil_commission_basis(self):
        """
        Commission basis = LCP Total Rate Card for every payment method.

        NEVER use the invoice amount, customer selling price, NIL ME share,
        revenue, profit or Cash USD/Seat to manufacture a Rate Card.
        """
        self.ensure_one()
        if self.move_type != 'out_invoice' or self.state != 'posted':
            return 0.0

        invoice_courses = self.sudo().training_course_ids
        originals = invoice_courses.mapped(
            'source_training_course_id'
        ).exists()
        lead = self._nil_get_commission_lead().sudo()

        def actual_rate_card(course):
            # Read the already computed LCP Total Rate Card. An explicitly
            # entered Rate Card/Seat and its seats are a valid equivalent.
            # Never infer a Rate Card from Selling Price or invoice revenue.
            return max(float(
                course.lcp_total_rate_card
                or course.snapshot_lcp_rate_card
                or (
                    (course.lcp_rate_card_per_seat or 0.0)
                    * max(course.no_of_student or 0, 0)
                )
                or 0.0
            ), 0.0)

        # Prefer the original CRM LCP behind each invoice training line.
        # Old invoices may lack this link, so use their saved LCP snapshot.
        if originals:
            total_rate_card = sum(
                actual_rate_card(course) for course in originals
            )
            if not total_rate_card:
                total_rate_card = sum(
                    actual_rate_card(course) for course in invoice_courses
                )
        else:
            total_rate_card = sum(
                actual_rate_card(course) for course in invoice_courses
            )

        # Do not copy an entire CRM Lead's Rate Card onto each invoice.
        # Fallback is permitted only if the Lead unambiguously belongs to
        # this ONE posted invoice. Otherwise leave the missing rate at zero.
        if not total_rate_card and lead:
            related_invoices = lead._nil_get_related_commission_invoices().filtered(
                lambda move: (
                    move.move_type == 'out_invoice'
                    and move.state == 'posted'
                    and move.company_id == self.company_id
                )
            )
            if len(related_invoices) == 1 and related_invoices.id == self.id:
                if lead.training_course_ids:
                    total_rate_card = sum(
                        actual_rate_card(course)
                        for course in lead.training_course_ids.sudo()
                    )
                if not total_rate_card:
                    total_rate_card = max(float(
                        lead.lcp_total_rate_card
                        or (
                            (lead.lcp_rate_card_per_seat or 0.0)
                            * max(lead.lcp_total_seats or 0, 0)
                        )
                        or 0.0
                    ), 0.0)

        # Credit notes proportionally reverse the commission entitlement,
        # but the commission base itself always originates from LCP Rate Card.
        invoiced = abs(float(self.amount_untaxed or 0.0))
        credited = sum(
            abs(float(move.amount_untaxed or 0.0))
            for move in self._nil_commission_credit_notes()
        )
        if invoiced and credited:
            total_rate_card *= max(
                1.0 - min(credited / invoiced, 1.0), 0.0
            )

        return max(float(total_rate_card or 0.0), 0.0)

    def _nil_prepare_auto_commission_for_update(
        self,
        commission,
        values,
        target_state,
    ):
        """
        Protect already-paid commissions.

        If a financial value changes after payment,
        reverse the old accounting entry first.
        """
        if not commission:
            return commission

        material_fields = (
            'training_value',
            'commission_rate',
            'salesperson_id',
        )

        material_change = any(
            field_name in values
            and (
                commission[field_name].id
                if commission._fields[field_name].type == 'many2one'
                else commission[field_name]
            ) != values[field_name]
            for field_name in material_fields
        )

        if commission.state == 'paid' and (
            material_change
            or target_state != 'paid'
        ):
            commission._nil_reverse_paid_entry()

            commission.with_context(
                nil_skip_paid_lock=True,
                nil_auto_sync=True,
            ).write({
                'state': 'draft',
            })

        return commission

    def _nil_sync_one_auto_commission(
        self,
        auto_key,
        salesperson,
        rate,
        common_values,
        active,
        excluded,
    ):
        """
        Maintain ONE automatic commission row
        per invoice and commission type.

        No duplicate automatic rows are created.
        """
        self.ensure_one()

        Commission = (
            self.env['nil.sales.commission']
            .sudo()
        )

        # =============================================================
        # FIND EXISTING AUTOMATIC ROW
        # =============================================================

        # The SQL unique constraint (invoice_id, auto_key) also covers
        # archived rows. A normal Odoo search hides active=False records
        # and would incorrectly reassign a legacy row to an occupied key.
        row = Commission.with_context(active_test=False).search([
            ('invoice_id', '=', self.id),
            ('auto_key', '=', auto_key),
        ], order='active desc, id asc', limit=1)

        if row and not row.active:
            # Keep the visible commission selected by deduplication,
            # without touching archived history or paid journal entries.
            visible_row = Commission._nil_existing_invoice_commission(self)
            if visible_row:
                return visible_row

            # When nothing is visible, reuse an eligible archived,
            # unpaid auto row instead of creating a duplicate SQL key.
            # Never reactivate a paid historical record via sync.
            if not active or excluded or row.state == 'paid':
                return row
            row.with_context(
                nil_auto_sync=True,
                nil_skip_paid_lock=True,
            ).write({'active': True})

        # =============================================================
        # FIND LEGACY AUTOMATIC ROWS
        #
        # Older module versions may have created automatic rows
        # without auto_key.
        #
        # For fixed-rate salespeople and Ruba we can safely identify
        # the old automatic rows and reuse them.
        # =============================================================

        legacy_rows = Commission.browse()

        if (
            auto_key == 'ruba'
            or rate > 0.0
        ):
            legacy_rows = Commission.search([
                ('invoice_id', '=', self.id),
                ('auto_key', '=', False),
                (
                    'salesperson_id',
                    '=',
                    salesperson.id
                    if salesperson
                    else False,
                ),
                ('commission_rate', '=', rate),
                (
                    'is_auto_ruba',
                    '=',
                    auto_key == 'ruba',
                ),
            ], order='id asc')

        # =============================================================
        # ADOPT ONE OLD ROW
        # =============================================================

        if not row and legacy_rows:

            paid_legacy_rows = (
                legacy_rows.filtered(
                    lambda rec:
                        rec.state == 'paid'
                )
            )

            row = (
                paid_legacy_rows[:1]
                if paid_legacy_rows
                else legacy_rows[:1]
            )

            row.with_context(
                nil_auto_sync=True,
                nil_skip_paid_lock=True,
            ).write({
                'auto_key': auto_key,
                'is_auto_ruba':
                    auto_key == 'ruba',
            })

        # =============================================================
        # REMOVE OLD NON-PAID DUPLICATES
        #
        # Paid historical rows are NEVER automatically deleted.
        # =============================================================

        if row and legacy_rows:

            duplicate_rows = (
                legacy_rows - row
            )

            unpaid_duplicates = (
                duplicate_rows.filtered(
                    lambda rec:
                        rec.state != 'paid'
                )
            )

            if unpaid_duplicates:
                unpaid_duplicates.with_context(
                    nil_sync_cleanup=True
                ).unlink()

        # =============================================================
        # TARGET STATUS
        # =============================================================

        salesperson_changed = bool(
            row
            and auto_key == 'salesperson'
            and row.salesperson_id != salesperson
        )

        if excluded:
            target_state = 'excluded'

        elif not active:
            target_state = 'cancelled'

        elif (
            salesperson_changed
            and row
            and row.state == 'excluded'
        ):
            # A new salesperson must get a new management decision.
            target_state = 'draft'

        elif (
            row
            and row.state in (
                'pending',
                'excluded',
                'paid',
            )
        ):
            # Preserve management decision.
            target_state = row.state

        else:
            target_state = 'draft'

        # =============================================================
        # VALUES
        # =============================================================

        values = dict(common_values)

        values.update({
            'salesperson_id': (
                salesperson.id
                if salesperson
                else False
            ),
            'commission_rate': rate,
            'auto_key': auto_key,
            'is_auto_ruba':
                auto_key == 'ruba',
            'excluded_by_invoice':
                bool(excluded),
        })

        # =============================================================
        # CREATE NEW ROW
        # =============================================================

        if not row:

            if not active or excluded:
                return Commission

            # One invoice, one active commission. Respect any existing
            # manual/legacy/other salesperson row, regardless of auto_key.
            # Never create a second invoice line with a different owner.
            existing_invoice_row = Commission._nil_existing_invoice_commission(
                self
            )
            if existing_invoice_row:
                return existing_invoice_row

            values['state'] = 'draft'

            return Commission.with_context(
                nil_auto_sync=True
            ).create(values)

        # Changing the basis must not automatically reverse previously
        # settled accounting entries. Credit notes remain actionable.
        if (
            row.state == 'paid'
            and self.state == 'posted'
            and self.invoice_date
            and self.invoice_date > COMMISSION_CUTOFF_DATE
            and not excluded
            and not self._nil_commission_credit_notes()
        ):
            return row

        # =============================================================
        # PAID ROW CHECK
        # =============================================================

        if (
            row.state == 'paid'
            and active
            and not excluded
        ):

            expected_amount = (
                (values['training_value'] or 0.0)
                * (rate or 0.0)
                / 100.0
            )

            unchanged = (
                abs(
                    (row.training_value or 0.0)
                    - (
                        values['training_value']
                        or 0.0
                    )
                ) < 0.000001

                and abs(
                    (row.commission_rate or 0.0)
                    - (rate or 0.0)
                ) < 0.000001

                and (
                    row.salesperson_id
                    == salesperson
                )

                and abs(
                    (
                        row.commission_amount
                        or 0.0
                    )
                    - expected_amount
                ) < 0.000001
            )

            if unchanged:
                target_state = 'paid'
            else:
                target_state = 'draft'

        # =============================================================
        # UPDATE EXISTING ROW
        # =============================================================

        row = (
            self
            ._nil_prepare_auto_commission_for_update(
                row,
                values,
                target_state,
            )
        )

        write_values = dict(values)

        if row.state != 'paid':
            write_values['state'] = (
                target_state
            )

        row.with_context(
            nil_auto_sync=True,
            nil_skip_paid_lock=True,
        ).write(write_values)

        return row

    def _nil_sync_sales_commission(self):
        """
        FINAL COMMISSION RULES

        1. Every eligible posted Customer Invoice is checked.

        2. If the Invoice has a Salesperson,
           that invoice MUST appear in the Commission Ledger.

        3. Loudy Al Abdo = 5%.

        4. Baraa Abo Saleh = 2%.

        5. Other salespeople still appear in the ledger.

        6. New salesperson commissions start as Draft.

        7. Management decides:
           Approve
           or
           Exclude

        8. One automatic salesperson commission per invoice.
           Re-sync never creates another one.

        9. Ruba commissions are disabled.
        """

        Commission = (
            self.env['nil.sales.commission']
            .sudo()
        )

        for invoice in self:

            # =========================================================
            # CUSTOMER INVOICE ONLY
            # =========================================================

            if invoice.move_type != 'out_invoice':
                continue

            # =========================================================
            # CRM LEAD
            # =========================================================

            lead = (
                invoice
                ._nil_get_commission_lead()
            )

            # =========================================================
            # SALESPERSON
            #
            # IMPORTANT:
            # Use the Salesperson ON THE INVOICE.
            # =========================================================

            salesperson = (
                invoice.invoice_user_id.sudo()
                if invoice.invoice_user_id
                else self.env['res.users']
            )

            # =========================================================
            # COMMISSION BASIS
            # =========================================================

            basis = (
                invoice
                ._nil_commission_basis()
            )

            # =========================================================
            # DATE RULE
            # =========================================================

            date_allowed = bool(
                invoice.invoice_date
                and (
                    invoice.invoice_date
                    > COMMISSION_CUTOFF_DATE
                )
            )

            # =========================================================
            # ACTIVE COMMISSION
            # =========================================================

            active = bool(
                invoice.state == 'posted'
                and date_allowed
                and basis > 0.0
            )

            excluded = bool(
                invoice.exclude_from_commission
            )

            # =========================================================
            # COMMON VALUES
            # =========================================================

            common_values = {
                'invoice_id':
                    invoice.id,

                'lead_id':
                    lead.id
                    if lead
                    else False,

                'customer_id': (
                    lead.partner_id.id
                    if (
                        lead
                        and lead.partner_id
                    )
                    else
                    invoice.partner_id.id
                    if invoice.partner_id
                    else False
                ),

                'company_id':
                    invoice.company_id.id,

                'currency_id':
                    invoice.currency_id.id,

                'commission_date':
                    invoice.invoice_date,

                'training_value':
                    basis,
            }

            # Ruba is no longer eligible. Keep paid historical journal
            # entries for audit; cancel unpaid legacy automatic rows.
            old_ruba_rows = Commission.search([
                ('invoice_id', '=', invoice.id),
                '|',
                ('auto_key', '=', 'ruba'),
                ('is_auto_ruba', '=', True),
            ])
            for row in old_ruba_rows.filtered(
                lambda rec: rec.state not in ('paid', 'cancelled')
            ):
                row.with_context(
                    nil_auto_sync=True,
                    nil_skip_paid_lock=True,
                ).write({'state': 'cancelled'})

            # =========================================================
            # SALESPERSON COMMISSION
            #
            # EVERY INVOICE WITH A SALESPERSON APPEARS.
            # =========================================================

            existing_salesperson_row = (
                Commission.with_context(active_test=False).search([
                    (
                        'invoice_id',
                        '=',
                        invoice.id,
                    ),
                    (
                        'auto_key',
                        '=',
                        'salesperson',
                    ),
                ], order='active desc, id asc', limit=1)
            )

            is_ruba_salesperson = bool(
                salesperson
                and
                Commission._nil_normalize_name(
                    salesperson.name
                ) == 'ruba khattam'
            )

            if (
                salesperson
                and not is_ruba_salesperson
            ):

                fixed_rate = (
                    Commission
                    ._nil_get_fixed_salesperson_rate(
                        salesperson
                    )
                )

                # -----------------------------------------------------
                # FIXED RATES
                #
                # Loudy Al Abdo = 5%
                # Baraa Abo Saleh = 2%
                # -----------------------------------------------------

                if fixed_rate > 0.0:
                    salesperson_rate = (
                        fixed_rate
                    )

                # -----------------------------------------------------
                # OTHER SALESPERSON
                #
                # Keep an existing commission rate if one was already
                # entered. Otherwise the row starts at 0%.
                #
                # The invoice STILL appears for management review.
                # -----------------------------------------------------

                elif (
                    existing_salesperson_row
                    and
                    existing_salesperson_row.salesperson_id
                    == salesperson
                ):
                    salesperson_rate = (
                        existing_salesperson_row
                        .commission_rate
                        or 0.0
                    )

                else:
                    salesperson_rate = 0.0

                invoice._nil_sync_one_auto_commission(
                    'salesperson',
                    salesperson,
                    salesperson_rate,
                    common_values,
                    active,
                    excluded,
                )

            # =========================================================
            # NO SALESPERSON / RUBA IS THE SALESPERSON
            #
            # Ruba already has her dedicated automatic 1% row.
            # Do not create a second generic salesperson row for her.
            # Clean any old non-paid generic Ruba row during re-sync.
            # =========================================================

            elif (
                existing_salesperson_row
                and
                existing_salesperson_row.state
                != 'paid'
            ):

                existing_salesperson_row.with_context(
                    nil_sync_cleanup=True
                ).unlink()

        return True

    def _nil_commission_impacted_invoices(self):
        """
        Return invoices affected by invoice/refund changes.
        """

        impacted = (
            self.env['account.move']
        )

        for move in self:

            if move.move_type == 'out_invoice':
                impacted |= move

            elif (
                move.move_type == 'out_refund'
                and move.reversed_entry_id
            ):
                impacted |= (
                    move.reversed_entry_id
                )

        return impacted

    def _nil_sync_commission_impacts(self):
        """
        Re-sync affected invoices.
        """

        impacted = (
            self
            ._nil_commission_impacted_invoices()
        )

        if impacted:
            impacted._nil_sync_sales_commission()

        return True

    def action_post(self):
        result = super().action_post()

        self._nil_sync_commission_impacts()

        return result

    def write(self, vals):
        result = super().write(vals)

        watched = {
            'state',
            'invoice_date',
            'invoice_user_id',
            'partner_id',
            'currency_id',
            'invoice_origin',
            'exclude_from_commission',
            'reversed_entry_id',
        }

        if watched.intersection(vals):
            self._nil_sync_commission_impacts()

        return result

    def button_draft(self):
        result = super().button_draft()

        self._nil_sync_commission_impacts()

        return result

    def button_cancel(self):
        result = super().button_cancel()

        self._nil_sync_commission_impacts()

        return result
