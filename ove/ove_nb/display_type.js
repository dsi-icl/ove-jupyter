define([], function () {
    const DisplayTypes = {
        AUDIO: "audio",
        CODE: "code",
        DISPLAY_HANDLE: "DisplayHandle",
        DISPLAY_OBJECT: "DisplayObject",
        FILE_LINK: "FileLink",
        FILE_LINKS: "FileLinks",
        GEOJSON: "GeoJSON",
        HTML: "HTML",
        IFRAME: "IFrame",
        IMAGE: "Image",
        JAVASCRIPT: "Javascript",
        JSON: "JSON",
        LATEX: "Latex",
        MARKDOWN: "Markdown",
        MATH: "Math",
        PRETTY: "Pretty",
        PROGRESS_BAR: "ProgressBar",
        SVG: "SVG",
        SCRIBD_DOCUMENT: "ScribdDocument",
        TEXT_DISPLAY_OBJECT: "TextDisplayObject",
        VIDEOS: "Video",
        VIMEO: "VimeoVideo",
        YOUTUBE: "YouTubeVideo"
    };

    const DataType = {
        AUDIO: "audio",
        DATAFRAME: "dataframe",
        GEOJSON: "geojson",
        HTML: "html",
        JPEG: "jpg",
        JSON: "json",
        LATEX: "latex",
        MARKDOWN: "markdown",
        PNG: "png",
        SVG: "svg",
        VIDEO: "videos"
    };

    const fromCellOutput = output => {
        if (output.data?.["text/plain"] === undefined) {
            return null;
        }

        const search = output["data"]["text/plain"].match(/IPython\.(?:core|lib)\.display\.([^ ]+)/);

        if (search === null) {
            return null;
        }

        return search[1];
    };

    const formatCellOutput = (type, output) => {
        if (type === DisplayTypes.YOUTUBE) {
            output.data = Object.keys(output.data).reduce((acc, x) => {
                if (x.includes("image")) return acc;
                acc[x] = output.data[x];
                return acc;
            }, {});
        }

        return output;
    };

    const toDataType = (displayType, outputType, data) => {
        if (displayType !== null && displayType === DisplayTypes.AUDIO && outputType.includes("text/html")) {
            return DataType.AUDIO;
        } else if (displayType !== null && (displayType === DisplayTypes.VIDEOS || displayType === DisplayTypes.YOUTUBE) && outputType.includes("text/html")) {
            return DataType.VIDEO;
        } else if (outputType.includes("text/html")) {
            return data.includes("dataframe") ? DataType.DATAFRAME : DataType.HTML;
        } else if (outputType.includes("image/png")) {
            return DataType.PNG;
        } else if (outputType.includes("image/jpeg")) {
            return DataType.JPEG;
        } else if (outputType.includes("image/svg+xml")) {
            return DataType.SVG;
        } else if (outputType.includes("text/latex")) {
            return DataType.LATEX;
        } else if (outputType.includes("text/markdown")) {
            return DataType.MARKDOWN;
        } else if (outputType.includes("application/json")) {
            return DataType.JSON;
        } else if (outputType.includes("application/geo+json")) {
            return DataType.GEOJSON;
        } else if (outputType.includes("text/plain")) {
            return null;
        } else {
            console.log(`Unhandled data type: ${outputType}`);
            return null;
        }
    };

    return {
        fromCellOutput,
        toDataType,
        formatCellOutput
    }
});