"""Custom class for handling f451 Labs SenseMon UI.

This class defines and manages the layout and display of 
data in the terminal. This is, however, not a complete TUI
as the SenseMon application only collects and displays data

We're using a few libraries to make this all look pretty:

Dependencies:
    - rich - handles UI layout, etc.
    - sparklines - display real-time-ish data as sparklines
    - termcolor - adds colors to sparklines 
"""

import time
import random

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from rich.rule import Rule
from rich.status import Status
from rich.table import Table

from sparklines import sparklines

import f451_common.common as f451Common
import f451_sensehat.sensehat_data as f451SenseData


# =========================================================
#              M I S C .   C O N S T A N T S
# =========================================================
APP_1COL_MIN_WIDTH = 40                 # Min width (in chars) for 1col terminal layout
APP_2COL_MIN_WIDTH = 80                 # Min width (in chars) for 2col terminal layout
APP_MIN_CLI_HEIGHT = 10                 # Min terminal window height (in rows)

STATUS_OK = 200

STATUS_LBL_NEXT = "Next:  "
STATUS_LBL_LAST = "Last:  "
STATUS_LBL_TOT_UPLD = "Total: "
STATUS_LBL_WAIT = "Waiting ..."
STATUS_LBL_INIT = "Initializing ..."
STATUS_LBL_UPLD = "Uploading ..."

HDR_STATUS = "Uploads"
VAL_BLANK_STR = "--"                    # Use for 'blank' value

COLOR_DEF = "grey"                      # Default color
COLOR_OK = "green"
COLOR_ERROR = "bold red"

CHAR_DIR_UP = '↑'                       # UP arrow to indicate increase
CHAR_DIR_EQ = '↔︎'                       # SIDEWAYS arrow to little/no change
CHAR_DIR_DWN = '↓'                      # DOWN arrow to indicate decline
CHAR_DIR_DEF = ' '                      # 'blank' to indicate unknown change

DELTA_FACTOR = 0.02                     # Any change with X% is considered negligable

# =========================================================
#    H E L P E R   C L A S S E S   &   F U N C T I O N S
# =========================================================
class Logo:
    """Renders fancy logo."""
    def __init__(self, width, namePlain, nameRender, verNum):
        self._render = f451Common.make_logo(width, nameRender, f"v{verNum}")
        self._plain = f"{namePlain} - v{verNum}"

    @property
    def rows(self):
        return max(self._render.count("\n"), 1) if self._render else 1

    @property    
    def plain(self):
        return self._plain

    def __rich__(self):
        return Text(self._render, end="")

    def __str__(self):
        return self._plain
    
    def __repr__(self):
        return f"{type(self.__name__)}(plain={self._plain!r})"


def render_footer(appName, conWidth):
    footer = Text()

    # Assemble colorful legend
    footer.append("  LOW ", f451SenseData.COLOR_MAP[f451SenseData.COLOR_LOW])
    footer.append("NORMAL ", f451SenseData.COLOR_MAP[f451SenseData.COLOR_NORM])
    footer.append("HIGH", f451SenseData.COLOR_MAP[f451SenseData.COLOR_HIGH])

    # Add app name and version and push to the right
    footer.append(appName.rjust(conWidth - len(str(footer)) - 2))
    footer.end = ""

    return footer


def render_table(data=[], labelsOnly=False):
    """Make a new table
    
    This is a beefy function and (re-)renders the whole table
    on each update so that we get that real-time update feel.

    Args:
        data: 
            'list' of data rows, each with a specific data set render
        labelsOnly:
            'bool' if 'True' that we only render labels and no data
    """

    def _prep_currval_str(val, unit, color, valPrev = None, labelsOnly = False):
        """Prep string for displaying current/last data point

        This is a formatted string with a data value and unit of 
        measure. The largest value will be 4 digits + 2 decimals. 
        We also want values to be right-justfied and align on the 
        decimal point.
        
        -->|        |<--
           |12345678|
        ---|--------|---
           |1,234.56|      <- Need min 8 char width for data values
           |    1.23|
        """
        text = Text()
        dirChar = CHAR_DIR_DEF

        if labelsOnly or val is None:
            text.append(f"{VAL_BLANK_STR} {unit}", COLOR_DEF)
        else:
            if valPrev is not None:
                if val > (valPrev * (1 + DELTA_FACTOR)):
                    dirChar = CHAR_DIR_UP
                elif val < (valPrev * (1 - DELTA_FACTOR)):
                    dirChar = CHAR_DIR_DWN
                else:
                    dirChar = CHAR_DIR_EQ

            text.append(f"{dirChar} {val:>8,.2f} {unit}", color)

        return text

    def _prep_sparkline_str(vals, colors, labelsOnly):
        """Prep sparkline graph string"""
        return "" if (labelsOnly or not vals) else sparklines(vals, num_lines = 1, minimum = 0, maximum = 8)[-1]

    # Build a table
    table = Table(show_header = True, show_footer = False, show_edge = True, show_lines = True, expand = True, box = box.SQUARE_DOUBLE_HEAD)
    table.add_column(Text("Description", justify = "center"), ratio = 1, width = 12, no_wrap = True, overflow = '')
    table.add_column(Text("Current", justify = "center"), ratio = 1, width = 16, no_wrap = True, overflow = '')
    table.add_column(Text("History", justify = "center"), ratio = 4, min_width = 12, no_wrap = True, overflow = '')

    # Render rows with/without data
    if data:
        for row in data:
            table.add_row(
                row["label"], 
                _prep_currval_str(row['dataPt'], row['unit'], row['dataPtColor'], row['dataPtPrev'], labelsOnly),
                _prep_sparkline_str(row['sparkData'][-40:], row['sparkColors'], labelsOnly)
            )
    else:
        table.add_row('', '', '')
        table.add_row('', '', '')
        table.add_row('', '', '')

    return table


# =========================================================
#                     M A I N   C L A S S
# =========================================================
class SenseMonUI:
    def __init__(self):
        self._console = None
        self._layout = None
        self._conWidth = 0
        self._conHeight = 0
        self._active = False
        self.logo = None
        self.show24h = False        # Show 24-hour time?
        self.showLocal = True       # Show local time?
        self.statusHdr = HDR_STATUS
        self.statusLblNext = STATUS_LBL_NEXT
        self.statusLblLast = STATUS_LBL_LAST
        self.statusLblTotUpld = STATUS_LBL_TOT_UPLD
        self.statusLblAction = STATUS_LBL_WAIT

    @property
    def is_dual_col(self):
        return (self._conWidth >= APP_2COL_MIN_WIDTH)

    @property
    def is_active(self):
        return self._active

    @property
    def console(self):
        """Provide hook to Rich 'console'"""
        return self._console if self._active else None

    @property
    def layout(self):
        """Provide hook to Rich 'layout'"""
        return self._layout if self._active else None

    def _make_time_str(self, t):
        timeFmtStr = "%H:%M:%S" if self.show24h else "%I:%M:%S %p"
        return time.strftime(
                timeFmtStr, 
                time.localtime(t) if self.showLocal else time.gmtime(t)
            )
    
    @staticmethod
    def init_progressbar(refreshRate=2):
        """Initialize new progress bar."""
        return Progress(                     
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            transient=True,
            refresh_per_second=refreshRate
        )

    def initialize(self, appNameLong, appNameShort, appVer, dataRows, enable=True):
        console = Console()
        layout = Layout()

        conWidth, conHeight = console.size
        logo = Logo(
            int(conWidth * 2 / 3) if (conWidth >= APP_2COL_MIN_WIDTH) else conWidth,
            appNameLong, 
            appNameShort, 
            appVer
        )

        # Is the terminal window big enough to hold the layout? Or does 
        # user not want UI? If not, then we're done.
        if not enable or conWidth < APP_1COL_MIN_WIDTH or conHeight < APP_MIN_CLI_HEIGHT:
            return
        
        # If terminal window is wide enough, then split header 
        # row and show fancy logo ...
        if (conWidth >= APP_2COL_MIN_WIDTH):
            layout.split(
                Layout(name="header", size = logo.rows + 1),
                Layout(name="main", size = 9),
                Layout(name="footer"),
            )
            layout["header"].split_row(
                Layout(name="logo", ratio = 2), 
                Layout(name="action")
            )
        # ... else stack all panels without fancy logo       
        else:
            layout.split(
                Layout(name="logo", size = logo.rows + 1, visible = (logo.rows > 1)), 
                Layout(name="action", size = 5),
                Layout(name="main", size = 9),
                Layout(name="footer"),
            )

        layout["action"].split(
            Layout(name="actHdr", size = 1),
            Layout(name="actNextUpld", size = 1),
            Layout(name="actLastUpld", size = 1),
            Layout(name="actNumUpld", size = 1),
            Layout(name="actCurrent", size = 1),
        )

        # Display fancy logo
        if logo.rows > 1:
            layout["logo"].update(logo)

        layout["actHdr"].update(Rule(title=self.statusHdr, style = COLOR_DEF, end = ''))
        layout["actNextUpld"].update(Text(f"{self.statusLblNext}--:--:--"))
        layout["actLastUpld"].update(Text(f"{self.statusLblLast}--:--:--"))
        layout["actNumUpld"].update(Text(f"{self.statusLblTotUpld}-"))
        layout["actCurrent"].update(Status(STATUS_LBL_INIT))

        # Display main row
        layout["main"].update(render_table(dataRows, True))

        # Display footer row
        layout["footer"].update(render_footer(logo.plain, conWidth))

        # Updating properties for this object ... and then we're done
        self._console = console
        self._layout = layout
        self._conWidth = conWidth
        self._conHeight = conHeight
        self._active = True
        self.logo = logo

    def update_data(self, data):
        if self._active:
            self._layout["main"].update(render_table(data))

    def update_upload_num(self, num):
        if self._active:
            self._layout["actNumUpld"].update(
                Text(f"{self.statusLblTotUpld}{num}", COLOR_DEF)
            )

    def update_upload_next(self, nextTime):
        if self._active:
            self._layout["actNextUpld"].update(
                Text(f"{self.statusLblNext}{self._make_time_str(nextTime)}", COLOR_DEF)
            )

    def update_upload_last(self, lastTime, lastStatus=STATUS_OK):
        if self._active:
            text = Text()
            text.append(f"{self.statusLblLast}{self._make_time_str(lastTime)} ", style = COLOR_DEF)

            if lastStatus == STATUS_OK:
                text.append("[OK]", COLOR_OK)
            else:
                text.append("[Error]", COLOR_ERROR)
            
            self._layout["actLastUpld"].update(text)

    def update_upload_status(self, lastTime, lastStatus, nextTime, numUploads):
        if self._active:
            self.update_upload_next(nextTime)
            self.update_upload_last(lastTime, lastStatus)
            self.update_upload_num(numUploads)

    def update_action(self, actMsg=None):
        if self._active:
            msgStr = actMsg if actMsg else self.statusLblAction
            self._layout["actCurrent"].update(Status(msgStr))

    def update_progress(self, progress=None):
        if self._active and progress is not None:
            self._layout["actCurrent"].update(progress)
