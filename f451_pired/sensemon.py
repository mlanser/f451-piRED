#!/usr/bin/env python3
"""f451 Labs SenseMon application on piRED device.

This application is designed for the f451 Labs piRED device which is also equipped with 
a Sense HAT add-on. The main objective is to continously read environment data (e.g. 
temperature, barometric pressure, and humidity from the Sense HAT sensors and then upload 
the data to the Adafruit IO service.

To launch this application from terminal:

    $ nohup python -u sensemon.py > sensemon.out &

This command launches the 'sensemon' application in the background. The application will 
keep running even after the terminal window is closed. Any output will be redirected to 
the 'sensemon.out' file.    

It's also possible to install this application via 'pip' from Github and one 
can launch the application as follows:

    $ nohup sensemon > sensemon.out &

NOTE: This code is based on the 'luftdaten_combined.py' example from the Enviro+ Python
      example files. Main modifications include support for Adafruit.io, using Python 
      'deque' to manage data queues, moving device support to a separate class, etc.

      Furthermore, this application is designed to get sensor data from the Raspberry 
      Pi Sense HAT which has fewer sensors than the Enviro+, an 8x8 LED, and a joystick.
      
      We also support additional display modes including a screen-saver mode, support 
      for 'settings.toml', and more.

Dependencies:
    - adafruit-io - only install if you have an account with Adafruit IO

TODO:
    - add support for custom colors in 'settings.toml'
    - add support for custom range factor in 'settings.toml'
"""

import argparse
import time
import sys
import asyncio

from collections import deque
from datetime import datetime
from pathlib import Path

from . import constants as const
from . import sensemon_ui as UI

import f451_common.common as f451Common
import f451_logger.logger as f451Logger
import f451_cloud.cloud as f451Cloud

import f451_sensehat.sensehat as f451SenseHat
import f451_sensehat.sensehat_data as f451SenseData

from rich.live import Live
from rich.traceback import install as install_rich_traceback

from Adafruit_IO import RequestError, ThrottlingError


# Install Rich 'traceback' to make (debug) life is
# easier. Trust me!
install_rich_traceback(show_locals=True)


# fmt: off
# =========================================================
#          G L O B A L    V A R S   &   I N I T S
# =========================================================
APP_VERSION = '0.0.1'
APP_NAME = 'f451 Labs piRED - SenseMon'
APP_NAME_SHORT = 'SenseMon'
APP_LOG = 'f451-pired-sensemon.log'     # Individual logs for devices with multiple apps
APP_SETTINGS = 'settings.toml'          # Standard for all f451 Labs projects
APP_DIR = Path(__file__).parent         # Find dir for this app

APP_MIN_SENSOR_READ_WAIT = 1            # Min wait in sec between sensor reads
APP_MIN_PROG_WAIT = 5                   # Remaining min wait time to display prog bar
APP_WAIT_1SEC = 1
APP_MAX_DATA = 120                      # Max number of data points in the queue
APP_DELTA_FACTOR = 0.02                 # Any change within X% is considered negligable

APP_DATA_TYPES = ['temperature', 'pressure', 'humidity']

APP_DISPLAY_MODES = {
    f451SenseHat.KWD_DISPLAY_MIN: const.MAX_DISPL,
    f451SenseHat.KWD_DISPLAY_MAX: const.MIN_DISPL,
}

# Load settings
CONFIG = f451Common.load_settings(APP_DIR.joinpath(APP_SETTINGS))

# Initialize device instance which includes all sensors
# and LED display on Sense HAT
SENSE_HAT = f451SenseHat.SenseHat(CONFIG)

# Initialize logger and IO cloud
LOGGER = f451Logger.Logger(CONFIG, LOGFILE=APP_LOG)
UPLOADER = f451Cloud.Cloud(CONFIG)

# Verify that feeds exist
try:
    FEED_TEMPS = UPLOADER.aio_feed_info(CONFIG.get(const.KWD_FEED_TEMPS, None))
    FEED_PRESS = UPLOADER.aio_feed_info(CONFIG.get(const.KWD_FEED_PRESS, None))
    FEED_HUMID = UPLOADER.aio_feed_info(CONFIG.get(const.KWD_FEED_HUMID, None))

except RequestError as e:
    LOGGER.log_error(f'Application terminated due to REQUEST ERROR: {e}')
    sys.exit(1)

# We use these timers to track when to upload data and/or set
# display to sleep mode. Normally we'd want them to be local vars
# inside 'main()'. However, since we need them reset them in the
# button actions, they need to be global.
timeUpdate = time.time()
displayUpdate = timeUpdate
# fmt: on


# =========================================================
#              H E L P E R   F U N C T I O N S
# =========================================================
def debug_config_info(cliArgs, console=None):
    """Print/log some basic debug info."""

    if console:
        console.rule('Config Settings', style='grey', align='center')
    else:
        LOGGER.log_debug('-- Config Settings --')

    LOGGER.log_debug(f'DISPL ROT:   {SENSE_HAT.displRotation}')
    LOGGER.log_debug(f'DISPL MODE:  {SENSE_HAT.displMode}')
    LOGGER.log_debug(f'DISPL PROGR: {SENSE_HAT.displProgress}')
    LOGGER.log_debug(f'SLEEP TIME:  {SENSE_HAT.displSleepTime}')
    LOGGER.log_debug(f'SLEEP MODE:  {SENSE_HAT.displSleepMode}')
    LOGGER.log_debug(f'IO DEL:      {CONFIG.get(const.KWD_DELAY, const.DEF_DELAY)}')
    LOGGER.log_debug(f'IO WAIT:     {CONFIG.get(const.KWD_WAIT, const.DEF_WAIT)}')
    LOGGER.log_debug(f'IO THROTTLE: {CONFIG.get(const.KWD_THROTTLE, const.DEF_THROTTLE)}')

    LOGGER.log_debug(
        f'TEMP COMP:   {CONFIG.get(f451Common.KWD_TEMP_COMP, f451Common.DEF_TEMP_COMP_FACTOR)}'
    )

    # Display Raspberry Pi serial and Wi-Fi status
    LOGGER.log_debug(f'Raspberry Pi serial: {f451Common.get_RPI_serial_num()}')
    LOGGER.log_debug(
        f'Wi-Fi: {(f451Common.STATUS_YES if f451Common.check_wifi() else f451Common.STATUS_UNKNOWN)}'
    )

    # Display CLI args
    LOGGER.log_debug(f'CLI Args:\n{cliArgs}')


def prep_data_for_screen(inData, labelsOnly=False, conWidth=UI.APP_2COL_MIN_WIDTH):
    """Prep data for display in terminal

    We only display temperature, humidity, and pressure, and we
    need to normalize all data to fit within the 1-8 range. We
    can use 0 for missing values and for values that fall outside the
    valid range for the Sense HAT, which we'll assume are erroneous.

    NOTE: We need to map the data sets agains a numeric range of 1-8 so
          that we can display them as sparkline graphs in the terminal.

    NOTE: We're using the 'limits' list to color the values, which means
          we need to create a special 'coloring' set for the sparkline
          graphs using converted limit values.

          The limits list has 4 values (see also 'SenseData' class) and
          we need to map them to colors:

          Limit set [A, B, C, D] means:

                     val <= A -> Dangerously Low    = "bright_red"
                B >= val >  A -> Low                = "bright_yellow"
                C >= val >  B -> Normal             = "green"
                D >= val >  C -> High               = "cyan"
                     val >  D -> Dangerously High   = "blue"

          Note that the Sparkline library has a specific syntax for
          limits and colors:

            "<name of color>:<gt|eq|lt>:<value>"

          Also, we only care about 'low', 'normal', and 'high'

    Args:
        inData: 'dict' with Sense HAT data

    Returns:
        'list' with processed data and only with data rows (i.e. temp,
        humidity, pressure) and columns (i.e. label, last data pt, and
        sparkline) that we want to display. Each row in the list is
        designed for display in the terminal.
    """
    outData = []

    def _is_valid(val, valid):
        """Verify value 'valid'

        We know what 'valid' ranges are for each sensor.
        This method allows us to verify that a given
        value falls within that range. Any value outside
        the range should be considered an error.

        Args:
            val: value to check
            valid: 'tuple' with min/max values for valid range

        Returns:
            'True' if value is valid, else 'False'
        """
        if val is not None and valid is not None:
            return float(val) >= float(valid[0]) and float(val) <= float(valid[1])

        return False

    def _in_range(first, second, factor):
        """Check if 1st value is within X% of 2nd value

        This method allows us to compare 2 values to see
        if they're equal-ish, and we can use this to even
        out minor deviations between sensor readings.

        Args:
            first: value to compare
            second: value to compare against
            factor: factor to extend range for comparison

        Returns:
            1: above range
            0: within range
           -1: below range
        """
        # If either value is 'None' then we have to
        # assume 'no change' ... 'coz we can't compare
        if first is None or second is None:
            return 0

        lower = second * (1 - factor)
        upper = second * (1 + factor)
        if first > upper:       # Above range
            return 1
        elif first < lower:     # Below range
            return -1
        else:
            return 0            # Within range

    def _sparkline_colors(limits, customColors=None):
        """Create color mapping for sparkline graphs

        This function creates the 'color' list which allows
        the 'sparklines' library to add add correct ANSI
        color codes to the graph.

        Args:
            limits: list with limits -- see SenseHat module for details
            customColors: (optional) custom color map

        Return:
            'list' with definitions for 'emph' param of 'sparklines' method
        """
        colorMap = f451SenseData.COLOR_MAP if customColors is None else customColors

        return [
            f'{colorMap[f451SenseData.COLOR_HIGH]}:gt:{round(limits[2], 1)}',  # High   # type: ignore
            f'{colorMap[f451SenseData.COLOR_NORM]}:eq:{round(limits[2], 1)}',  # Normal # type: ignore
            f'{colorMap[f451SenseData.COLOR_NORM]}:lt:{round(limits[2], 1)}',  # Normal # type: ignore
            f'{colorMap[f451SenseData.COLOR_LOW]}:eq:{round(limits[1], 1)}',  # Low    # type: ignore
            f'{colorMap[f451SenseData.COLOR_LOW]}:lt:{round(limits[1], 1)}',  # Low    # type: ignore
        ]

    def _dataPt_color(val, limits, default='', customColors=None):
        """Determine color mapping for specific value

        Args:
            val: value to check
            limits: list with limits -- see SenseHat module for details
            default: (optional) default color name string
            customColors: (optional) custom color map

        Return:
            'list' with definitions for 'emph' param of 'sparklines' method
        """
        color = default
        colorMap = f451SenseData.COLOR_MAP if customColors is None else customColors

        if val is not None:
            if val > round(limits[2], 1):
                color = colorMap[f451SenseData.COLOR_HIGH]
            elif val <= round(limits[1], 1):
                color = colorMap[f451SenseData.COLOR_LOW]
            else:
                color = colorMap[f451SenseData.COLOR_NORM]

        return color

    # Process each data row and create a new data structure that we can use
    # for displaying all necessary data in the terminal.
    for key, row in inData.items():
        if key in APP_DATA_TYPES:
            # Create new crispy clean set :-)
            dataSet = {
                'sparkData': [],
                'sparkColors': [],
                'sparkMinMax': (None, None),
                'dataPt': None,
                'dataPtOK': True,
                'dataPtDelta': 0,
                'dataPtColor': '',
                'unit': row['unit'],
                'label': row['label'],
            }

            # If we only need labels, then we'll skip to
            # next iteration of the loop
            if labelsOnly:
                outData.append(dataSet)
                continue

            # Data slice we can display in table row
            graphWidth = min(int(conWidth / 2), 40)
            dataSlice = list(row['data'])[-graphWidth:]

            # Get filtered data to calculate min/max. Note that 'valid' data
            # will have only valid values. Any invalid values would have been
            # replaced with 'None' values. We can display this set using the
            # 'sparklines' library. We continue refining the data by removing
            # all 'None' values to get a 'clean' set, which we can use to
            # establish min/max values for the set.
            dataValid = [i if _is_valid(i, row['valid']) else None for i in dataSlice]
            dataClean = [i for i in dataValid if i is not None]

            # Current data point is valid if value is valid. So we set 'OK' flag
            # to 'True' if data is valid or missing (i.e. None)
            dataPt = dataSlice[-1] if _is_valid(dataSlice[-1], row['valid']) else None
            dataPtOK = dataPt or dataSlice[-1] is None

            # We determine up/down/sideways trend by looking at delate between
            # current value and previous value. If current and/or previous value
            # is 'None' for whatever reason, then we assume 'sideways' (0)trend.
            dataPtPrev = dataSlice[-2] if _is_valid(dataSlice[-2], row['valid']) else None
            dataPtDelta = _in_range(dataPt, dataPtPrev, APP_DELTA_FACTOR)

            # Update data set
            dataSet['sparkData'] = dataValid
            dataSet['sparkColors'] = _sparkline_colors(row['limits'])
            dataSet['sparkMinMax'] = (
                (min(dataClean), max(dataClean)) if any(dataClean) else (None, None)
            )

            dataSet['dataPt'] = dataPt
            dataSet['dataPtOK'] = dataPtOK
            dataSet['dataPtDelta'] = dataPtDelta
            dataSet['dataPtColor'] = _dataPt_color(dataPt, row['limits'])

            outData.append(dataSet)

    return outData


def init_cli_parser():
    """Initialize CLI (ArgParse) parser.

    Initialize the ArgParse parser with the CLI 'arguments' and
    return a new parser instance.

    Returns:
        ArgParse parser instance
    """
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description=f'{APP_NAME} [v{APP_VERSION}] - read sensor data from Sense HAT and upload to Adafruit IO and/or Arduino Cloud.',
        epilog='NOTE: This application requires active accounts with corresponding cloud services.',
    )

    parser.add_argument(
        '-V',
        '--version',
        action='store_true',
        help='display script version number and exit',
    )
    parser.add_argument('-d', '--debug', action='store_true', help='run script in debug mode')
    parser.add_argument(
        '--cron',
        action='store_true',
        help='use when running as cron job - run script once and exit',
    )
    parser.add_argument(
        '--noCLI',
        action='store_true',
        default=False,
        help='do not display output on CLI',
    )
    parser.add_argument(
        '--noLED',
        action='store_true',
        default=False,
        help='do not display output on LED',
    )
    parser.add_argument(
        '--progress',
        action='store_true',
        help='show upload progress bar on LED',
    )
    parser.add_argument(
        '--log',
        action='store',
        type=str,
        help='name of log file',
    )
    parser.add_argument(
        '--uploads',
        action='store',
        type=int,
        default=-1,
        help='number of uploads before exiting',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        default=False,
        help='show output to CLI stdout',
    )

    return parser


async def upload_sensor_data(*args, **kwargs):
    """Send sensor data to cloud services.

    This helper function parses and sends enviro data to
    Adafruit IO and/or Arduino Cloud.

    NOTE: This function will upload specific environment
          data using the following keywords:

          'temperature' - temperature data
          'pressure'    - barometric pressure
          'humidity'    - humidity

    Args:
        args:
            User can provide single 'dict' with data
        kwargs:
            User can provide individual data points as key-value pairs
    """
    # We combine 'args' and 'kwargs' to allow users to provide a 'dict' with
    # all data points and/or individual data points (which could override
    # values in the 'dict').
    data = {**args[0], **kwargs} if args and isinstance(args[0], dict) else kwargs

    sendQ = []

    # Send temperature data ?
    if data.get(const.KWD_DATA_TEMPS, None) is not None:
        sendQ.append(UPLOADER.aio_send_data(FEED_TEMPS.key, data.get(const.KWD_DATA_TEMPS)))  # type: ignore

    # Send barometric pressure data ?
    if data.get(const.KWD_DATA_PRESS, None) is not None:
        sendQ.append(UPLOADER.aio_send_data(FEED_PRESS.key, data.get(const.KWD_DATA_PRESS)))  # type: ignore

    # Send humidity data ?
    if data.get(const.KWD_DATA_HUMID, None) is not None:
        sendQ.append(UPLOADER.aio_send_data(FEED_HUMID.key, data.get(const.KWD_DATA_HUMID)))  # type: ignore

    # deviceID = SENSE_HAT.get_ID(DEF_ID_PREFIX)

    await asyncio.gather(*sendQ)


def btn_up(event):
    """SenseHat Joystick UP event

    Rotate display by -90 degrees and reset screen blanking
    """
    global displayUpdate

    if event.action != f451SenseHat.BTN_RELEASE:
        SENSE_HAT.display_rotate(-1)
        displayUpdate = time.time()


def btn_down(event):
    """SenseHat Joystick DOWN event

    Rotate display by +90 degrees and reset screen blanking
    """
    global displayUpdate

    if event.action != f451SenseHat.BTN_RELEASE:
        SENSE_HAT.display_rotate(1)
        displayUpdate = time.time()


def btn_left(event):
    """SenseHat Joystick LEFT event

    Switch display mode by 1 mode and reset screen blanking
    """
    global displayUpdate

    if event.action != f451SenseHat.BTN_RELEASE:
        SENSE_HAT.update_display_mode(-1)
        displayUpdate = time.time()


def btn_right(event):
    """SenseHat Joystick RIGHT event

    Switch display mode by 1 mode and reset screen blanking
    """
    global displayUpdate

    if event.action != f451SenseHat.BTN_RELEASE:
        SENSE_HAT.update_display_mode(1)
        displayUpdate = time.time()


def btn_middle(event):
    """SenseHat Joystick MIDDLE (down) event

    Turn display on/off
    """
    global displayUpdate

    if event.action != f451SenseHat.BTN_RELEASE:
        # Wake up?
        if SENSE_HAT.displSleepMode:
            SENSE_HAT.update_sleep_mode(False)
            displayUpdate = time.time()
        else:
            SENSE_HAT.update_sleep_mode(True)


APP_JOYSTICK_ACTIONS = {
    f451SenseHat.KWD_BTN_UP: btn_up,
    f451SenseHat.KWD_BTN_DWN: btn_down,
    f451SenseHat.KWD_BTN_LFT: btn_left,
    f451SenseHat.KWD_BTN_RHT: btn_right,
    f451SenseHat.KWD_BTN_MDL: btn_middle,
}


# =========================================================
#      M A I N   F U N C T I O N    /   A C T I O N S
# =========================================================
def main(cliArgs=None):
    """Main function.

    This function will goes through the setup and then runs the
    main application loop.

    NOTE:
     -  Application will exit with error level 1 if invalid Adafruit IO
        or Arduino Cloud feeds are provided

     -  Application will exit with error level 0 if either no arguments
        are entered via CLI, or if arguments '-V' or '--version' are used.
        No data will be uploaded will be sent in that case.

    Args:
        cliArgs:
            CLI arguments used to start application
    """
    global LOGGER
    global SENSE_HAT
    global timeUpdate
    global displayUpdate

    # Parse CLI args and show 'help' and exit if no args
    cli = init_cli_parser()
    cliArgs, _ = cli.parse_known_args(cliArgs)
    if not cliArgs and len(sys.argv) == 1:
        cli.print_help(sys.stdout)
        sys.exit(0)

    if cliArgs.version:
        print(f'{APP_NAME} (v{APP_VERSION})')
        sys.exit(0)

    # Initialize core data queues and related variables
    senseData = f451SenseData.SenseData(None, APP_MAX_DATA)
    tempCompFactor = CONFIG.get(f451Common.KWD_TEMP_COMP, f451Common.DEF_TEMP_COMP_FACTOR)
    cpuTempsQMaxLen = CONFIG.get(f451Common.KWD_MAX_LEN_CPU_TEMPS, f451Common.MAX_LEN_CPU_TEMPS)

    # If comp factor is 0 (zero), then do NOT compensate
    # for CPU temp
    tempCompYN = tempCompFactor > 0

    cpuTempsQ = []
    if tempCompYN:
        cpuTempsQ = deque(
            [SENSE_HAT.get_CPU_temp(False)] * cpuTempsQMaxLen, 
            maxlen=cpuTempsQMaxLen
        )

    # Initialize UI for terminal
    screen = UI.SenseMonUI()
    screen.initialize(
        APP_NAME,
        APP_NAME_SHORT,
        APP_VERSION,
        prep_data_for_screen(senseData.as_dict(), True),
        not cliArgs.noCLI,
    )

    # Initialize Sense HAT joystick and LED display
    SENSE_HAT.joystick_init(**APP_JOYSTICK_ACTIONS)
    SENSE_HAT.display_init(**APP_DISPLAY_MODES)
    SENSE_HAT.update_sleep_mode(cliArgs.noLED)

    if cliArgs.progress:
        SENSE_HAT.displProgress = True

    # Get core settings
    ioFreq = CONFIG.get(const.KWD_FREQ, const.DEF_FREQ)
    ioDelay = CONFIG.get(const.KWD_DELAY, const.DEF_DELAY)
    ioWait = max(CONFIG.get(const.KWD_WAIT, const.DEF_WAIT), APP_MIN_SENSOR_READ_WAIT)
    ioThrottle = CONFIG.get(const.KWD_THROTTLE, const.DEF_THROTTLE)
    ioRounding = CONFIG.get(const.KWD_ROUNDING, const.DEF_ROUNDING)
    ioUploadAndExit = cliArgs.cron

    logLvl = CONFIG.get(f451Logger.KWD_LOG_LEVEL, f451Logger.LOG_NOTSET)
    debugMode = logLvl == f451Logger.LOG_DEBUG

    # Update log file or level?
    if cliArgs.debug:
        LOGGER.set_log_level(f451Logger.LOG_DEBUG)
        logLvl = f451Logger.LOG_DEBUG
        debugMode = True

    if cliArgs.log is not None:
        LOGGER.set_log_file(logLvl, cliArgs.log)

    if debugMode:
        debug_config_info(cliArgs, screen.console)

    # -- Main application loop --
    timeSinceUpdate = 0
    timeUpdate = time.time()
    displayUpdate = timeUpdate
    uploadDelay = ioDelay  # Ensure that we do NOT upload first reading
    maxUploads = int(cliArgs.uploads)
    numUploads = 0
    exitNow = False

    # Let user know when first upload will happen
    screen.update_upload_next(timeUpdate + uploadDelay)

    # If log level <= INFO
    LOGGER.log_info('-- START Data Logging --')

    with Live(screen.layout, screen=True, redirect_stderr=False) as live:  # noqa: F841
        try:
            while not exitNow:
                timeCurrent = time.time()
                timeSinceUpdate = timeCurrent - timeUpdate
                SENSE_HAT.update_sleep_mode(
                    (timeCurrent - displayUpdate) > SENSE_HAT.displSleepTime, cliArgs.noLED
                )

                # --- Get sensor data ---
                #
                screen.update_action('Reading sensors ...')

                # Get raw temp from sensor
                tempRaw = tempComp = SENSE_HAT.get_temperature()

                # Do we need to compensate for CPUY temp?
                if tempCompYN:
                    # Get current CPU temp, add to queue, and calculate new average
                    #
                    # NOTE: This feature relies on the 'vcgencmd' which is found on
                    #       RPIs. If this is not run on a RPI (e.g. during testing),
                    #       then we need to neutralize the 'cpuTemp' compensation.
                    cpuTempsQ.append(SENSE_HAT.get_CPU_temp(False))
                    cpuTempAvg = sum(cpuTempsQ) / float(cpuTempsQMaxLen)

                    # Smooth out with some averaging to decrease jitter
                    tempComp = tempRaw - ((cpuTempAvg - tempRaw) / tempCompFactor)

                # Get barometric pressure and humidity data
                pressRaw = SENSE_HAT.get_pressure()
                humidRaw = SENSE_HAT.get_humidity()
                #
                # ---

                # Is it time to upload data?
                if timeSinceUpdate >= uploadDelay:
                    screen.update_action('Uploading ...')
                    try:
                        # asyncio.run(
                        #     upload_sensor_data(
                        #         temperature=round(tempComp, ioRounding),
                        #         pressure=round(pressRaw, ioRounding),
                        #         humidity=round(humidRaw, ioRounding),
                        #         deviceID=f451Common.get_RPI_ID(f451Common.DEF_ID_PREFIX),
                        #     )
                        # )
                        time.sleep(10)

                    except RequestError as e:
                        LOGGER.log_error(f'Application terminated: {e}')
                        sys.exit(1)

                    except ThrottlingError:
                        # Keep increasing 'ioDelay' each time we get
                        # a 'ThrottlingError'
                        uploadDelay += ioThrottle

                    else:
                        # Reset 'uploadDelay' back to normal 'ioFreq'
                        # on successful upload
                        numUploads += 1
                        uploadDelay = ioFreq
                        exitNow = exitNow or ioUploadAndExit
                        screen.update_upload_status(
                            timeCurrent,
                            UI.STATUS_OK,
                            timeCurrent + uploadDelay,
                            numUploads,
                            maxUploads,
                        )
                        LOGGER.log_info(
                            f'Uploaded: TEMP: {round(tempComp, ioRounding)} - PRESS: {round(pressRaw, ioRounding)} - HUMID: {round(humidRaw, ioRounding)}'
                        )

                    finally:
                        timeUpdate = timeCurrent
                        exitNow = (maxUploads > 0) and (numUploads >= maxUploads)
                        screen.update_action(UI.STATUS_LBL_WAIT)

                # Update data set and display to terminal as needed
                senseData.temperature.data.append(tempComp)
                senseData.pressure.data.append(pressRaw)
                senseData.humidity.data.append(humidRaw)
                screen.update_data(prep_data_for_screen(senseData.as_dict()))

                # Check display mode. Each mode corresponds to a data type
                if SENSE_HAT.displMode == const.IDX_TEMP:  # type = "temperature"
                    SENSE_HAT.display_as_graph(senseData.temperature.as_dict())

                elif SENSE_HAT.displMode == const.IDX_PRESS:  # type = "pressure"
                    SENSE_HAT.display_as_graph(senseData.pressure.as_dict())

                elif SENSE_HAT.displMode == const.IDX_HUMID:  # type = "humidity"
                    SENSE_HAT.display_as_graph(senseData.humidity.as_dict())

                else:  # Display sparkles
                    SENSE_HAT.display_sparkle()

                # Are we done? And do we have to wait a bit before next sensor read?
                if not exitNow:
                    # If we'tre not done and there's a substantial wait before we can
                    # read the sensors again, then lets display and update the progress
                    # bar as needed. Once the wait is done, we can go through this whole
                    # loop all over again ... phew!
                    if ioWait > APP_MIN_PROG_WAIT:
                        progress = screen.init_progressbar()
                        task = progress.add_task('Waiting for sensors ...')
                        screen.update_progress(progress)
                        for i in range(ioWait):
                            progress.update(task, completed=int(i / ioWait * 100))
                            SENSE_HAT.display_progress(timeSinceUpdate / uploadDelay)
                            time.sleep(APP_WAIT_1SEC)
                    else:
                        # screen.update_action(UI.STATUS_LBL_WAIT)
                        # screen.update_action("TEST 1-2-3")
                        time.sleep(ioWait)

        except KeyboardInterrupt:
            exitNow = True

    # If log level <= INFO
    LOGGER.log_info('-- END Data Logging --')

    # A bit of clean-up before we exit ...
    SENSE_HAT.display_reset()
    SENSE_HAT.display_off()

    # ... and display summary info
    print(f'Work end:    {(datetime.now()):%a %b %-d, %Y at %-I:%M:%S %p}')
    print(f'Num uploads: {numUploads}')
    # console.rule(style="grey", align="center")


# =========================================================
#            G L O B A L   C A T C H - A L L
# =========================================================
if __name__ == '__main__':
    main()  # pragma: no cover
