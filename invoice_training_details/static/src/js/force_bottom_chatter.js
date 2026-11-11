/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormCompiler } from "@web/views/form/form_compiler";

/*
 * Keep chatter below the form and mark forms that contain the repeated
 * LCP page so CSS can remove Odoo's centered-sheet max width only there.
 */
patch(FormCompiler.prototype, {
    compile(node, params) {
        const result = super.compile(node, params);

        const formRenderer =
            result?.matches?.(".o_form_renderer")
                ? result
                : result?.querySelector?.(".o_form_renderer");

        if (!formRenderer) {
            return result;
        }

        if (result.querySelector?.(".o_lcp_full_width_page")) {
            formRenderer.classList.add(
                "o_nil_lcp_full_width"
            );
        }

        const chatters = result.querySelectorAll(
            ".o-mail-Form-chatter"
        );

        if (!chatters.length) {
            return result;
        }

        formRenderer.classList.add(
            "o_nil_force_bottom_chatter"
        );

        for (const chatter of chatters) {
            chatter.removeAttribute(
                "t-attf-class"
            );

            chatter.classList.remove(
                "o-aside"
            );

            chatter.classList.add(
                "o_nil_bottom_chatter"
            );

            const chatterComponent =
                chatter.querySelector(
                    "t[t-component='__comp__.mailComponents.Chatter']"
                );

            if (chatterComponent) {
                chatterComponent.setAttribute(
                    "isChatterAside",
                    "false"
                );

                if (
                    !chatter.closest(
                        ".o_form_sheet_bg"
                    )
                ) {
                    chatterComponent.setAttribute(
                        "isInFormSheetBg",
                        "false"
                    );
                }
            }
        }

        return result;
    },
});
