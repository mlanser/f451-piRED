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


def render_table(data=[]):
    """Make a new table."""
    table = Table(show_header = True, show_footer = False, show_edge = True, show_lines = True, expand = True, box = box.SQUARE_DOUBLE_HEAD)
    table.add_column("Description", max_width = 12)
    table.add_column("Current", max_width = 8)
    table.add_column("History", min_width = 20)

    if data:
        for row in data:
            table.add_row(
                row["label"], 
                f"{row['data'][-1]:3.2f} {row['unit']}", 
                sparklines(list(row['data'])[-20])[-1]
            )
        # table.add_row("Temperature", f"{random.random() * 100:3.2f}", sparklines([random.randint(1, 20) for _ in range(20)])[-1])
        # table.add_row("Humidity", f"{random.random() * 100:3.2f}", sparklines([random.randint(1, 20) for _ in range(20)])[-1])
        # table.add_row("Pressure", f"{random.random() * 100:3.2f}", sparklines([random.randint(1, 20) for _ in range(20)])[-1])
    else:
        table.add_row("Temperature", "", "")
        table.add_row("Humidity", "", "")
        table.add_row("Pressure", "", "")

    return table


def init_progressbar(refreshRate=2):
    """Initialize new progress bar."""
    return Progress(                     
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True,
        refresh_per_second=refreshRate
    )


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
        self.show24h = True         # Show 24-hour time
        self.showLocal = True       # Show local time
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
    
    def initialize(self, appNameLong, appNameShort, appVer, enable=True):
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
        # user not want UI?
        if not enable or conWidth < APP_1COL_MIN_WIDTH or conHeight < APP_MIN_CLI_HEIGHT:
            return              # We're done!
        
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

        layout["actHdr"].update(Rule(title=self.statusHdr, style = "grey", end = ''))
        layout["actNextUpld"].update(Text(f"{self.statusLblNext}--:--:--"))
        layout["actLastUpld"].update(Text(f"{self.statusLblLast}--:--:--"))
        layout["actNumUpld"].update(Text(f"{self.statusLblTotUpld}-"))
        layout["actCurrent"].update(Status(STATUS_LBL_INIT))

        # Display main row
        layout["main"].update(render_table())

        # Display footer row
        layout["footer"].update(Text(logo.plain, justify="right"))

        # Updating properties for this object ... and then we're done
        self._console = console
        self._layout = layout
        self._conWidth = conWidth
        self._conHeight = conHeight
        self._active = True
        self.logo = logo

    def update_data(self, data):
        self._layout["main"].update(render_table(data))

    def update_upload_next(self, nextTime):
        self._layout["actNextUpld"].update(
            Text(f"{self.statusLblNext}{self._make_time_str(nextTime)}", "grey")
        )

    def update_upload_last(self, lastTime, lastStatus=STATUS_OK):
        if lastStatus == STATUS_OK:
            color = "grey"
            statusMsg = "[OK]"
        else:
            color = "red"
            statusMsg = "[Error]"
        
        self._layout["actLastUpld"].update(
            Text(f"{self.statusLblNext}{self._make_time_str(lastTime)} {statusMsg}", color)
        )

    def update_upload_status(self, lastTime, lastStatus, nextTime):
        self.update_upload_next(nextTime)
        self.update_upload_last(lastTime, lastStatus)

    def update_action(self, actMsg=None, actType="status"):
        msgStr = actMsg if actMsg else self.statusLblAction
        if actType == "progress": 
            self._layout["actCurrent"].update(Status(msgStr))
        else:
            self._layout["actCurrent"].update(Status(msgStr))
