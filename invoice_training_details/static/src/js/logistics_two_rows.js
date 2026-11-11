/** @odoo-module **/

import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { ListRenderer } from "@web/views/list/list_renderer";

class LogisticsListRenderer extends ListRenderer {
    get getEmptyRowIds() {
        const count = Math.max(0, 2 - this.props.list.records.length - (this.displayRowCreates ? 1 : 0));
        return Array.from({ length: count }, (_, index) => index);
    }
}

class LogisticsTwoRowsField extends X2ManyField {
    static components = { ...X2ManyField.components, ListRenderer: LogisticsListRenderer };

    get rendererProps() {
        const props = super.rendererProps;
        props.activeActions = {
            ...props.activeActions,
            create: Boolean(props.activeActions.create) && this.list.count < 2,
        };
        return props;
    }

    async onAdd(params = {}) {
        if (this.list.count >= 2) {
            return;
        }
        return super.onAdd(params);
    }
}

registry.category("fields").add("logistics_two_rows", {
    ...x2ManyField,
    component: LogisticsTwoRowsField,
});
