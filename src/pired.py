#!/usr/bin/python
import time
import sys

from collections import deque
from random import randrange, randint
from configparser import ConfigParser
from pathlib import Path

from sense_hat import SenseHat, ACTION_PRESSED, ACTION_HELD, ACTION_RELEASED
from Adafruit_IO import Client, MQTTClient, RequestError, ThrottlingError


# -- CONSTANTS --
#           - 0    1    2    3    4    5    6    7 -
_EMPTY_Q_ = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
_EPSILON_ = sys.float_info.epsilon                      # Smallest possible difference.

_RGB_BLACK_ = (0, 0, 0)                                 # RGB values for black (pixel off)
_RGB_BLUE_ = (0, 0, 255)
_RGB_GREEN_ = (0, 255, 0)
_RGB_YELLOW_ = (255, 255, 0)
_RGB_RED_ = (255, 0, 0)
_COLORS_  = [_RGB_BLUE_, _RGB_GREEN_, _RGB_YELLOW_, _RGB_RED_]

_MIN_TEMP_ = 0.0        # Min/max sense degrees in C
_MAX_TEMP_ = 65.0
_MIN_PRESS_ = 260.0     # Min/max sense pressure in hPa
_MAX_PRESS_ = 1260.0
_MIN_HUMID_ = 0.0       # Min/max sense humidity in %
_MAX_HUMID_ = 100.0

_MAX_COL_ = 8           # sense has an 8x8 LED display
_MAX_ROW_ = 8

_ROTATE_90_ = 90

_DISPL_BLANK_ = 0       # Display `blank` screen
_DISPL_TEMP_ = 1        # Show temperature data
_DISPL_PRESS_ = 2       # Show barometric pressure data
_DISPL_HUMID_ = 3       # Show humidity data
_DISPL_SPARKLE_ = 4     # Show random sparkles

# -- GLOBALS --
IO_USER = ""            # Adafruit IO username
IO_KEY = ""             # Adafruit IO key
IO_DELAY = 1            # Delay between uploads

ROTATION = 0
DISPLAY = _DISPL_SPARKLE_

# SenseHat Joystick UP event
def pushed_up(event):
    global ROTATION

    if event.action != ACTION_RELEASED:
        ROTATION = 270 if ROTATION <= 0 else ROTATION - _ROTATE_90_ 


# SenseHat Joystick DOWN event
def pushed_down(event):
    global ROTATION

    if event.action != ACTION_RELEASED:
        ROTATION = 0 if ROTATION >= 270 else ROTATION + _ROTATE_90_ 


# SenseHat Joystick LEFT event
def pushed_left(event):
    global DISPLAY

    if event.action != ACTION_RELEASED:
        DISPLAY = 4 if DISPLAY <= 1 else DISPLAY - 1


# SenseHat Joystick RIGHT event
def pushed_right(event):
    global DISPLAY

    if event.action != ACTION_RELEASED:
        DISPLAY = 1 if DISPLAY >= 4 else DISPLAY + 1


# SenseHat Joystick RIGHT event
def pushed_middle(event):
    global DISPLAY

    if event.action != ACTION_RELEASED:
        DISPLAY = _DISPL_BLANK_


# Map value to range
# 
# We use this function to map values (e.g. temp, etc.) against the Y-axis of 
# the sense 8x8 LED display. This means that all values must be mapped 
# against a range of 0-7.
#
# Based on code found here: https://www.30secondsofcode.org/python/s/num-to-range/
def num_to_range(num, inMin, inMax, outMin, outMax):
    return outMin + (float(num - inMin) / float(inMax - inMin) * (outMax - outMin))


# Map a value to RGB
#
# Based on reply found on StackOverflow by `martineau`: 
#
# See: https://stackoverflow.com/questions/20792445/calculate-rgb-value-for-a-range-of-values-to-create-heat-map
#
def convert_to_rgb(minval, maxval, val, colors):
    # `colors` is a series of RGB colors delineating a series of
    # adjacent linear color gradients between each pair.

    # Determine where the given value falls proportionality within
    # the range from minval->maxval and scale that fractional value
    # by the total number in the `colors` palette.
    i_f = float(val-minval) / float(maxval-minval) * (len(colors)-1)

    # Determine the lower index of the pair of color indices this
    # value corresponds and its fractional distance between the lower
    # and the upper colors.
    i, f = int(i_f // 1), i_f % 1  # Split into whole & fractional parts.

    # Does it fall exactly on one of the color points?
    if f < _EPSILON_:
        return colors[i]
    else: # Return a color linearly interpolated in the range between it and 
          # the following one.
        (r1, g1, b1), (r2, g2, b2) = colors[i], colors[i+1]
        return int(r1 + f*(r2-r1)), int(g1 + f*(g2-g1)), int(b1 + f*(b2-b1))


# Update sense 8x8 LED
#
# Update all pixels on sense with new color values
def update_LED(LED, rotation, data, inMin, inMax):
    normalized = [round(num_to_range(val, inMin, inMax, 0, _MAX_ROW_)) for val in data]
    maxCol = min(_MAX_COL_, len(normalized))

    pixels = [_RGB_BLACK_ if row < (_MAX_ROW_ - normalized[col]) else convert_to_rgb(inMin, inMax, data[col], _COLORS_) for row in range(_MAX_ROW_) for col in range(maxCol)]
    LED.set_rotation(rotation)
    LED.set_pixels(pixels)
 

# Show blank LED
def blank_LED(LED):
    LED.clear()
    

# Show random sparkles on LED
def sparkle_LED(LED):
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


# Get Adafruit IO feed info
def get_feed_info(io_client, feed):
    try:
        info = io_client.feeds(feed)
    except RequestError as e:
        print(f"ADAFRUIT REQUEST ERROR: {e} on '{feed}'")
        info = None
    
    return info


# Read sensor data
def read_sensor_data(sensors):
    # Read sensors and round values to 1 decimal place
    tempC = round(sensors.get_temperature(), 1)     # Temperature in C
    press = round(sensors.get_pressure(), 1)        # Presure in hPa
    humid = round(sensors.get_humidity(), 1)        # Humidity 

    return tempC, press, humid 


# Send sensor data to Adafruit IO
def send_sensor_data(io_client, tempsData, pressData, humidData):
    try:
        io_client.send_data(tempsData["feed"].key, tempsData["data"])
        io_client.send_data(pressData["feed"].key, pressData["data"])
        io_client.send_data(humidData["feed"].key, humidData["data"])

    except RequestError as e:
        print(f"ADAFRUIT REQUEST ERROR: {e}")
    
    except ThrottlingError as e:
        print(f"ADAFRUIT THROTTLING ERROR: {e}")


# `main` loop
if __name__ == '__main__':
    # -- Initialize ConfigParser --
    config = ConfigParser()

    # settingsPath = Path(__file__).parent.joinpath("settings.ini")
    config.read(Path(__file__).parent.joinpath("settings.ini"))

    IO_USER = config.get("adafruit_io", "io_username")
    IO_KEY = config.get("adafruit_io", "io_key")
    IO_DELAY = int(config.get("defaults", "delay"))
    ROTATION = int(config.get("defaults", "rotation"))
    DISPLAY = int(config.get("defaults", "display"))

    # -- Initialize core variables --
    tempsQ = deque(_EMPTY_Q_, maxlen=_MAX_COL_) # Temperature queue
    pressQ = deque(_EMPTY_Q_, maxlen=_MAX_COL_) # Pressure queue
    humidQ = deque(_EMPTY_Q_, maxlen=_MAX_COL_) # Humidity queue

    # -- Initialize Adafruit IO --
    aio = Client(IO_USER, IO_KEY)
    mqtt = MQTTClient(IO_USER, IO_KEY)

    tempsFeed = get_feed_info(aio, config.get("io_feeds", "temperature"))
    pressFeed = get_feed_info(aio, config.get("io_feeds", "pressure"))
    humidFeed = get_feed_info(aio, config.get("io_feeds", "humidity"))

    delayCounter = IO_DELAY                     # Ensure that we upload first reading

    # -- Initialize SenseHat --
    sense = SenseHat()
    sense.clear()                               # Clear 8x8 LED
    sense.low_light = True
    sense.set_rotation(ROTATION)                # Set initial rotation
    sense.set_imu_config(False, False, False)   # Disable IMU functions

    sense.stick.direction_up = pushed_up
    sense.stick.direction_down = pushed_down
    sense.stick.direction_left = pushed_left
    sense.stick.direction_right = pushed_right
    sense.stick.direction_middle = pushed_middle

    try:
        while True:
            tempC, press, humid = read_sensor_data(sense)

            tempsQ.append(tempC)
            pressQ.append(press)
            humidQ.append(humid)

            if DISPLAY == _DISPL_TEMP_:
                update_LED(sense, ROTATION, tempsQ, _MIN_TEMP_, _MAX_TEMP_)
            elif DISPLAY == _DISPL_PRESS_:    
                update_LED(sense, ROTATION, pressQ, _MIN_PRESS_, _MAX_PRESS_)
            elif DISPLAY == _DISPL_HUMID_:    
                update_LED(sense, ROTATION, humidQ, _MIN_HUMID_, _MAX_HUMID_)
            elif DISPLAY == _DISPL_SPARKLE_:    
                sparkle_LED(sense)
            else:    
                blank_LED(sense)

            if delayCounter < IO_DELAY:
                delayCounter += 1
            else:    
                send_sensor_data(
                    aio,
                    {"data": tempC, "feed": tempsFeed},
                    {"data": press, "feed": pressFeed},
                    {"data": humid, "feed": humidFeed},
                )
                delayCounter = 0

            time.sleep(1)

    except KeyboardInterrupt:
        pass

    finally:
        sense.clear()
        sense.low_light = False
