#!/usr/bin/python
import time
import sys

from collections import deque

from random import randrange

from sense_hat import SenseHat
sense = SenseHat()
sense.clear()
# sense.set_rotation(90)
# sense.set_rotation(270)

# -- CONSTANTS --
#           - 0    1    2    3    4    5    6    7 -
_EMPTY_Q_ = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
_EPSILON_ = sys.float_info.epsilon                                  # Smallest possible difference.

_COLORS_  = [(0, 0, 255), (0, 255, 0), (255, 255, 0), (255, 0, 0)]  # [BLUE, GREEN, YELLOW, RED]
_RGB_BLACK_ = (0, 0, 0)                                             # RGB values for black (pixel off)

_MIN_TEMP_ = 0.0        # Min/max SenseHat degrees in C
_MAX_TEMP_ = 65.0
_MIN_PRESS_ = 260.0     # Min/max SenseHat pressure in hPa
_MAX_PRESS_ = 1260.0
_MIN_HUMID_ = 0.0       # Min/max SenseHat humidity in %
_MAX_HUMID_ = 100.0

_MAX_PIXEL_ = 8         # SenseHat has 8x8 LED display
_MAX_DATA_ = 8

# -- GLOBALS --
tempsQ = deque(_EMPTY_Q_, maxlen=_MAX_DATA_)     # Temperature queue
pressQ = deque(_EMPTY_Q_, maxlen=_MAX_DATA_)     # Pressure queue
humidQ = deque(_EMPTY_Q_, maxlen=_MAX_DATA_)     # Humidity queue

# Map value to range
# 
# We use this function to map values (e.g. temp, etc.) against the Y-axis of 
# the SenseHat 8x8 LED display. This means that all values must be mapped 
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


# Update SenseHat 8x8 LED
#
# Update all pixels on SenseHat with new color values
def update_LED(data, inMin, inMax):
    pixels = []
    tstData = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    for i in range(_MAX_DATA_):
        val = round(num_to_range(data[i], inMin, inMax, 0, _MAX_PIXEL_))
        # val = tstData[i]
        # val = 3.0
        
        for j in range(_MAX_PIXEL_):
            pixels.append(_RGB_BLACK_ if j < (_MAX_PIXEL_ - val) else convert_to_rgb(inMin, inMax, data[i], _COLORS_))

    sense.set_pixels(pixels)
    # print(f"{pixels}")


# Read sensor data
def read_sensors():
    # Read all 3 sensors and round the values 
    # to one decimal place
    # tempC = round(sense.get_temperature(), 1)     # Temperature in C
    # press = round(sense.get_pressure(), 1)        # Presure in hPa
    # humid = round(sense.get_humidity(), 1)        # Humidity 
    tempC = randrange(0, 650) / 10
    press = randrange(2600, 12600) / 10
    humid = randrange(0, 1000) / 10

    return tempC, press, humid 


# `main` loop
if __name__ == '__main__':
    try:
        while True:
            tempC, press, humid = read_sensors()

            tempsQ.append(tempC)
            pressQ.append(press)
            humidQ.append(humid)

            update_LED(tempsQ, _MIN_TEMP_, _MAX_TEMP_)
            # print(f"\nTemps:    {tempsQ} \n\n") 
            # print(f"Humidity: {humidQ}")  
            # print(f"Pressure: {pressQ}")

            time.sleep(1)

    except KeyboardInterrupt:
        pass

    sense.clear()
    