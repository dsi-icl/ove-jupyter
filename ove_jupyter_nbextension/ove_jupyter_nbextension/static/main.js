// noinspection JSUnresolvedReference

define([
    "jquery",
    "base/js/namespace",
    "notebook/js/outputarea",
    "./display_type",
    'base/js/dialog'
], ($, Jupyter, oa, dt, dialog) => {
    const global_config = Jupyter.notebook.metadata.ove_jupyter || {
        rows: 2,
        cols: 2,
        space: "LocalFour",
        mode: "production",
        multi_controller: false,
        remove: true,
        out: ".ove",
        env: ".env"
    };
    const create_dialog = () => {
        const global_config_ = JSON.stringify(global_config, undefined, 4);
        const cell_config_ = JSON.stringify(Jupyter.notebook.get_selected_cell().metadata.ove_jupyter || {
            cell_no: -1,
            row: null,
            col: null,
            width: null,
            height: null,
            x: null,
            y: null,
            from: null,
            to: null,
            split: null,
        }, undefined, 4);
        const modal = dialog.modal({
            show: false,
            title: 'Edit OVE config',
            notebook: Jupyter.notebook,
            keyboard_manager: Jupyter.notebook.keyboard_manager,
            body: $('<form/>').attr("id", "ove-modal-body")
                .append($("<div/>")
                    .attr("id", "ove-control-container")
                    .attr("style", "display: flex;")
                    .append($("<div/>")
                        .addClass("dropdown")
                        .append($("<button/>")
                            .addClass("btn btn-secondary dropdown-toggle")
                            .append($("<span/>").addClass("caret"))
                            .attr("type", "button")
                            .attr("id", "dropdown-menu-button")
                            .attr("data-toggle", "dropdown")
                            .attr("aria-haspopup", "true")
                            .attr("aria-expanded", "false")
                            .text("Config type - global")
                        )
                        .append($("<ul/>")
                            .addClass("dropdown-menu")
                            .attr("aria-labelledby", "dropdown-menu-button")
                            .append($("<li/>")
                                .append($("<button/>")
                                    .addClass("dropdown-item active")
                                    .attr("style", "width: 100%;")
                                    .attr("id", "ove-config-global")
                                    .on("click", event => {
                                        event.preventDefault();
                                        $("#ove-config-global").addClass("active");
                                        $("#ove-config-cell").removeClass("active");
                                        $("#dropdown-menu-button").text("Config type - global");

                                        $("#ove-config").text(global_config_);
                                    })
                                    .text("Global")
                                )
                            )
                            .append($("<li/>")
                                .append($("<button/>")
                                    .addClass("dropdown-item")
                                    .attr("id", "ove-config-cell")
                                    .attr("style", "width: 100%;")
                                    .on("click", event => {
                                        event.preventDefault();
                                        $("#ove-config-cell").addClass("active");
                                        $("#ove-config-global").removeClass("active");
                                        $("#dropdown-menu-button").text("Config type - cell");

                                        $("#ove-config").text(cell_config_);
                                    })
                                    .text("Cell"))
                            )
                        )
                    )
                    .append($("<button/>")
                        .addClass("btn")
                        .append($("<i/>").addClass("fa fa-gamepad"))
                        .attr("id", "ove-controller")
                        .on("click", event => {
                            event.preventDefault();
                            const baseUrl = window.location.href.replace(window.location.pathname, "");
                            window.open(`${baseUrl}${$("body").data("baseUrl")}ove-jupyter/static/control.html`)
                        })
                    )
                    .append($("<button/>")
                        .addClass("btn")
                        .append($("<i/>").addClass("fa fa-eye"))
                        .attr("id", "ove-preview")
                        .on("click", event => {
                            event.preventDefault();
                            const baseUrl = window.location.href.replace(window.location.pathname, "");
                            window.open(`${baseUrl}${$("body").data("baseUrl")}ove-jupyter/static/overview.html`)
                        })
                    )
                )
                .append($("<label/>")
                    .attr("for", "ove-config")
                )
                .append($("<textarea/>")
                    .attr("id", "ove-config")
                    .attr("name", "ove-config")
                    .attr("rows", "20")
                    .attr("cols", "50")
                    .text(global_config_)
                ),
            buttons: {
                'Save': {
                    class: 'btn-primary',
                    click: () => {
                        const input = JSON.parse($("#ove-config").val());
                        const cell = Jupyter.notebook.get_selected_cell();
                        if ($("#ove-config-global").hasClass("active")) {
                            if (JSON.stringify(input) === global_config_) return;
                            Jupyter.notebook.metadata.ove_jupyter = input;
                            config_handler(input).catch(console.error);
                        } else {
                            if (JSON.stringify(input) === cell_config_) return;
                            cell.metadata.ove_jupyter = input;
                        }
                    }
                }
            }
        })
            .attr('id', 'ove_jupyter_modal');

        modal.modal('show');
    };

    const config_handler = async config => {
        const body = $("body");
        await fetch(`${body.data("baseUrl")}ove-jupyter/config`, {
            method: "POST",
            headers: {
                "Authorization": `token ${body.data("jupyterApiToken")}`,
                "X-XSRFToken": getCookie("_xsrf"),
                "Content-Type": "application/json",
            },
            body: JSON.stringify(config),
            credentials: "same-origin"
        });

        console.log("Updated ove-jupyter config");
    };

    const format_outputs = outputs => outputs.flatMap((output, output_idx) => {
        if (output.data === null || output.data === undefined || Object.keys(output.data).length === 0) {
            return [];
        }

        const display_mode = dt.fromCellOutput(output);

        if (display_mode !== null) {
            output = dt.formatCellOutput(display_mode, output);
        }

        output.data = Object.keys(output.data).reduce((acc, x) => {
            if (x.includes("text/plain")) return acc;
            acc[x] = output.data[x];
            return acc;
        }, {});

        if (Object.keys(output.data).length > 1) {
            throw new Error(`Unexpected output size: ${Object.keys(output.data).length}`);
        }

        return Object.keys(output.data).map(key => {
            const data_type = dt.toDataType(display_mode, key, output.data[key]);
            const metadata = output.metadata?.[key];
            return [output_idx.toString(10), data_type, output.data[key], metadata];
        });
    });

    const tee_handler = async (config, outputs) => {
        const body = $("body");
        await fetch(`${body.data("baseUrl")}ove-jupyter/tee`, {
            method: "POST",
            headers: {
                "Authorization": `token ${body.data("jupyterApiToken")}`,
                "X-XSRFToken": getCookie("_xsrf"),
                "Content-Type": "application/json",
            },
            credentials: "same-origin",
            body: JSON.stringify({
                config,
                outputs
            })
        });
    };
    const getCookie = name => document.cookie.match('\\b' + name + '=([^;]*)\\b')?.[1];

    const initialize = () => {
        console.log("Initializing OVE Jupyter");

        Jupyter.notebook.events.on("finished_execute.CodeCell", async function (event, {cell}) {
            try {
                const metadata = cell.metadata.ove_jupyter;
                if (metadata === null || metadata === undefined) return;
                const outputs = JSON.parse(JSON.stringify(cell))["outputs"];
                const formatted_outputs = format_outputs(outputs);
                tee_handler(metadata, formatted_outputs).catch(console.error);
            } catch (e) {
                console.log(e);
            }
        });

        Jupyter.toolbar.add_buttons_group([
            Jupyter.keyboard_manager.actions.register({
                help: 'Edit ove-jupyter config data',
                icon: 'fa-solid fa-desktop',
                handler: create_dialog
            }, 'edit_ove_config_data', 'OVE')
        ]);

        if (Jupyter.notebook.metadata.ove_jupyter !== undefined) {
            console.log("Loading ove-jupyter config");
            config_handler(global_config).catch(console.error);
        }
    };

    const load_ipython_extension = () => Jupyter.notebook.config.loaded.then(initialize).catch(e => console.error(`Error loading ove-jupyter: ${e}`));

    // noinspection JSUnusedGlobalSymbols
    return {
        load_ipython_extension
    };
});