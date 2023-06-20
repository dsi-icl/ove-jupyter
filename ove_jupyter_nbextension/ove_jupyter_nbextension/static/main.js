define([
    "jquery",
    "base/js/namespace",
    "notebook/js/outputarea",
    "./display_type"
], ($, Jupyter, oa, dt) => {
    const generate_uuid = () => {
        const rand_int = (max) => Math.floor(Math.random() * max);
        const opt = rand_int(3);
        switch (opt) {
            case 0:
                return rand_int(10);
            case 1:
                return String.fromCharCode(rand_int(26) + 65);
            case 2:
                return String.fromCharCode(rand_int(26) + 97);
            default:
                throw new Error(`Unknown opt: ${opt}`);
        }
    };

    let _outputs = {};
    const uuid = Array.from({length: 50}, generate_uuid).join("");

    const check_regex = async (regex, str, handler) => {
        if (str === null || str === undefined) return false;
        const match = str.match(regex);
        if (match !== null) {
            if (handler !== null && handler !== undefined) {
                if (match.length > 1) {
                    await handler(match[1]);
                } else {
                    await handler();
                }
            }
            return [true, match];
        }
        return [false, match];
    };

    const config_handler = async args => {
        console.log(`OVE CONFIG: ${args}`);
        await fetch("http://localhost:8000/config", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                data: args,
                id: uuid
            })
        });

        console.log("Updated config");
    };

    const format_outputs = outputs => outputs.flatMap((output, output_idx) => {
        if (Object.keys(output.data).length === 0) {
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

    const tee_handler = async args => {
        console.log(`TEE CONFIG: ${args}`);
        await fetch("http://localhost:8000/tee", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                data: args,
                id: uuid
            })
        });
    };

    const controller_handler = async () => {
        console.log("REGISTERING CONTROLLER");
        await fetch("http://localhost:8000/controller", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                id: uuid
            })
        });

        console.log("Registered controller");
    };

    const initialize = () => {
        console.log("Initializing OVE Jupyter");
        const body = $("body");

        console.log(`Base URL: ${body.data("baseUrl")}`);

        const getCookie = name => document.cookie.match('\\b' + name + '=([^;]*)\\b')?.[1];

        fetch(`/ove-jupyter/config`, {
            credentials: "same-origin",
            headers: {
                "Authorization": `token ${body.data("jupyterApiToken")}`,
                "X-XSRFToken": getCookie("_xsrf")
            },
            method: "POST",
            body: JSON.stringify({id: 1})
        }).then(console.log).catch(console.error);
        console.log(`JUPYTER API TOKEN: ${body.data("jupyterApiToken")}`);

        Jupyter.notebook.events.on("execute.CodeCell", async function (event, {cell}) {
            console.log("Executing cell");
            try {
                const data = JSON.parse(JSON.stringify(cell));
                const config_regex = /^# ?ove_config ([^\n]*)/;
                const controller_regex = /^# ?ove_controller\n?/;

                await check_regex(config_regex, data?.source, config_handler);
                await check_regex(controller_regex, data?.source, controller_handler);
            } catch (e) {
                console.log(e);
            }
        });

        Jupyter.notebook.events.on("finished_execute.CodeCell", async function (event, {cell}) {
            try {
                const formatted_cell = JSON.parse(JSON.stringify(cell));
                const [, match] = await check_regex(/# ?tee (\d+)(?: (.+))?/, formatted_cell?.source);
                if (match === null || match.length <= 1) {
                    return
                }
                console.log(`Finished executing cell: ${match[1]}`);

                await tee_handler(match.slice(1).filter(x => x !== null && x !== undefined).join(" "));

                const formatted_outputs = format_outputs(_outputs[match[1]]);
                console.log(JSON.stringify(formatted_outputs));
                await fetch("http://localhost:8000/output", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        cell_no: parseInt(match[1]),
                        data: formatted_outputs,
                        id: uuid
                    }),
                });
                delete _outputs[match[1]];
            } catch (e) {
                _outputs = {};
                console.log(e);
            }
        });

        // noinspection JSUnusedGlobalSymbols
        oa.OutputArea.prototype.handle_output = async function () {
            console.log("Handling output");
            try {
                const cell = JSON.parse(JSON.stringify(this.element.closest(".cell").data("cell")));
                const [, match] = await check_regex(/# ?tee (\d+)(?: (.+))?/, cell.source);
                if (match !== null && match.length > 1) {
                    if (_outputs[match[1]] !== undefined) {
                        _outputs[match[1]].push(arguments["0"]?.content);
                    } else {
                        _outputs[match[1]] = [arguments["0"]?.content];
                    }
                }
            } catch (e) {
                console.log(e);
            }

            this.append_output({
                output_type: "display_data",
                metadata: {},
                data: {}
            });
        };
    };

    const load_ipython_extension = () => Jupyter.notebook.config.loaded.then(initialize).catch(() => console.log("Error loading ove-jupyter"));

    // noinspection JSUnusedGlobalSymbols
    return {
        load_ipython_extension
    };
});