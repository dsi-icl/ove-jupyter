define([
    "base/js/namespace",
    "notebook/js/outputarea",
    "notebook/js/codecell"
], function (Jupyter, oa) {
    const params = {
        limit_output: 0,
        limit_stream: true,
        limit_execute_result: true,
        limit_display_data: true,
        limit_html_output: true,
        limit_output_message: "<b>OVE Jupyter extension: Maximum message size of {limit_output_length} exceeded with {output_length} characters</b>"
    };

    const update_params = function () {
        const config = Jupyter.notebook.config;
        for (let key in params) {
            if (config.data.hasOwnProperty(key)) {
                params[key] = config.data[key];
            }
        }
    };

    function is_finite_number (n) {
        n = parseFloat(n);
        return !isNaN(n) && isFinite(n);
    }

    const insert_cell = function () {
        const cell = Jupyter.notebook.insert_cell_above("code");
        cell.set_text("Hello from OVE");
        Jupyter.notebook.select_prev(cell);
    };

    const initialize = function () {
        console.log("Initializing OVE Jupyter");
        update_params();
        params.limit_output = parseFloat(params.limit_output);
        const old_handle_output = oa.OutputArea.prototype.handle_output;
        oa.OutputArea.prototype.handle_output = function (msg) {
            const handled_msg_types = ["stream", "execute_result", "display_data"];
            console.log(JSON.stringify(msg));

            if (handled_msg_types.indexOf(msg.header.msg_type) < 0) {
                return old_handle_output.apply(this, arguments);
            }

            if (!params.limit_html_output && msg?.content?.data?.["text/html"] !== undefined) {
                return old_handle_output.apply(this, arguments);
            }

            let MAX_CHARACTERS = params.limit_output;
            console.log("-------------------");
            console.log(JSON.stringify(this.element.closest(".cell").text()));
            console.log(JSON.stringify(this.element.closest(".cell").data("cell")));
            fetch("http://localhost:8999").then(res => console.log(res));
            console.log("-------------------");
            const cell_metadata = this.element.closest(".cell").data("cell").metadata;

            if (is_finite_number(cell_metadata.limit_output)) {
                MAX_CHARACTERS = parseFloat(cell_metadata.limit_output);
            }

            let count = this.element.data("limit_output_count") || 0;
            const old_count = count;

            if (msg.header.msg_type === "stream" && params.limit_stream) {
                count += String(msg.content.text).length;
            } else if ((msg.header.msg_type === "execute_result" && params.limit_execute_result) || (msg.header.msg_type === "display_data" && params.limit_display_data)) {
                count += Math.max((msg.content.data["text/plain"] === undefined) ? 0 : String(msg.content.data["text/plain"]).length,
                    (msg.content.data["text/html"] === undefined) ? 0 : String(msg.content.data["text/html"]).length);
            }

            this.element.data("limit_output_count", count);

            if (count <= MAX_CHARACTERS) {
                return old_handle_output.apply(this, arguments);
            }

            if (old_count > MAX_CHARACTERS) {
                return
            }

            const to_add = MAX_CHARACTERS - old_count;

            if (msg.header.msg_type === "stream") {
                msg.content.text = msg.content.text.substring(0, to_add);
            } else {
                if (msg?.content?.data?.["text/plain"] !== undefined) {
                    msg.content.data["text/plain"] = msg.content.data["text/plain"].substring(0, to_add);
                }
                if (msg?.content?.data?.["text/html"] !== undefined) {
                    msg.content.data["text/html"] = msg.content.data["text/html"].substring(0, to_add);
                }

                old_handle_output.apply(this, arguments);

                console.log(`limit_output: Maximum message size of ${MAX_CHARACTERS} exceeded with ${count} characters. Further output muted.`);

                const limit_message = params.limit_output_message.replace("{message_type}", msg.header.msg_type).replace("{limit_output_length}", MAX_CHARACTERS).replace("{output_length}", count);

                this.append_output({
                    output_type: "display_data",
                    metadata: {},
                    data: {"text/html": limit_message}
                });
            }
        };

        const old_clear_output = oa.OutputArea.prototype.clear_output;

        oa.OutputArea.prototype.clear_output = function () {
            this.element.data("limit_output_count", 0);
            return old_clear_output.apply(this, arguments);
        };
    };

    const oveButton = function () {
        console.log();
        Jupyter.toolbar.add_buttons_group([
            Jupyter.keyboard_manager.actions.register({
                "help": "Add OVE Jupyter cell",
                "icon": "fa-paper-plane",
                "handler": insert_cell
            }, "add-ove-jupyter-cell", "OVE Jupyter")
        ]);
    };

    function load_ipython_extension() {
        if (Jupyter.notebook.get_cells().length === 1) {
            insert_cell();
        }
        oveButton();
        return Jupyter.notebook.config.loaded.then(initialize);
    }

    return {
        load_ipython_extension
    };
});