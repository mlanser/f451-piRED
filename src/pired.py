#!/usr/bin/env python3
"""f451 Labs piRED application.

This application is designed for the f451 Labs piRED device which is also equipped with 
a SenseHat add-on. This application will continously read environment data (e.g. temperature, 
barometric pressure, and humidity from the SenseHat sensors and then upload this data to 
the Adafruit IO service.
"""

import time
import sys
import tomli
import logging
import asyncio

from collections import deque
from random import randrange, randint
from pathlib import Path

from Adafruit_IO import Client, MQTTClient, RequestError, ThrottlingError

import constants as const

try:
    from sense_hat import SenseHat, ACTION_PRESSED, ACTION_HELD, ACTION_RELEASED
except ImportError:
    from mocks.fake_hat import FakeHat as SenseHat, ACTION_PRESSED, ACTION_HELD, ACTION_RELEASED


# =========================================================
#          G L O B A L S   A N D   H E L P E R S
# =========================================================
EPSILON = sys.float_info.epsilon                      # Smallest possible difference.

#         - 0    1    2    3    4    5    6    7 -
EMPTY_Q = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
COLORS  = [const.RGB_BLUE, const.RGB_GREEN, const.RGB_YELLOW, const.RGB_RED]

LOGLVL = "INFO"
LOGFILE = "f451-piRED.log"
LOGNAME = "f451-piRED"


# =========================================================
#              H E L P E R   F U N C T I O N S
# =========================================================
def init_logger(logLvl, logFile=None):
    """Initialize logger
    
    This function will always initialize the logger with a stream 
    handler. However, a file handler will only be created if a file
    name has been provided.

    Args:
        logLvl:
            Log level used for handlers
        logFile:
            Path object for log file

    Returns:
        Logger instance
    """
    logger = logging.getLogger("f451-piRED")
    logger.setLevel(logLvl)

    if logFile:
        fileHandler = logging.FileHandler(logFile)
        fileHandler.setLevel(logLvl)
        fileHandler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s: %(message)s"))
        logger.addHandler(fileHandler)

    streamHandler = logging.StreamHandler()
    streamHandler.setLevel(logging.ERROR)
    streamHandler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s: %(message)s"))
    logger.addHandler(streamHandler)

    return logger


def pushed_up(event):
    """SenseHat Joystick UP event"""
    global displRotation

    if event.action != ACTION_RELEASED:
        displRotation = 270 if displRotation <= 0 else displRotation - const.ROTATE_90 


def pushed_down(event):
    """SenseHat Joystick DOWN event"""
    global displRotation

    if event.action != ACTION_RELEASED:
        displRotation = 0 if displRotation >= 270 else displRotation + const.ROTATE_90 


def pushed_left(event):
    """SenseHat Joystick LEFT event"""
    global displMode

    if event.action != ACTION_RELEASED:
        displMode = 4 if displMode <= 1 else displMode - 1


def pushed_right(event):
    """SenseHat Joystick RIGHT event"""
    global displMode

    if event.action != ACTION_RELEASED:
        displMode = 1 if displMode >= 4 else displMode + 1


def pushed_middle(event):
    """SenseHat Joystick RIGHT event"""
    global displMode

    if event.action != ACTION_RELEASED:
        displMode = const.DISPL_BLANK


def num_to_range(num, inMin, inMax, outMin, outMax):
    """Map value to range

    We use this function to map values (e.g. temp, etc.) against the Y-axis of 
    the SenseHat 8x8 LED display. This means that all values must be mapped 
    against a range of 0-7.

    Based on code found here: https://www.30secondsofcode.org/python/s/num-to-range/

    Args:
        num:
            Number to map against range
        inMin:
            Min value of range for numbers to be converted
        inMax:
            Max value of range for numbers to be converted
        outMin:
            Min value of target range
        outMax:
            Max value of target range

    Returns:
        'float'
    """
    return outMin + (float(num - inMin) / float(inMax - inMin) * (outMax - outMin))


def convert_to_rgb(num, inMin, inMax, colors):
    """
    Map a value to RGB

    Based on reply found on StackOverflow by `martineau`: 

    See: https://stackoverflow.com/questions/20792445/calculate-rgb-value-for-a-range-of-values-to-create-heat-map

    Args:
        num:
            Number to convert/map to RGB
        inMin:
            Min value of range for numbers to be converted
        inMax:
            Max value of range for numbers to be converted
        colors:
            series of RGB colors delineating a series of adjacent 
            linear color gradients.

    Returns:
        'tuple' with RGB value
    """

    # Determine where the given value falls proportionality within
    # the range from inMin->inMax and scale that fractional value
    # by the total number in the `colors` palette.
    i_f = float(num - inMin) / float(inMax - inMin) * (len(colors) - 1)

    # Determine the lower index of the pair of color indices this
    # value corresponds and its fractional distance between the lower
    # and the upper colors.
    i, f = int(i_f // 1), i_f % 1  # Split into whole & fractional parts.

    # Does it fall exactly on one of the color points?
    if f < EPSILON:
        return colors[i]
    # ... if not, then return a color linearly interpolated in the 
    # range between it and the following one.
    else:
        (r1, g1, b1), (r2, g2, b2) = colors[i], colors[i+1]
        return int(r1 + f * (r2 - r1)), int(g1 + f * (g2 - g1)), int(b1 + f * (b2 - b1))


def reset_LED(LED):
    """Reset and clear LED

    Args:
        LED:
            SenseHat instance
    """
    LED.clear()
    LED.low_light = False


def update_LED(LED, rotation, data, inMin, inMax):
    """
    Update all pixels on SenseHat 8x8 LED with new color values

    Args:
        LED:
            SenseHat instance
        rotation:
            'int' with 0, 90, 180, or 270
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
    LED.set_rotation(rotation)
    LED.set_pixels(pixels)
 

def blank_LED(LED):
    """Show blank LED

    Args:
        LED:
            SenseHat instance
    """
    LED.clear()
    

def sparkle_LED(LED):
    """Show random sparkles on LED

    Args:
        LED:
            SenseHat instance
    """
    x = randint(0, 7)
    y = randint(0, 7)
    r = randint(0, 255)
    g = randint(0, 255)
    b = randint(0, 255)

    toggle = randint(0, 3)

    if toggle != 0:
        LED.set_pixel(x, y, r, g, b)
    else:    
        LED.clear()


def read_sensor_data(sensors):
    """
    Read sensor data round values to 1 decimal place

    Args:
        sensors:
            SenseHat instance

    Returns:
        'tuple' with 1 data point from each of the SenseHat sensors
    """
    tempC = round(sensors.get_temperature(), 1)     # Temperature in C
    press = round(sensors.get_pressure(), 1)        # Presure in hPa
    humid = round(sensors.get_humidity(), 1)        # Humidity 

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


def get_feed_info(ioClient, feed):
    """Get Adafruit IO feed info

    Args:
        ioClient:
            Adafruit IO client instance
        feed:
            'str' with feed (key) name    
    """
    global logger
    try:
        info = ioClient.feeds(feed)

    except RequestError as e:
        logger.error(f"Failed to get feed info - ADAFRUIT REQUEST ERROR: {e}")
        raise
    
    return info


async def _send_sensor_data(ioClient, data):
    """
    Send sensor data to Adafruit IO

    Args:
        ioClient:
            Adafruit IO client instance
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
        ioClient.send_data(data["feed"].key, data["data"])
    except RequestError as e:
        logger.error(f"Upload failed for {data['feed'].key} - REQUEST ERROR: {e}")
        raise RequestError
    except ThrottlingError as e:
        logger.error(f"Upload failed for {data['feed'].key} - THROTTLING ERROR: {e}")
        raise ThrottlingError


async def send_all_sensor_data(ioClient, tempsData, pressData, humidData):
    """
    Send sensor data to Adafruit IO

    Args:
        ioClient:
            Adafruit IO client instance
        tempsData:
            'dict' with 'temperature feed' key and temperature data point
        pressData:
            'dict' with 'pressure feed' key and pressure data point
        humidData:
            'dict' with 'humidity feed' key and humidity data point

    Raises:
        RequestError:
            When API request fails
        ThrottlingError:
            When exceeding Adafruit IO rate limit
    """
    await asyncio.gather(
        _send_sensor_data(ioClient, tempsData),
        _send_sensor_data(ioClient, pressData),
        _send_sensor_data(ioClient, humidData)
    )


# =========================================================
#      M A I N   F U N C T I O N    /   A C T I O N S
# =========================================================
if __name__ == '__main__':
    # Initialize TOML parser
    appDir = Path(__file__).parent
    with open(appDir.joinpath("settings.toml"), mode="rb") as fp:
        config = tomli.load(fp)

    # Get core settings
    ioUser = get_setting(config, const.KWD_AIO_USER, "")
    ioKey = get_setting(config, const.KWD_AIO_KEY, "")
    ioDelay = get_setting(config, const.KWD_DELAY, const.DEF_DELAY)
    ioWait = get_setting(config, const.KWD_WAIT, const.DEF_WAIT)
    ioThrottle = get_setting(config, const.KWD_THROTTLE, const.DEF_THROTTLE)
    
    displRotation = get_setting(config, const.KWD_ROTATION, const.DEF_ROTATION)
    displMode = get_setting(config, const.KWD_DISPLAY, const.DISPL_SPARKLE)

    # Initialize logger
    logFile = get_setting(config, const.KWD_LOG_FILE)
    logFileFP = appDir.parent.joinpath(logFile) if logFile else None

    logger = init_logger(
        get_setting(config, const.KWD_LOG_LEVEL, const.LOG_INFO),
        logFileFP
    )

    # Initialize core data queues
    tempsQ = deque(EMPTY_Q, maxlen=const.LED_MAX_COL) # Temperature queue
    pressQ = deque(EMPTY_Q, maxlen=const.LED_MAX_COL) # Pressure queue
    humidQ = deque(EMPTY_Q, maxlen=const.LED_MAX_COL) # Humidity queue

    # Initialize SenseHat
    sense = SenseHat()
    sense.clear()                               # Clear 8x8 LED
    sense.low_light = True
    sense.set_rotation(displRotation)           # Set initial rotation
    sense.set_imu_config(False, False, False)   # Disable IMU functions

    sense.stick.direction_up = pushed_up
    sense.stick.direction_down = pushed_down
    sense.stick.direction_left = pushed_left
    sense.stick.direction_right = pushed_right
    sense.stick.direction_middle = pushed_middle

    # Initialize Adafruit IO clients
    aio = Client(ioUser, ioKey)
    mqtt = MQTTClient(ioUser, ioKey)

    try:
        tempsFeed = get_feed_info(aio, get_setting(config, const.KWD_FEED_TEMPS, ""))
        pressFeed = get_feed_info(aio, get_setting(config, const.KWD_FEED_PRESS, ""))
        humidFeed = get_feed_info(aio, get_setting(config, const.KWD_FEED_HUMID, ""))
    except RequestError as e:
        logger.error(f"Application terminated due to REQUEST ERROR: {e}")
        reset_LED(sense)
        sys.exit(1)

    # Ensure that we upload first reading
    delayCounter = maxDelay = ioDelay

    # -- Main application loop --
    try:
        logger.info("-- START Data Logging --")

        while True:
            tempC, press, humid = read_sensor_data(sense)

            tempsQ.append(tempC)
            pressQ.append(press)
            humidQ.append(humid)

            if displMode == const.DISPL_TEMP:
                update_LED(sense, displRotation, tempsQ, const.MIN_TEMP, const.MAX_TEMP)
            elif displMode == const.DISPL_PRESS:    
                update_LED(sense, displRotation, pressQ, const.MIN_PRESS, const.MAX_PRESS)
            elif displMode == const.DISPL_HUMID:    
                update_LED(sense, displRotation, humidQ, const.MIN_HUMID, const.MAX_HUMID)
            elif displMode == const.DISPL_SPARKLE:    
                sparkle_LED(sense)
            else:    
                blank_LED(sense)

            # We only want to send data at certain intervals ...
            if delayCounter < maxDelay:
                delayCounter += 1
            else:
                try:
                    asyncio.run(send_all_sensor_data(
                        aio,
                        {"data": tempC, "feed": tempsFeed},
                        {"data": press, "feed": pressFeed},
                        {"data": humid, "feed": humidFeed},
                    ))

                except RequestError as e:
                    logger.error(f"Application terminated due to REQUEST ERROR: {e}")
                    raise

                except ThrottlingError as e:
                    # Keep increasing 'maxDelay' each time we get a 'ThrottlingError'
                    maxDelay += ioThrottle
                    
                else:
                    # Reset 'maxDelay' back to normal 'ioDelay' on successful upload
                    maxDelay = ioDelay
                    logger.info(f"Uploaded: TEMP: {tempC} - PRESS: {press} - HUMID: {humid}")

                finally:
                    # Reset counter even on failure
                    delayCounter = 1

            # ... but we check the sensors every second
            time.sleep(ioWait)

    except KeyboardInterrupt:
        logger.info("Application terminated by user.")

    finally:
        reset_LED(sense)
        logger.info("-- END Data Logging --")
