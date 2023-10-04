# storm-control

Storm-Control is:
- software for controlling equipment used for [STORM and MERFISH imaging](https://zhuang.harvard.edu/research.html);
- a collection of modules for controlling different types of hardware, with mechanisms for defining what subset of this collection is in use;
- a set of Qt applications, which through Qt Objects form the basis for functionality like object communication and concurrency, and which provide GUIs for controlling the hardware and setting up the experiments. Hal controls the microscope (cameras, XY stage, Z stage, light engine); Kilroy controls the fluidics; Steve manages mosaic/map acquisition; Dave coordinates the whole experiment.

## Configuration

#### Modules

The first thing you will want to do is to create a main configuration file; examples can be found in `storm-control/storm_control/hal4000/xml`.

When Hal starts up, it creates a HalCore object and passes to it the main configuration file.
HalCore reads the main configuration file and, for each module listed under `<modules>`, instantiates the class specified by `module_name` and `class_name`, and adds this instance object to `self.modules`.

Each of these classes under `<modules>` must be a subclass of HalModule.
Through HalModule, each of these modules has a `newMessage` attribute, which is just a Qt Signal.
During startup, HalCore connects each of these modules' newMessage Signal to HalCore.handleMessage, which functions as a Qt Slot.
In this way, Hal can talk to each of the configured modules.

Any module that is _not_ in the configuration will _not_ get loaded or run.


#### Dave config, Hal config, shutter config

[TODO: overview of Dave config]
[Is a dave-config the same as a recipe the same as a (new-style) experiment descriptor file?]
[...] Each `<movie>` references a hal-config.

[TODO: I think there should be a example/template/commented hal-config and shutter-config in this repo]

The hal-config contains settings for the main camera and the autofocus.

Each hal-config has a matching shutter-config; by convention, they have the same 'z' numbers in their file names.
The 'z' numbers describe the z stack: for example 405z7dz15 means channel 405 (DAPI channel), at 7 different z positions, 1.5um apart.
The shutter-config is referenced in the hal-config's `<illumination>` field.
The `<frames>` number must match between the two files.

In the hal-config, the `<z_offsets>` describe the z positions at which to image.

The shutter-config contains instructions for the light engine; it describes when to turn on which lasers.
Each `<event>` block refers to a different set of N images using one laser;
for example if `<on>` has 0.0 and `<off>` has 7.0, then images 0 to 6 - corresponding to the first 7 `<z_offsets>`
in the hal-config - use some laser X.

Each round of imaging (e.g. low-res/10x for map acquisition, 60x for the actual image)
references a different hal-config and shutter-config.

## Workflow

#### Kilroy

[TODO... Roughly: Select "prime all", put sample in tube line,
click "image"; Kilroy fills the chamber; you remove bubbles; lock sample in.]

#### Hal

Set up your environment according to the instructions in `storm-control/storm_control/hal4000/INSTALL.txt`.
Then from `storm-control/storm_control/hal4000`:
    `python hal4000.py xml/[your-config-here].xml`

Load your hal-config and shutter-config (using Hal's File menu or by dragging and dropping).

[TODO: Autofocus]

#### Steve

Then run steve:
    `python storm-control/storm_control/steve/steve.py`

First acquire a mosaic. Position the stage/your sample over the objective, centered roughly on your region of interest
(or one of same).
If your stage can be zeroed, then zero it.
If your stage cannot be zeroed, then under "Tile Settings", click "Get Stage Position".
Set the grid size according to your needs, then click "Acquire".

Then under "Generate Positions", first, if you did not zero the stage, then you probably want to set the center
to whatever it was for "Tile Settings" (or adjust this center based on your mosaic result).
Then set the grid size and the spacing, and then click "Create".

The spacing value is expressed in microns. See the Steve section below for more information on what this should be.

You may end up generating points over areas that you are not interested in. In that case, you can select
those positions on the list and delete them.
You may have multiple areas of interest on your slide. In that case, you can set a new center and if necessary
a new grid size; then click "Create" again, and if necessary, pare away the points you don't want.
In this way you build up your final positions list; then click File > Save Positions.

#### Dave

[TODO. Roughly: Set dave-config and the list of positions; Dave generates complete list of tasks to run,
and then runs the tasks.]


## Notes

#### Qt

Dave, Hal, Steve, and Kilroy are Qt applications.
In particular, they are built with Qt for Python, the documentation for which is [here](https://doc.qt.io/qtforpython-6/index.html).

The UIs for Dave, Hal, and Steve are defined in `.ui` files generated by Qt Creator.
Use Qt Creator to view and edit these UIs. Then, use a Python Qt UIC (User Interface Compiler) to [compile](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/uifiles.html#option-a-generating-a-python-class) the `.ui` file to a Python file.

Precompiled Python files for the existing UIs are already committed to version control along with their corresponding `.ui` files;
these were generated by PyQt5 UIC 5.x; an executable `pyuic5` should be in your path if you are using a virtual environment and it is activated. For Qt 6, the equivalent tool is `pyside6-uic`.


#### Steve

Steve ultimately outputs a list of positions in the X-Y plane, for later use in Dave.
For each position, a tile image (a "field of view") is acquired which forms part of
a larger picture (a "movie").

Therefore, the appropriate distance between the FOVs varies according to the
objective that will be used (the magnification) and the pixel size on the camera chip.
(Together, those two things determine the real area captured by one FOV.)

Additionally, the distance should take into account the desired fractional overlap
between consecutive fields of view. The fractional overlap can be set in the parameters file
but the default in storm-control is 0.05 (5% on each side, 10% overall).

When using the "Generate Positions" function in Steve, the "Spacing" field must be
set to this distance, expressed in micrometers.

For example, with the Hamamatsu C14440-20UP and a 60x objective, this is
(6.5 micrometers per pixel edge) x (2304 pixels) / 60 = 249.6 micrometers per pixel;
then 249.6 * 0.95 = 237.12 micrometers.

Note that Steve's "Generate Positions" function outputs a grid in a snaking pattern
(reversing the x-coordinates every other row).
This allows the stage to move without large jumps when capturing the fields of view.

_(Note: When taking the initial low-resolution mosaic map, Steve actually calculates this
distance on its own: It first acquires the center tile image, converts the image numpy data
into a Qt pixmap, queries the pixmap for the image size in pixels, converts that size to micrometers
(the default pixel-to-micrometer factor in storm-control is 1.0), and then combines
this with information about the objective from the main configuration, along with
the fractional overlap, to determine the distance by which to multiply the current grid
offset and get the next stage position in micrometers. It then sends this position to the
stage module.)_


Steve also features a robust secret menu of hotkeys (the tooltips serve as quick reminders):
- Once you have selected a position on the list, you can use 8, 4, 2, and 6 like ~khjl~WASD, to move the position around.
- Once you have selected one or more positions on the list, use DELETE or BACKSPACE to delete the position(s).
- Inside the mosaic view, use SPACE to take a single picture, use 3, 5, 7, 9 to take an N by N-picture spiral,
  or use 'g' to take a grid of pictures (according to the size defined in Tile Settings > Grid Size). All of these start from
  the current cursor position.
- Inside the mosaic view, use
    - 'p' to add the current cursor position to the list of positions,
    - 's' to add the current cursor position to the list of sections,
    - 'h' to toggle drag mode,
    - 'y' to toggle select mode,
    - 'n' to add the current position to the center position for position generation.



## ALGOBIOLAB-SPECIFIC HARDWARE NOTES

#### ZABER XY STAGE

Model: [Zaber X-ADR130B100B-SAE53D12](https://www.zaber.com/manuals/X-ADR-AE#m-17-specifications).
This is a linear-motor XY stage.
Zaber linear-motor stage motion is expressed in unitless values ('data' values)
which are converted to real-world units according to a device-specific conversion factor,
the 'Encoder Count Size'; for this stage, that's 1nm.

The `<zaber_stage>` section of the configuration expresses values in micrometers and
specifies a `unit_to_um` factor.

Historically, Steve has been used with stages that can be zeroed, and its features have been built accordingly.
The Zaber X-ADR13 cannot be zeroed. This is not a problem, but it is good to keep in mind because for example
when acquiring Steve mosaics you need to first "Get Stage Position"; after which you may need to dig around a bit
for your fields of view in the bottom-right quadrant of the Steve mosaic display.

_(NB: The inability to zero *is* a problem with the Jupyter script flow, but we are moving away from that
and it's not relevant to the current codebase.)_


#### HAMAMATSU CAMERA

Model: [Hamamatsu C14440-20UP](https://www.hamamatsu.com/us/en/product/cameras/cmos-cameras/C14440-20UP.html).
The cell size (pixel size) is 6.5 micrometers (horizontal and vertical); the resolution is 2304x2304 pixels.
