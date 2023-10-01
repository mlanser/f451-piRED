"""Global constants for f451 Labs piRED application.

This module holds all global constants used within the components of 
the f451 Labs piRED application. Some of the constants are used as 
keyword equivalents for attributes listed in the `settings.toml` file.
"""
# =========================================================
#              M I S C .   C O N S T A N T S
# =========================================================
DELIM_STD = "|"
DELIM_VAL = ":"
EMPTY_STR = ""

RGB_BLACK = (0, 0, 0)   # RGB values for black (pixel off)
RGB_BLUE = (0, 0, 255)
RGB_GREEN = (0, 255, 0)
RGB_YELLOW = (255, 255, 0)
RGB_RED = (255, 0, 0)

ROTATE_90 = 90          # Rotate 90 degrees    

DISPL_BLANK = 0         # Display `blank` screen
DISPL_TEMP = 1          # Show temperature data
DISPL_PRESS = 2         # Show barometric pressure data
DISPL_HUMID = 3         # Show humidity data
DISPL_SPARKLE = 4       # Show random sparkles

# -- SenseHat --
MIN_TEMP = 0.0          # Min/max sense degrees in C
MAX_TEMP = 65.0
MIN_PRESS = 260.0       # Min/max sense pressure in hPa
MAX_PRESS = 1260.0
MIN_HUMID = 0.0         # Min/max sense humidity in %
MAX_HUMID = 100.0

LED_MAX_COL = 8         # sense has an 8x8 LED display
LED_MAX_ROW = 8

DEF_DELAY = 59          # Default delay between uploads
DEF_WAIT = 1            # Default delay between sensor reads
DEF_ROTATION = 0


# =========================================================
#    K E Y W O R D S   F O R   C O N F I G   F I L E S
# =========================================================
SENSOR_ALL: str = "all"
SENSOR_MAIN: str = "f451_main"
SENSOR_TEMP: str = "f451_temperature"
SENSOR_HUMID: str = "f451_humidity"
SENSOR_WIND: str = "f451_wind"
SENSOR_RAIN: str = "f451_rain"
SENSOR_SPEED: str = "f451_speed"

KWD_AIO_USER: str = "AIO_USERNAME"
KWD_AIO_KEY: str = "AIO_KEY"
KWD_DELAY: str = "DELAY"
KWD_WAIT: str = "WAIT"
KWD_ROTATION: str = "ROTATION"
KWD_DISPLAY: str = "DISPLAY"
KWD_LOG_LEVEL: str = "LOGLVL"
KWD_LOG_FILE: str = "LOGFILE"
KWD_FEED_TEMPS: str = "FEED_TEMPS"
KWD_FEED_PRESS: str = "FEED_PRESS"
KWD_FEED_HUMID: str = "FEED_HUMID"

LOG_CRITICAL: str = "CRITICAL"
LOG_DEBUG: str = "DEBUG"
LOG_ERROR: str = "ERROR"
LOG_INFO: str = "INFO"
LOG_NOTSET: str = "NOTSET"
LOG_OFF: str = "OFF"
LOG_WARNING: str = "WARNING"

LOG_LVL_OFF: int = -1
LOG_LVL_MIN: int = -1
LOG_LVL_MAX: int = 100

STATUS_SUCCESS: str = "success"
STATUS_FAILURE: str = "failure"
