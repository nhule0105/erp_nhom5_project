/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import {
    SaleOrderLineProductField,
    saleOrderLineProductField,
} from "@sale/js/sale_product_field";
import {
    ProductLabelSectionAndNoteFieldAutocomplete,
} from "@account/components/product_label_section_and_note_field/product_label_section_and_note_field";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, useEffect, useState } from "@odoo/owl";

const SERIAL_SELECTION_EVENT = "custom_sales_serial_selection";
const LINE_SERIAL_SELECTION_EVENT = "custom_sales_line_serial_selection";
let activeSerialSearchToken = null;

export class SerialPickerDialog extends Component {
    static template = "custom_sales.SerialPickerDialog";
    static components = { Dialog };
    static props = {
        productName: String,
        serials: Array,
        initialSelection: { type: Array, optional: true },
        onSelected: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            selectedIds: [...(this.props.initialSelection || [])],
            searchTerm: "",
        });
    }

    get filteredSerials() {
        const searchTerm = this.state.searchTerm.trim().toLocaleLowerCase();
        if (!searchTerm) {
            return this.props.serials;
        }
        return this.props.serials.filter((serial) =>
            [serial.name, serial.status_label, serial.lifecycle_status_label]
                .filter(Boolean)
                .some((value) => value.toLocaleLowerCase().includes(searchTerm))
        );
    }

    onSearchInput(event) {
        this.state.searchTerm = event.target.value;
    }

    isSelected(serialId) {
        return this.state.selectedIds.includes(serialId);
    }

    toggleSerial(serial) {
        if (!serial.selectable) {
            return;
        }
        this.state.selectedIds = this.isSelected(serial.id)
            ? this.state.selectedIds.filter((id) => id !== serial.id)
            : [...this.state.selectedIds, serial.id];
    }

    async confirm() {
        await this.props.onSelected(this.state.selectedIds);
        this.props.close();
    }
}

export class SerialCountField extends Component {
    static template = "custom_sales.SerialCountField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.addDialog = useOwnedDialogs();
        this.state = useState({ loading: false });
    }

    get value() {
        return this.props.record.data[this.props.name] || 0;
    }

    async openSerials(event) {
        event.stopPropagation();
        event.preventDefault();
        if (this.state.loading || !this.value) {
            return;
        }
        this.state.loading = true;
        try {
            const serials = await this.orm.call(
                this.props.record.resModel,
                "get_serial_picker_data",
                [[this.props.record.resId]]
            );
            this.addDialog(SerialPickerDialog, {
                productName: this.props.record.data.display_name || this.props.record.data.name,
                serials,
                onSelected: (lotIds) => {
                    if (lotIds.length) {
                        this.env.bus.trigger(SERIAL_SELECTION_EVENT, {
                            productModel: this.props.record.resModel,
                            productId: this.props.record.resId,
                            searchToken: activeSerialSearchToken,
                            lotIds,
                        });
                    }
                },
            });
        } finally {
            this.state.loading = false;
        }
    }
}

export class SerialLotPickerField extends Component {
    static template = "custom_sales.SerialLotPickerField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.addDialog = useOwnedDialogs();
        this.state = useState({ loading: false });
    }

    get productId() {
        return this.props.record.data.product_id?.[0];
    }

    get selectedIds() {
        return this.props.record.data[this.props.name].records.map(
            (record) => record.resId
        );
    }

    async openSerials(event) {
        event.stopPropagation();
        event.preventDefault();
        if (this.state.loading || !this.productId) {
            return;
        }
        this.state.loading = true;
        try {
            const serials = await this.orm.call(
                "product.product",
                "get_serial_picker_data",
                [[this.productId]]
            );
            this.addDialog(SerialPickerDialog, {
                productName: this.props.record.data.product_id[1],
                serials,
                initialSelection: this.selectedIds,
                onSelected: (lotIds) => {
                    this.props.record.update({
                        [this.props.name]: [[6, 0, lotIds]],
                    });
                },
            });
        } finally {
            this.state.loading = false;
        }
    }
}

class SerialMany2XAutocomplete extends ProductLabelSectionAndNoteFieldAutocomplete {
    static props = {
        ...ProductLabelSectionAndNoteFieldAutocomplete.props,
        serialRecord: Object,
    };

    setup() {
        super.setup();
        this.addSerialDialog = useOwnedDialogs();
        this.pendingSerials = new Map();
        useBus(this.env.bus, SERIAL_SELECTION_EVENT, (event) => {
            if (event.detail.searchToken !== this.searchToken) {
                return;
            }
            this.pendingSerials.set(
                `${event.detail.productModel}:${event.detail.productId}`,
                event.detail.lotIds
            );
        });
    }

    async onSearchMore(request) {
        if (
            !["product.product", "product.template"].includes(this.props.resModel) ||
            !this.props.serialRecord
        ) {
            return super.onSearchMore(request);
        }

        const { resModel, getDomain, context, fieldString } = this.props;
        this.searchToken = `${Date.now()}-${Math.random()}`;
        activeSerialSearchToken = this.searchToken;
        this.pendingSerials.clear();
        const domain = getDomain();
        let dynamicFilters = [];
        if (request.length) {
            const nameGets = await this.orm.call(resModel, "name_search", [], {
                name: request,
                args: domain,
                operator: "ilike",
                limit: this.props.searchMoreLimit,
                context,
            });
            dynamicFilters = [
                {
                    description: _t("Quick search: %s", request),
                    domain: [["id", "in", nameGets.map((item) => item[0])]],
                },
            ];
        }

        this.addSerialDialog(SelectCreateDialog, {
            title: _t("Search: %s", fieldString),
            noCreate: !this.activeActions.create,
            multiSelect: false,
            resModel,
            context,
            domain,
            dynamicFilters,
            onSelected: async (resIds) => {
                const productId = resIds[0];
                await this.props.update([{ id: productId }]);
                const selectionKey = `${resModel}:${productId}`;
                const lotIds = this.pendingSerials.get(selectionKey);
                activeSerialSearchToken = null;
                if (lotIds?.length) {
                    this.env.bus.trigger(LINE_SERIAL_SELECTION_EVENT, {
                        lineRecordId: this.props.serialRecord.id,
                        productModel: resModel,
                        productId,
                        lotIds,
                    });
                    this.pendingSerials.delete(selectionKey);
                }
            },
        });
    }
}

class SerialSaleOrderLineProductField extends SaleOrderLineProductField {
    static components = {
        ...SaleOrderLineProductField.components,
        Many2XAutocomplete: SerialMany2XAutocomplete,
    };

    setup() {
        super.setup();
        this.notification = useService("notification");
        this.pendingSelection = null;
        useBus(this.env.bus, LINE_SERIAL_SELECTION_EVENT, (event) => {
            if (event.detail.lineRecordId === this.props.record.id) {
                this.pendingSelection = event.detail;
                this.applyPendingSelection();
            }
        });
        useEffect(
            () => {
                this.applyPendingSelection();
            },
            () => [
                this.props.record.data.product_id?.[0],
                this.props.record.data.product_template_id?.[0],
            ]
        );
    }

    get Many2XAutocompleteProps() {
        return {
            ...super.Many2XAutocompleteProps,
            serialRecord: this.props.record,
        };
    }

    async applyPendingSelection() {
        const selection = this.pendingSelection;
        if (!selection) {
            return;
        }
        const selectedProductId =
            selection.productModel === "product.template"
                ? this.props.record.data.product_template_id?.[0]
                : this.props.record.data.product_id?.[0];
        if (
            selectedProductId !== selection.productId ||
            !this.props.record.data.product_id?.[0]
        ) {
            return;
        }
        this.pendingSelection = null;
        try {
            await this.props.record.update({
                x_selected_serial_lot_ids: [[6, 0, selection.lotIds]],
            });
        } catch (error) {
            this.notification.add(error.message || _t("Không thể gán Serial đã chọn."), {
                type: "danger",
            });
        }
    }
}

registry.category("fields").add("serial_count", {
    component: SerialCountField,
    displayName: _t("Serial count"),
    supportedTypes: ["integer"],
});
registry.category("fields").add("serial_lot_picker", {
    component: SerialLotPickerField,
    displayName: _t("Serial picker"),
    supportedTypes: ["many2many"],
});
registry.category("fields").add("serial_product_picker", {
    ...saleOrderLineProductField,
    component: SerialSaleOrderLineProductField,
});
registry.category("fields").add("sol_product_many2one_serial", {
    ...saleOrderLineProductField,
    component: SerialSaleOrderLineProductField,
});
