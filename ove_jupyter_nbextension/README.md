# ove-jupyter

Connecting OVE and Jupyter Notebooks.

Create and control a visualisation in OVE directly from your Jupyter notebooks.

## Features

- Automatically generate sections in OVE
- Control each section from the notebook output
- Saves outputs and a project.json for migration to the OVE Asset Manager
- Choose from one of four supported [display modes](#display-modes)
- Setup in 3 lines of code

## How to use

### Installation

To install please use the following command:

```pip install -r requirements.txt```

### Environment setup

Create a .env file with the following variables:

- OVE_HOST: your external ip. Can be found using the command ```curl ifconfig.me```.
- OVE_PORT: port for file server, default is 8000.
- OVE_CORE: hostname for OVE Core server.

### Load the extension

```%load_ext ove```

### Configure the extension

```%ove_configure *args```

### Display a cell in OVE

```%%tee cell_no *args```

### After notebook exit

It is possible to serve the saved files after the notebook has exited using the following command:
```cd .ove && python(3) -m http.server -p 8000```

## Display modes

### Automatic

Uses the cell_no to fill the OVE space as a grid, down each column.

### Flex

Specify a top-left and bottom-right corner for the section using the grid.

### Grid

Specify the row and column for the section to be displayed at.

### Pixel

Specify a width, height, x offset and y offset in pixel values.

## API

### ove_configure

- --space (-s): OVE Space to create visualisation in. Default is LocalFour.
- --rows (-r): Number of rows in visualisation grid. Default is 2.
- --cols (-c): Number of columns in visualisation grid. Default is 2.
- --env (-e): Location of environment variable file. Default is .env.
- --out (-o): Location of output directory for file serving. Default is .ove.
- --remove (-rm): Whether to clear output directory on configuration. Default is true.
- --mode (-m): Accepts "production" or "development". If mode is "development", no calls to external OVE are made and
  information is logged to file.

### tee

- cell_no: Required. Unique number as cell id. In automatic display mode is used as position in visualisation grid.
- --row (-r): Display Mode Grid. Row position in grid.
- --col (-c): Display Mode Grid. Column position in grid.
- --width (-w): Display Mode Pixel. Pixel width.
- --height (-h): Display Mode Pixel. Pixel height.
- --x (-x): Display Mode Pixel. x-axis pixel offset.
- --y (-y): Display Mode Pixel. y-axis pixel offset.
- --from (-f): Display Mode Flex. Top-left corner position in grid.
- --to (-t): Display Mode Flex. Bottom-right corner position in grid.
- --split (-s): How to display multiple outputs. Accepts "width" or "height", splits into columns or rows respectively.