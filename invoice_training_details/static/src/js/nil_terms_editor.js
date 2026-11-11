/** @odoo-module **/

import { Component, onMounted, onWillUnmount, onWillUpdateProps, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class NilTermsEditor extends Component {
    static template = "invoice_training_details.NilTermsEditor";
    static props = { ...standardFieldProps };

    setup() {
        this.editorRef = useRef("editor");
        this.savedRange = null;
        this.commitTimer = null;
        this.internalUpdate = false;

        this._selectionHandler = () => {
            this.rememberSelection();
        };

        onMounted(() => {
            this._setHtml(this.props.record.data[this.props.name] || "");
            document.addEventListener("selectionchange", this._selectionHandler);
        });

        onWillUpdateProps((nextProps) => {
            const nextValue = nextProps.record.data[nextProps.name] || "";

            if (
                this.editorRef.el &&
                !this.internalUpdate &&
                document.activeElement !== this.editorRef.el &&
                this.editorRef.el.innerHTML !== nextValue
            ) {
                this._setHtml(nextValue);
            }

            this.internalUpdate = false;
        });

        onWillUnmount(() => {
            document.removeEventListener(
                "selectionchange",
                this._selectionHandler
            );

            if (this.commitTimer) {
                clearTimeout(this.commitTimer);
            }
        });
    }

    _setHtml(value) {
        if (this.editorRef.el) {
            this.editorRef.el.innerHTML = value || "";
        }
    }

    rememberSelection() {
        const editor = this.editorRef.el;
        const selection = window.getSelection();

        if (!editor || !selection || !selection.rangeCount) {
            return;
        }

        const range = selection.getRangeAt(0);

        let node = range.commonAncestorContainer;

        if (node.nodeType !== Node.ELEMENT_NODE) {
            node = node.parentElement;
        }

        if (node && editor.contains(node)) {
            this.savedRange = range.cloneRange();
        }
    }

    restoreSelection() {
        if (!this.savedRange) {
            return false;
        }

        const selection = window.getSelection();

        selection.removeAllRanges();
        selection.addRange(this.savedRange);

        return true;
    }

    focusEditor() {
        this.editorRef.el.focus();
        this.restoreSelection();
    }

    save(immediate = false) {
        if (!this.editorRef.el) {
            return;
        }

        const commit = () => {
            this.internalUpdate = true;

            this.props.record.update({
                [this.props.name]: this.editorRef.el.innerHTML,
            });
        };

        if (this.commitTimer) {
            clearTimeout(this.commitTimer);
        }

        if (immediate) {
            commit();
        } else {
            this.commitTimer = setTimeout(commit, 180);
        }
    }

    onEditorInput() {
        this.rememberSelection();
        this.save(false);
    }

    onEditorBlur() {
        this.save(true);
    }

    onToolbarMouseDown(ev) {
        if (ev.target.tagName === "BUTTON") {
            ev.preventDefault();
        }

        this.rememberSelection();
    }

    execCommand(ev) {
        const command = ev.currentTarget.dataset.command;

        this.focusEditor();

        document.execCommand(
            "styleWithCSS",
            false,
            true
        );

        document.execCommand(
            command,
            false,
            null
        );

        this.rememberSelection();
        this.save(true);
    }

    setBlock(ev) {
        const value = ev.target.value;

        if (!value) {
            return;
        }

        this.focusEditor();

        document.execCommand(
            "formatBlock",
            false,
            value
        );

        ev.target.value = "";

        this.rememberSelection();
        this.save(true);
    }

    setFontSize(ev) {
        const value = ev.target.value;

        if (!value) {
            return;
        }

        this.focusEditor();

        document.execCommand(
            "styleWithCSS",
            false,
            false
        );

        document.execCommand(
            "fontSize",
            false,
            "7"
        );

        for (
            const font of
            this.editorRef.el.querySelectorAll('font[size="7"]')
        ) {
            font.removeAttribute("size");
            font.style.fontSize = value;
        }

        ev.target.value = "";

        this.rememberSelection();
        this.save(true);
    }

    setTextColor(ev) {
        const value = ev.target.value;

        this.focusEditor();

        document.execCommand(
            "styleWithCSS",
            false,
            true
        );

        document.execCommand(
            "foreColor",
            false,
            value
        );

        this.rememberSelection();
        this.save(true);
    }

    setHighlight(ev) {
        const value = ev.target.value;

        this.focusEditor();

        document.execCommand(
            "styleWithCSS",
            false,
            true
        );

        document.execCommand(
            "hiliteColor",
            false,
            value
        );

        this.rememberSelection();
        this.save(true);
    }

    _currentRange() {
        const selection = window.getSelection();

        if (selection && selection.rangeCount) {
            const range = selection.getRangeAt(0);

            let node = range.commonAncestorContainer;

            if (node.nodeType !== Node.ELEMENT_NODE) {
                node = node.parentElement;
            }

            if (node && this.editorRef.el.contains(node)) {
                return range;
            }
        }

        return this.savedRange;
    }

    _closestBlock(node) {
        let element = node;

        if (!element) {
            return null;
        }

        if (element.nodeType !== Node.ELEMENT_NODE) {
            element = element.parentElement;
        }

        const block = element?.closest(
            "p,div,li,td,th,blockquote,h1,h2,h3,h4,h5,h6"
        );

        return (
            block &&
            this.editorRef.el.contains(block)
        )
            ? block
            : null;
    }

    _selectedBlocks() {
        const range = this._currentRange();

        if (!range) {
            return [];
        }

        if (range.collapsed) {
            const block = this._closestBlock(
                range.startContainer
            );

            return block ? [block] : [];
        }

        const selector =
            "p,div,li,td,th,blockquote,h1,h2,h3,h4,h5,h6";

        const blocks = [];

        for (
            const node of
            this.editorRef.el.querySelectorAll(selector)
        ) {
            try {
                if (range.intersectsNode(node)) {
                    blocks.push(node);
                }
            } catch {
            }
        }

        if (!blocks.length) {
            const block = this._closestBlock(
                range.startContainer
            );

            if (block) {
                blocks.push(block);
            }
        }

        return blocks;
    }

    setLineHeight(ev) {
        const value = ev.target.value;

        if (!value) {
            return;
        }

        this.focusEditor();

        for (const block of this._selectedBlocks()) {
            block.style.lineHeight = value;
        }

        ev.target.value = "";

        this.rememberSelection();
        this.save(true);
    }

    setParagraphGap(ev) {
        const value = ev.target.value;

        if (value === "") {
            return;
        }

        this.focusEditor();

        for (const block of this._selectedBlocks()) {
            block.style.marginBottom = `${value}px`;
        }

        ev.target.value = "";

        this.rememberSelection();
        this.save(true);
    }

    setIndent(ev) {
        const value = ev.target.value;

        if (value === "") {
            return;
        }

        this.focusEditor();

        for (const block of this._selectedBlocks()) {
            block.style.marginLeft = `${value}px`;
        }

        ev.target.value = "";

        this.rememberSelection();
        this.save(true);
    }

    insertTable(ev) {
        const value = ev.target.value;

        if (!value) {
            return;
        }

        const [rowsText, colsText] =
            value.split("x");

        const rows = parseInt(rowsText, 10);
        const cols = parseInt(colsText, 10);

        this.focusEditor();

        let html = `
            <table style="
                width:100%;
                border-collapse:collapse;
                margin:10px 0;
            ">
                <tbody>
        `;

        for (let r = 0; r < rows; r++) {
            html += "<tr>";

            for (let c = 0; c < cols; c++) {
                html += `
                    <td style="
                        border:1px solid #777;
                        padding:8px;
                        vertical-align:top;
                    ">
                        <br/>
                    </td>
                `;
            }

            html += "</tr>";
        }

        html += `
                </tbody>
            </table>
            <p><br/></p>
        `;

        document.execCommand(
            "insertHTML",
            false,
            html
        );

        ev.target.value = "";

        this.rememberSelection();
        this.save(true);
    }

    _currentCell() {
        const range = this._currentRange();

        if (!range) {
            return null;
        }

        let node = range.startContainer;

        if (node.nodeType !== Node.ELEMENT_NODE) {
            node = node.parentElement;
        }

        const cell = node?.closest("td,th");

        return (
            cell &&
            this.editorRef.el.contains(cell)
        )
            ? cell
            : null;
    }

    _currentTable() {
        return (
            this._currentCell()?.closest("table") ||
            null
        );
    }

    addRow() {
        const cell = this._currentCell();

        if (!cell) {
            return;
        }

        const row = cell.closest("tr");

        const newRow = row.cloneNode(true);

        for (
            const newCell of
            newRow.querySelectorAll("td,th")
        ) {
            newCell.removeAttribute("rowspan");
            newCell.innerHTML = "<br/>";
        }

        row.after(newRow);

        this.save(true);
    }

    deleteRow() {
        const cell = this._currentCell();

        if (!cell) {
            return;
        }

        const table = cell.closest("table");
        const row = cell.closest("tr");

        if (table.rows.length <= 1) {
            return;
        }

        row.remove();

        this.save(true);
    }

    addColumn() {
        const cell = this._currentCell();

        if (!cell) {
            return;
        }

        const table = cell.closest("table");
        const index = cell.cellIndex;

        for (const row of table.rows) {
            const reference =
                row.cells[index] ||
                row.cells[row.cells.length - 1];

            const newCell =
                document.createElement(
                    reference?.tagName === "TH"
                        ? "th"
                        : "td"
                );

            newCell.innerHTML = "<br/>";
            newCell.style.border =
                "1px solid #777";
            newCell.style.padding =
                "8px";
            newCell.style.verticalAlign =
                "top";

            if (reference) {
                reference.after(newCell);
            } else {
                row.appendChild(newCell);
            }
        }

        this.save(true);
    }

    deleteColumn() {
        const cell = this._currentCell();

        if (!cell) {
            return;
        }

        const table = cell.closest("table");
        const index = cell.cellIndex;

        if (
            table.rows[0]?.cells.length <= 1
        ) {
            return;
        }

        for (const row of table.rows) {
            if (row.cells[index]) {
                row.deleteCell(index);
            }
        }

        this.save(true);
    }

    mergeRight() {
        const cell = this._currentCell();

        if (!cell) {
            return;
        }

        const row = cell.closest("tr");

        const next =
            row.cells[
                cell.cellIndex + 1
            ];

        if (!next) {
            return;
        }

        const currentSpan =
            parseInt(
                cell.getAttribute("colspan") ||
                "1",
                10
            );

        const nextSpan =
            parseInt(
                next.getAttribute("colspan") ||
                "1",
                10
            );

        const currentContent =
            cell.innerHTML.trim();

        const nextContent =
            next.innerHTML.trim();

        if (
            nextContent &&
            nextContent !== "<br>"
        ) {
            cell.innerHTML =
                (
                    currentContent &&
                    currentContent !== "<br>"
                        ? currentContent + " "
                        : ""
                ) +
                nextContent;
        }

        cell.setAttribute(
            "colspan",
            String(
                currentSpan +
                nextSpan
            )
        );

        next.remove();

        this.save(true);
    }

    splitCell() {
        const cell = this._currentCell();

        if (!cell) {
            return;
        }

        const colspan =
            parseInt(
                cell.getAttribute("colspan") ||
                "1",
                10
            );

        if (colspan <= 1) {
            return;
        }

        cell.setAttribute(
            "colspan",
            "1"
        );

        for (
            let i = 1;
            i < colspan;
            i++
        ) {
            const newCell =
                document.createElement(
                    cell.tagName.toLowerCase()
                );

            newCell.innerHTML = "<br/>";
            newCell.style.cssText =
                cell.style.cssText;

            cell.after(newCell);
        }

        this.save(true);
    }

    toggleHeaderCell() {
        const cell = this._currentCell();

        if (!cell) {
            return;
        }

        const replacement =
            document.createElement(
                cell.tagName === "TH"
                    ? "td"
                    : "th"
            );

        for (const attr of cell.attributes) {
            replacement.setAttribute(
                attr.name,
                attr.value
            );
        }

        replacement.innerHTML =
            cell.innerHTML;

        cell.replaceWith(
            replacement
        );

        this.save(true);
    }

    setCellPadding(ev) {
        const value = ev.target.value;

        if (value === "") {
            return;
        }

        const table =
            this._currentTable();

        if (!table) {
            ev.target.value = "";
            return;
        }

        for (
            const cell of
            table.querySelectorAll("td,th")
        ) {
            cell.style.padding =
                `${value}px`;
        }

        ev.target.value = "";

        this.save(true);
    }

    setBorderWidth(ev) {
        const value = ev.target.value;

        if (value === "") {
            return;
        }

        const table =
            this._currentTable();

        if (!table) {
            ev.target.value = "";
            return;
        }

        for (
            const cell of
            table.querySelectorAll("td,th")
        ) {
            cell.style.border =
                value === "0"
                    ? "none"
                    : `${value}px solid #777`;
        }

        ev.target.value = "";

        this.save(true);
    }

    setCellBackground(ev) {
        const cell =
            this._currentCell();

        if (!cell) {
            return;
        }

        cell.style.backgroundColor =
            ev.target.value;

        this.save(true);
    }

    setCellVerticalAlign(ev) {
        const value = ev.target.value;

        if (!value) {
            return;
        }

        const cell =
            this._currentCell();

        if (cell) {
            cell.style.verticalAlign =
                value;
        }

        ev.target.value = "";

        this.save(true);
    }

    setTableWidth(ev) {
        const value = ev.target.value;

        if (!value) {
            return;
        }

        const table =
            this._currentTable();

        if (table) {
            table.style.width =
                value;
        }

        ev.target.value = "";

        this.save(true);
    }

    setTableAlign(ev) {
        const value = ev.target.value;

        if (!value) {
            return;
        }

        const table =
            this._currentTable();

        if (table) {
            if (value === "center") {
                table.style.marginLeft =
                    "auto";

                table.style.marginRight =
                    "auto";
            } else if (
                value === "right"
            ) {
                table.style.marginLeft =
                    "auto";

                table.style.marginRight =
                    "0";
            } else {
                table.style.marginLeft =
                    "0";

                table.style.marginRight =
                    "auto";
            }
        }

        ev.target.value = "";

        this.save(true);
    }

    clearFormatting() {
        this.focusEditor();

        document.execCommand(
            "removeFormat",
            false,
            null
        );

        this.rememberSelection();
        this.save(true);
    }
}

registry.category("fields").add(
    "nil_terms_editor",
    {
        component: NilTermsEditor,

        supportedTypes: [
            "html",
            "text",
        ],
    }
);
