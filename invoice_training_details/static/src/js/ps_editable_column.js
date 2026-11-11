/** @odoo-module **/

// Keep Odoo's normal x2many inline editing, adding/removing rows, and totals.
// Replace the TWO independent custom-value columns' static headers with live inputs.
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { ListRenderer } from "@web/views/list/list_renderer";

export class NilPSListRenderer extends ListRenderer {
    static template = "invoice_training_details.NilPSListRenderer";
    static props = [...ListRenderer.props, "headingRecord"];

    stopHeaderEvent(ev) {
        ev.stopPropagation();
    }

    onHeadingKeydown(ev) {
        ev.stopPropagation();
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.target.blur(); // Commits via onHeadingChange.
        }
    }

    async onHeadingChange(ev) {
        ev.stopPropagation();
        if (!this.props.headingRecord.isInEdition) {
            return;
        }
        const headingField = ev.currentTarget.dataset.headingField;
        if (!["nil_ps_custom_heading", "nil_ps_custom_heading_2"].includes(headingField)) {
            return;
        }
        const heading = ev.currentTarget.value.trim();
        if (heading !== (this.props.headingRecord.data[headingField] || "")) {
            await this.props.headingRecord.update({ [headingField]: heading });
        }
    }
}

export class NilPSX2ManyField extends X2ManyField {
    static template = "invoice_training_details.NilPSX2ManyField";
    static components = {
        ...X2ManyField.components,
        NilPSListRenderer,
    };
}

registry.category("fields").add("nil_ps_editable_column", {
    ...x2ManyField,
    component: NilPSX2ManyField,
});
