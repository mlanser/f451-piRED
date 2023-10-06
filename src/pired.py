"""f451 Labs piRED Device Class.

The piRED Device class includes support for hardware extensions (e.g. Sense Hat, etc.),
core services (e.g. Adafruit IO, etc.), and uitilities (e.g. logger, etc.).

The class wraps -- and extends as needed -- the methods and functions supported by 
underlying libraries, and also keeps track of core counters, flags, etc.
"""

import time
import sys
import logging
import asyncio
import signal

from collections import deque
from random import randint
from pathlib import Path

from Adafruit_IO import Client, MQTTClient, RequestError, ThrottlingError

import constants as const
from helpers import convert_to_bool, convert_to_rgb, num_to_range, exit_now, EXIT_NOW

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

try:
    from sense_hat import SenseHat, ACTION_PRESSED, ACTION_HELD, ACTION_RELEASED
except ImportError:
    from mocks.fake_hat import FakeHat as SenseHat, ACTION_PRESSED, ACTION_HELD, ACTION_RELEASED


# =========================================================
#          G L O B A L S   A N D   H E L P E R S
# =========================================================
class Device:
    def __init__(self, sense, aio, logger, config):
        self.sense = sense
        self.aio = aio
        self.logger = logger
        self.config = config
        self.displRotation = 0
        self.displSleep = 0
        self.displMode = 0
        self.displProgress = False
        self.sleepCounter = 0
        # self.ioDelay = 0
        # self.delayCounter = 0
        # self.maxDelay = 0

    def init_SenseHat(self):
        """Initialize SenseHat
        
        Initialize the SenseHat device, set some default 
        parameters, and clear LED.

        Args:
            defRotation:
                Default rotation
        """
        self.sense.clear()                               # Clear 8x8 LED
        self.sense.low_light = True

        self.sense.set_rotation(self.displRotation)      # Set initial rotation
        self.sense.set_imu_config(False, False, False)   # Disable IMU functions

        self.sense.stick.direction_up = self._pushed_up
        self.sense.stick.direction_down = self._pushed_down
        self.sense.stick.direction_left = self._pushed_left
        self.sense.stick.direction_right = self._pushed_right
        self.sense.stick.direction_middle = self._pushed_middle

    def init_logger(self, logLvl, logFile=None):
        """Initialize logger
        
        This method will always initialize the logger with a stream 
        handler. But file handler will only be created if a file
        name has been provided.

        Args:
            logLvl:
                Log level used for handlers
            logFile:
                Path object for log file
        """
        self.logger.setLevel(logLvl)

        if logFile:
            fileHandler = logging.FileHandler(logFile)
            fileHandler.setLevel(logLvl)
            fileHandler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s: %(message)s"))
            self.logger.addHandler(fileHandler)

        streamHandler = logging.StreamHandler()
        streamHandler.setLevel(logLvl if logLvl == const.LOG_DEBUG else logging.ERROR)
        streamHandler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s: %(message)s"))
        self.logger.addHandler(streamHandler)

    def _pushed_up(self, event):
        """SenseHat Joystick UP event
        
        Rotate display by -90 degrees and reset screen blanking
        """
        if event.action != ACTION_RELEASED:
            self.displRotation = 270 if self.displRotation <= 0 else self.displRotation - const.ROTATE_90
            self.sleepCounter = self.displSleep 

    def _pushed_down(self, event):
        """SenseHat Joystick DOWN event
        
        Rotate display by +90 degrees and reset screen blanking
        """
        if event.action != ACTION_RELEASED:
            self.displRotation = 0 if self.displRotation >= 270 else self.displRotation + const.ROTATE_90 
            self.sleepCounter = self.displSleep 

    def _pushed_left(self, event):
        """SenseHat Joystick LEFT event
        
        Switch display mode by 1 mode and reset screen blanking
        """
        if event.action != ACTION_RELEASED:
            self.displMode = 4 if self.displMode <= 1 else self.displMode - 1
            self.sleepCounter = self.displSleep 

    def _pushed_right(self, event):
        """SenseHat Joystick RIGHT event
        
        Switch display mode by 1 mode and reset screen blanking
        """
        if event.action != ACTION_RELEASED:
            self.displMode = 1 if self.displMode >= 4 else self.displMode + 1
            self.sleepCounter = self.displSleep 

    def _pushed_middle(self, event):
        """SenseHat Joystick MIDDLE (down) event
        
        Turn off display and reset screen blanking
        """
        if event.action != ACTION_RELEASED:
            self.displMode = const.DISPL_BLANK
            self.sleepCounter = 1 

    def get_feed_info(self, feedKwd, default=""):
        """Get Adafruit IO feed info

        Args:
            feedKwd:
                'str' with feed keyword to find in config/settings
        """
        feed = get_setting(self.config, feedKwd, default)
        try:
            info = self.aio.feeds(feed)

        except RequestError as e:
            self.logger.log(logging.ERROR, f"Failed to get feed info - ADAFRUIT REQUEST ERROR: {e}")
            raise
        
        return info

    def get_sensor_data(self):
        """
        Read sensor data and round values to 1 decimal place

        Returns:
            'tuple' with 1 data point from each of the SenseHat sensors
        """
        tempC = round(self.sense.get_temperature(), 1)     # Temperature in C
        press = round(self.sense.get_pressure(), 1)        # Presure in hPa
        humid = round(self.sense.get_humidity(), 1)        # Humidity 

        return tempC, press, humid 

    def get_setting(settings, key, default=None):
        """Get a config value from settings
        
        This function will use the value from settings (TOML), but 
        can use a default value if settings value is not provided.

        Args:
            settings:
                'dict' with settings values
            key:
                'str' with name of settings key
            defaul:
                Default value

        Returns:
            Settings value        
        """
        return settings[key] if key in settings else default

    def log(self, lvl, msg):
            """Wrapper of Logger.log()"""
            self.logger.log(lvl, msg)

    def blank_LED(self):
        """Show clear/blank LED"""
        self.sense.clear()
        
    def reset_LED(self):
        """Reset and clear LED"""
        self.sense.clear()
        self.sense.low_light = False

    def sparkle_LED(self):
        """Show random sparkles on LED"""
        x = randint(0, 7)
        y = randint(0, 7)
        r = randint(0, 255)
        g = randint(0, 255)
        b = randint(0, 255)

        toggle = randint(0, 3)

        if toggle != 0:
            self.sense.set_pixel(x, y, r, g, b)
        else:    
            self.sense.clear()

    def update_LED(self, data, inMin, inMax):
        """
        Update all pixels on SenseHat 8x8 LED with new color values

        Args:
            data:
                'list' with one value for each column of pixels on LED
            inMin:
                Min value of range for (sensor) data
            inMax:
                Max value of range for (sensor) data
        """
        normalized = [round(num_to_range(val, inMin, inMax, 0, const.LED_MAX_ROW)) for val in data]
        maxCol = min(const.LED_MAX_COL, len(normalized))

        pixels = [const.RGB_BLACK if row < (const.LED_MAX_ROW - normalized[col]) else convert_to_rgb(data[col], inMin, inMax, COLORS) for row in range(const.LED_MAX_ROW) for col in range(maxCol)]
        # self.sense.set_rotation(self.displRotation)
        self.sense.set_pixels(pixels)
    
    def update_LED_progress(self, inVal, maxVal=100):
        """Update progressbar on bottom row of LED

        Args:
            inVal:
                Value to represent on progressbar
            maxVal:
                Max value so we can calculate percentage
        """
        # Convert value to percentange and map against num pixels in a row
        normalized = int(num_to_range(inVal / maxVal, 0.0, 1.0, 0.0, float(const.LED_MAX_COL)))
        
        # Update LED bottom row
        for x in range(0, normalized):
            self.sense.set_pixel(x, const.LED_MAX_ROW - 1, const.RGB_PROGRESS)

    async def send_sensor_data(self, data):
        """Send sensor data to Adafruit IO

        Args:
            data:
                'dict' with feed key and data point

        Raises:
            RequestError:
                When API request fails
            ThrottlingError:
                When exceeding Adafruit IO rate limit
        """
        global logger

        try:
            self.aio.send_data(data["feed"].key, data["data"])
        except RequestError as e:
            self.logger.log(logging.ERROR, f"Upload failed for {data['feed'].key} - REQUEST ERROR: {e}")
            raise RequestError
        except ThrottlingError as e:
            self.logger.log(logging.ERROR, f"Upload failed for {data['feed'].key} - THROTTLING ERROR: {e}")
            raise ThrottlingError


#         - 0    1    2    3    4    5    6    7 -
EMPTY_Q = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
COLORS  = [const.RGB_BLUE, const.RGB_GREEN, const.RGB_YELLOW, const.RGB_RED]

LOGLVL = "ERROR"
LOGFILE = "f451-piRED.log"
LOGNAME = "f451-piRED"


# =========================================================
#              H E L P E R   F U N C T I O N S
# =========================================================
def get_setting(settings, key, default=None):
    """Get a config value from settings
    
    This function will use the value from settings (TOML), but 
    can use a default value if settings value is not provided.

    Args:
        settings:
            'dict' with settings values
        key:
            'str' with name of settings key
        defaul:
            Default value

    Returns:
        Settings value        
    """
    return settings[key] if key in settings else default
