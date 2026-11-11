/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
    SelectionField,
    selectionField,
} from "@web/views/fields/selection/selection_field";

const LCP_NUMERIC_INPUT_FIELDS = [
    "lcp_vat_rate",
    "lcp_clcs_per_seat",
    "lcp_rate_card_per_seat",
    "lcp_partner_share_pct",
    "lcp_partner_cash_cost",
    "lcp_instructor_md_rate",
    "lcp_vendor_instructor_day",
    "lcp_uber_day_rate",
    "lcp_per_diem_rate",
    "lcp_per_diem_days",
    "lcp_venue_cost",
    "lcp_catering_cost",
];

export class LcpPaymentMethodResetField extends SelectionField {
    async onChange(ev) {
        const value = JSON.parse(ev.target.value);
        const previous = this.props.record.data[this.props.name];

        if (value === previous) {
            return;
        }

        // First change the payment method so the normal Odoo onchange chain runs.
        await this.props.record.update(
            { [this.props.name]: value },
            { save: this.props.autosave }
        );

        // Then explicitly clear every manual LCP numeric input in the client
        // record. This makes the reset immediate in the Training and LCP tabs
        // and does not depend on hidden-field onchange propagation.
        const resetValues = {};
        for (const fieldName of LCP_NUMERIC_INPUT_FIELDS) {
            if (fieldName in this.props.record.fields) {
                resetValues[fieldName] = 0;
            }
        }

        if (Object.keys(resetValues).length) {
            await this.props.record.update(
                resetValues,
                { save: this.props.autosave }
            );
        }
    }
}

export const lcpPaymentMethodResetField = {
    ...selectionField,
    component: LcpPaymentMethodResetField,
};

registry.category("fields").add(
    "lcp_payment_method_reset",
    lcpPaymentMethodResetField
);
