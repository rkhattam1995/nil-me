/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
    X2ManyField,
    x2ManyField,
} from "@web/views/fields/x2many/x2many_field";
import { CharField } from "@web/views/fields/char/char_field";
import { FloatField } from "@web/views/fields/float/float_field";
import { IntegerField } from "@web/views/fields/integer/integer_field";
import { MonetaryField } from "@web/views/fields/monetary/monetary_field";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { SelectionField } from "@web/views/fields/selection/selection_field";


export class LcpPerTrainingField extends X2ManyField {
    static template = "invoice_training_details.LcpPerTrainingField";

    static components = {
        CharField,
        FloatField,
        IntegerField,
        MonetaryField,
        Many2OneField,
        SelectionField,
    };

    get records() {
        return this.list.records;
    }

    trainingName(record) {
        const training = record.data.training_id;
        if (training && training[1]) {
            return training[1];
        }
        return record.data.name || "Training";
    }

    selectionLabel(record, fieldName) {
        const value = record.data[fieldName];
        const field = record.fields[fieldName];
        const selection = field && field.selection ? field.selection : [];
        const option = selection.find(([key]) => key === value);
        return option ? option[1] : "";
    }

    formatPercent(value) {
        const number = Number(value || 0);
        return `${(number * 100).toFixed(2)}%`;
    }
}


export const lcpPerTrainingField = {
    ...x2ManyField,
    component: LcpPerTrainingField,
};

registry.category("fields").add(
    "lcp_per_training",
    lcpPerTrainingField
);
