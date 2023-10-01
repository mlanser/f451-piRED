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
IO_USER = ""            # Adafruit IO username
IO_KEY = ""             # Adafruit IO key
IO_DELAY = 1            # Delay between uploads

ROTATION = 0
DISPLAY = const.DISPL_SPARKLE

EPSILON = sys.float_info.epsilon                      # Smallest possible difference.

#         - 0    1    2    3    4    5    6    7 -
EMPTY_Q = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
COLORS  = [const.RGB_BLUE, const.RGB_GREEN, const.RGB_YELLOW, const.RGB_RED]


# =========================================================
#              H E L P E R   F U N C T I O N S
# =========================================================
# SenseHat Joystick UP event
def pushed_up(event):
    global ROTATION

    if event.action != ACTION_RELEASED:
        ROTATION = 270 if ROTATION <= 0 else ROTATION - const.ROTATE_90 


# SenseHat Joystick DOWN event
def pushed_down(event):
    global ROTATION

    if event.action != ACTION_RELEASED:
        ROTATION = 0 if ROTATION >= 270 else ROTATION + const.ROTATE_90 


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
        DISPLAY = const.DISPL_BLANK


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
    if f < EPSILON:
        return colors[i]
    else: # Return a color linearly interpolated in the range between it and 
          # the following one.
        (r1, g1, b1), (r2, g2, b2) = colors[i], colors[i+1]
        return int(r1 + f*(r2-r1)), int(g1 + f*(g2-g1)), int(b1 + f*(b2-b1))


# Update sense 8x8 LED
#
# Update all pixels on sense with new color values
def update_LED(LED, rotation, data, inMin, inMax):
    normalized = [round(num_to_range(val, inMin, inMax, 0, const.LED_MAX_ROW)) for val in data]
    maxCol = min(const.LED_MAX_COL, len(normalized))

    pixels = [const.RGB_BLACK if row < (const.LED_MAX_ROW - normalized[col]) else convert_to_rgb(inMin, inMax, data[col], COLORS) for row in range(const.LED_MAX_ROW) for col in range(maxCol)]
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


# =========================================================
#      M A I N   F U N C T I O N    /   A C T I O N S
# =========================================================
# `main` loop
if __name__ == '__main__':
    # -- Initialize TOML parser --
    with open(Path(__file__).parent.joinpath("settings.toml"), mode="rb") as fp:
        config = tomli.load(fp)

    IO_USER = config["AIO_USERNAME"]
    IO_KEY = config["AIO_KEY"]
    IO_DELAY = config["DELAY"]
    ROTATION = config["ROTATION"]
    DISPLAY = config["DISPLAY"]

    # -- Initialize core variables --
    tempsQ = deque(EMPTY_Q, maxlen=const.LED_MAX_COL) # Temperature queue
    pressQ = deque(EMPTY_Q, maxlen=const.LED_MAX_COL) # Pressure queue
    humidQ = deque(EMPTY_Q, maxlen=const.LED_MAX_COL) # Humidity queue

    # -- Initialize Adafruit IO --
    aio = Client(IO_USER, IO_KEY)
    mqtt = MQTTClient(IO_USER, IO_KEY)

    tempsFeed = get_feed_info(aio, config["FEED_TEMPS"])
    pressFeed = get_feed_info(aio, config["FEED_PRESS"])
    humidFeed = get_feed_info(aio, config["FEED_HUMID"])

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

            if DISPLAY == const.DISPL_TEMP:
                update_LED(sense, ROTATION, tempsQ, const.MIN_TEMP, const.MAX_TEMP)
            elif DISPLAY == const.DISPL_PRESS:    
                update_LED(sense, ROTATION, pressQ, const.MIN_PRESS, const.MAX_PRESS)
            elif DISPLAY == const.DISPL_HUMID:    
                update_LED(sense, ROTATION, humidQ, const.MIN_HUMID, const.MAX_HUMID)
            elif DISPLAY == const.DISPL_SPARKLE:    
                sparkle_LED(sense)
            else:    
                blank_LED(sense)

            # We only want to send data at certain intervals ...
            if delayCounter < IO_DELAY:
                delayCounter += 1
            else:    
                send_sensor_data(
                    aio,
                    {"data": tempC, "feed": tempsFeed},
                    {"data": press, "feed": pressFeed},
                    {"data": humid, "feed": humidFeed},
                )
                delayCounter = 1    # Reset counter

            # ... but we check the sensors every second
            time.sleep(1)

    except KeyboardInterrupt:
        pass

    finally:
        sense.clear()
        sense.low_light = False
