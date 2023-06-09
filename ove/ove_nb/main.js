define([
    "base/js/namespace",
    "notebook/js/outputarea",
    "./display_type"
], (Jupyter, oa, dt) => {
    let _outputs = {};

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
                "Content-Type": "text/plain",
            },
            body: args,
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

        output.data = Object.fromEntries(Object.entries(output.data).filter(([key]) => !key.includes('text/plain')));

        if (Object.keys(output.data).length > 1) {
            throw new Error(`Unexpected output size: ${Object.keys(output.data).length}`);
        }

        return Object.entries(output.data).map(([key, value]) => {
            const data_type = dt.toDataType(display_mode, key, value);
            const metadata = output.metadata?.[key];
            return [output_idx.toString(10), data_type, value, metadata];
        });
    });

    const tee_handler = async args => {
        console.log(`TEE CONFIG: ${args}`);
        await fetch("http://localhost:8000/tee", {
            method: "POST",
            headers: {
                "Content-Type": "text/plain",
            },
            body: args,
        });
    };

    const controller_handler = async () => {
        console.log("REGISTERING CONTROLLER");
        await fetch("http://localhost:8000/controller", {
            method: "POST"
        });

        console.log("Registered controller");
    };

    const initialize = () => {
        console.log("Initializing OVE Jupyter");

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
                    body: JSON.stringify(formatted_outputs),
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