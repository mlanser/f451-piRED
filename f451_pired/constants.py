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

RGB_BLACK = (0, 0, 0)
RGB_WHITE = (255, 255, 255)
RGB_BLUE = (0, 0, 255)
RGB_CYAN = (0, 255, 255)
RGB_GREEN = (0, 255, 0)
RGB_YELLOW = (255, 255, 0)
RGB_RED = (255, 0, 0)

RGB_PROGRESS = (127, 0, 255) # Use for progressbar at bottom of LED

ROTATE_90 = 90              # Rotate 90 degrees    

MAX_LEN_CPU_TEMPS = 5       # Max number of CPU temps

DEF_UPLOADS = -1            # Number of uploads. If -1, then no limit.
DEF_FREQ = 600              # Default delay between uploads in seconds
DEF_DELAY = 300             # Default delay before first upload in seconds
DEF_WAIT = 1                # Default delay between sensor reads
DEF_THROTTLE = 120          # Default additional delay on 'ThrottlingError'
DEF_ROUNDING = 2            # Default 'rounding' precision for uploaded data

DEF_ID_PREFIX = "raspi-"    # Default prefix for ID string

# Tuning factor for compensation. Decrease this number to adjust the
# temperature down, and increase to adjust up
DEF_TEMP_COMP_FACTOR = 2.25

LOG_NOTSET = 0
LOG_DEBUG = 10
LOG_INFO = 20
LOG_WARNING = 30
LOG_ERROR = 40
LOG_CRITICAL = 50

STATUS_YES = "yes"
STATUS_NO = "no"
STATUS_UNKNOWN = "unknown"


# =========================================================
#    K E Y W O R D S   F O R   C O N F I G   F I L E S
# =========================================================
KWD_TEMP_COMP = "TEMP_COMP"
KWD_MAX_LEN_CPU_TEMPS = "CPU_TEMPS"

KWD_FREQ = "FREQ"
KWD_DELAY = "DELAY"
KWD_WAIT = "WAIT"
KWD_THROTTLE = "THROTTLE"
KWD_ROUNDING = "ROUNDING"
KWD_UPLOADS = "UPLOADS"
KWD_FEED_TEMPS = "FEED_TEMPS"
KWD_FEED_PRESS = "FEED_PRESS"
KWD_FEED_HUMID = "FEED_HUMID"

KWD_DATA_TEMPS = "temperature"
KWD_DATA_PRESS = "pressure"
KWD_DATA_HUMID = "humidity"


# =========================================================
#   C O N S T A N T S   F O R   D I S P L A Y   M O D E S
# =========================================================
IDX_SPARKLE = 0         # Display sparkles
IDX_TEMP  = 1
IDX_PRESS = 2
IDX_HUMID = 3

MIN_DISPL = IDX_SPARKLE # Cannot be smaller than smallest IDX_xx value     
MAX_DISPL = IDX_HUMID   # Cannot be larger than largest IDX_xx value 


# //////////////////////////////\\\\\\\\\\\\\\\\\\\\\\\\\\\
# -- SenseHat --
MIN_TEMP = 0.0          # Min/max sense degrees in C
MAX_TEMP = 65.0
MIN_PRESS = 260.0       # Min/max sense pressure in hPa
MAX_PRESS = 1260.0
MIN_HUMID = 0.0         # Min/max sense humidity in %
MAX_HUMID = 100.0

LED_MAX_COL = 8         # sense has an 8x8 LED display
LED_MAX_ROW = 8

# DEF_DELAY = 59          # Default delay between uploads
# DEF_WAIT = 1            # Default delay between sensor reads
# DEF_THROTTLE = 120      # Default additional delay on 'ThrottlingError'
# DEF_ROTATION = 0
# DEF_SLEEP = 600

# LOG_CRITICAL = "CRITICAL"
# LOG_DEBUG = "DEBUG"
# LOG_ERROR = "ERROR"
# LOG_INFO = "INFO"
# LOG_NOTSET = "NOTSET"
# LOG_OFF = "OFF"
# LOG_WARNING = "WARNING"

# LOG_LVL_OFF = -1
# LOG_LVL_MIN = -1
# LOG_LVL_MAX = 100

# STATUS_SUCCESS = "success"
# STATUS_FAILURE = "failure"

# STATUS_ON = "on"
# STATUS_OFF = "off"
# STATUS_TRUE = "true"
# STATUS_FALSE = "false"
# STATUS_YES = "yes"
# STATUS_NO = "no"

# =========================================================
#    K E Y W O R D S   F O R   C O N F I G   F I L E S
# =========================================================
# KWD_AIO_USER = "AIO_USERNAME"
# KWD_AIO_KEY = "AIO_KEY"
# KWD_DELAY = "DELAY"
# KWD_WAIT = "WAIT"
# KWD_THROTTLE = "THROTTLE"
# KWD_ROTATION = "ROTATION"
# KWD_DISPLAY = "DISPLAY"
# KWD_PROGRESS = "PROGRESS"
# KWD_SLEEP = "SLEEP"
# KWD_LOG_LEVEL = "LOGLVL"
# KWD_LOG_FILE = "LOGFILE"
# KWD_FEED_TEMPS = "FEED_TEMPS"
# KWD_FEED_PRESS = "FEED_PRESS"
# KWD_FEED_HUMID = "FEED_HUMID"


