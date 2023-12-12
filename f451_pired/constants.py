"""Global constants for f451 Labs piRED application.

This module holds all global constants used within the components of 
the f451 Labs piRED application. Some of the constants are used as 
keyword equivalents for attributes listed in the `settings.toml` file.
"""

# =========================================================
#              M I S C .   C O N S T A N T S
# =========================================================
DEF_FREQ = 600      # Default delay between uploads in seconds
DEF_DELAY = 300     # Default delay before first upload in seconds
DEF_WAIT = 1        # Default delay between sensor reads
DEF_THROTTLE = 120  # Default additional delay on 'ThrottlingError'
DEF_ROUNDING = 2    # Default 'rounding' precision for uploaded data

# =========================================================
#    K E Y W O R D S   F O R   C O N F I G   F I L E S
# =========================================================
KWD_FREQ = 'FREQ'
KWD_DELAY = 'DELAY'
KWD_WAIT = 'WAIT'
KWD_THROTTLE = 'THROTTLE'
KWD_ROUNDING = 'ROUNDING'

KWD_FEED_TEMPS = 'FEED_TEMPS'
KWD_FEED_PRESS = 'FEED_PRESS'
KWD_FEED_HUMID = 'FEED_HUMID'

KWD_DATA_TEMPS = 'temperature'
KWD_DATA_PRESS = 'pressure'
KWD_DATA_HUMID = 'humidity'


# =========================================================
#   C O N S T A N T S   F O R   D I S P L A Y   M O D E S
# =========================================================
IDX_SPARKLE = 0             # Display sparkles
IDX_TEMP = 1
IDX_PRESS = 2
IDX_HUMID = 3

MIN_DISPL = IDX_SPARKLE     # Cannot be smaller than smallest IDX_xx value
MAX_DISPL = IDX_HUMID       # Cannot be larger than largest IDX_xx value
