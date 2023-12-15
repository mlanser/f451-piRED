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

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from rich.rule import Rule
from rich.status import Status
from rich.table import Table

from sparklines import sparklines

import f451_common.common as f451Common
import f451_sensehat.sensehat_data as f451SenseData

# fmt: off
# =========================================================
#              M I S C .   C O N S T A N T S
# =========================================================
APP_1COL_MIN_WIDTH = 40     # Min width (in chars) for 1col terminal layout
APP_2COL_MIN_WIDTH = 80     # Min width (in chars) for 2col terminal layout
APP_MIN_CLI_HEIGHT = 10     # Min terminal window height (in rows)

STATUS_OK = 200

STATUS_LBL_NEXT = 'Next:  '
STATUS_LBL_LAST = 'Last:  '
STATUS_LBL_TOT_UPLD = 'Total: '
STATUS_LBL_WAIT = 'Waiting …'
STATUS_LBL_INIT = 'Initializing …'
STATUS_LBL_UPLD = 'Uploading …'

HDR_STATUS = 'Uploads'
VAL_BLANK_STR = '--'        # Use for 'blank' data
VAL_ERROR_STR = 'Error'     # Use for invalid data

COLOR_DEF = 'grey'          # Default color
COLOR_OK = 'green'
COLOR_ERROR = 'red'

CHAR_DIR_UP = '↑'           # UP arrow to indicate increase
CHAR_DIR_EQ = '↔︎'           # SIDEWAYS arrow to little/no change
CHAR_DIR_DWN = '↓'          # DOWN arrow to indicate decline
CHAR_DIR_DEF = ' '          # 'blank' to indicate unknown change

MAX_PROGBAR = 100           # Use 100% as max for progress bars
# fmt: o2


# =========================================================
#    H E L P E R   C L A S S E S   &   F U N C T I O N S
# =========================================================
class Logo:
    """Render fancy logo."""

    def __init__(self, width, namePlain, nameRender, verNum):
        self._render = f451Common.make_logo(width, nameRender, f"v{verNum}")
        self._plain = f"{namePlain} - v{verNum}"

    @property
    def rows(self):
        return max(self._render.count('\n'), 1) if self._render else 1

    @property
    def plain(self):
        return self._plain

    def __rich__(self):
        return Text(str(self._render), end='')

    def __str__(self):
        return self._plain

    def __repr__(self):
        return f"{type(self).__name__}(plain={self._plain!r})"


def render_table(data, labelsOnly=False):
    """Make a new table

    This is a beefy function and (re-)renders the whole table
    on each update so that we get that real-time update feel.

    Args:
        data:
            'list' of data rows, each with a specific data set render
        labelsOnly:
            'bool' if 'True' then we only render labels and no data

    Returns:
        'Table' with data
    """

    def _prep_currval_str(data, labelsOnly=False):
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

        NOTE: We display '--' if value is 'None' and status is 'ok' 
              as that represents a 'missing' value. But we display 
              'ERROR' if value is 'None' and status is not 'ok' as
              that indicates an invalid value. Both cases are shown
              as gaps in sparkline graph.   
        
        Args:
            data:
                'dict' with data point value and attributes
            labelsOnly:
                'bool' if 'True' then we do not generate 'current value' string

        Returns:
            'Text' object with formatted 'current value'
        """
        text = Text()
        dirChar = CHAR_DIR_DEF

        if labelsOnly or (data['dataPt'] is None and data['dataPtOK']):
            text.append(f"{dirChar} {VAL_BLANK_STR:>8} {data['unit']}", COLOR_DEF)
        elif data['dataPt'] is None and not data['dataPtOK']:
            text.append(f"{dirChar} {VAL_ERROR_STR:>8}", COLOR_ERROR)
        else:
            if data['dataPtDelta'] > 0:
                dirChar = CHAR_DIR_UP
            elif data['dataPtDelta'] < 0:
                dirChar = CHAR_DIR_DWN
            else:
                dirChar = CHAR_DIR_EQ

            text.append(
                f"{dirChar} {data['dataPt']:>8,.2f} {data['unit']}",
                data['dataPtColor']
            )

        return text

    def _prep_sparkline_str(data, labelsOnly):
        """Prep sparkline graph string

        NOTE: 'sparklines' library will return string with ANSI color 
              codes when used with 'termcolors' library.

        Args:
            data:
                'dict' with data point value and attributes
            labelsOnly:
                'bool' if 'True' then we do not generate 'current value' string

        Returns:
            'Text' object with formatted 'current value'
        """
        if labelsOnly or not data['sparkData']:
            return ''
        else:
            return Text.from_ansi(
                sparklines(
                    data['sparkData'], 
                    emph=data['sparkColors'], 
                    num_lines=1, 
                    minimum=data['sparkMinMax'][0],
                    maximum=data['sparkMinMax'][1]
                )[-1], 
                justify="center"
            )

    # Build a table
    table = Table(
        show_header=True,
        show_footer=False,
        show_edge=True,
        show_lines=True,
        expand=True,
        box=box.SQUARE_DOUBLE_HEAD,
    )
    table.add_column(
        Text('Description', justify='center'),
        ratio=1,
        width=12,
        no_wrap=True,
        overflow='crop',
    )
    table.add_column(
        Text('Current', justify='center'), 
        ratio=1, 
        width=16, 
        no_wrap=True, 
        overflow='crop'
    )
    table.add_column(
        Text('History', justify='center'),
        ratio=4,
        min_width=12,
        no_wrap=True,
        overflow='crop',
    )

    # Render rows with/without data
    if data:
        for row in data:
            table.add_row(
                row['label'],                           # 1st col: label
                _prep_currval_str(row, labelsOnly),     # 2nd col: current value
                _prep_sparkline_str(row, labelsOnly)    # 3rd col: sparkline
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
        self._console = Console()
        self._layout = Layout()
        self._conWidth = 0
        self._conHeight = 0
        self._active = False
        self._progBar = None
        self._progTaskID = None
        self.logo = None
        self.show24h = False    # Show 24-hour time?
        self.showLocal = True   # Show local time?
        self.statusHdr = HDR_STATUS
        self.statusLblNext = STATUS_LBL_NEXT
        self.statusLblLast = STATUS_LBL_LAST
        self.statusLblTotUpld = STATUS_LBL_TOT_UPLD

    @property
    def is_dual_col(self):
        return self._conWidth >= APP_2COL_MIN_WIDTH

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

    @property
    def statusbar(self):
         """Provide hook to Rich 'status'"""
         return self._layout['actCurrent'] if self._active else None

    def _make_time_str(self, t):
        timeFmtStr = '%H:%M:%S' if self.show24h else '%I:%M:%S %p'
        return time.strftime(timeFmtStr, time.localtime(t) if self.showLocal else time.gmtime(t))

    @staticmethod
    def _make_progressbar(console, refreshRate=2):
        """Initialize progress bar object"""
        return Progress(
            TextColumn('[progress.description]{task.description}'),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=True,
            refresh_per_second=refreshRate,
        )

    @staticmethod
    def _make_statusbar(console, msg=None):
        """Initialize 'status' bar object"""
        msg = msg if msg is not None else STATUS_LBL_WAIT
        return Status(msg, console=console, spinner='dots')

    def initialize(self, appNameLong, appNameShort, appVer, dataRows, enable=True):
        """Initialize main UI
        
        This method will create the base UI with all components (e.g. logo), 
        table, status fields, etc.). But there will not be any data.

        Also, the layout will depend on the width of the console. If the console
        is not wide enough, then the items will be stacked in a single column.

        Args:
            appNameLong: used for footer
            appNameShort: used for fancy logo
            appVer: app version displayed in fancy logo and footer
            dataRows: table rows with labels
            enable: 
        """
        def _footer(appName, conWidth):
            """Create 'footer' object"""
            footer = Text()

            # Assemble colorful legend
            footer.append('  LOW ', f451SenseData.COLOR_MAP[f451SenseData.COLOR_LOW])
            footer.append('NORMAL ', f451SenseData.COLOR_MAP[f451SenseData.COLOR_NORM])
            footer.append('HIGH', f451SenseData.COLOR_MAP[f451SenseData.COLOR_HIGH])

            # Add app name and version, and push to the right
            footer.append(appName.rjust(conWidth - len(str(footer)) - 2))
            footer.end = ''

            return footer

        # Get dimensions of screen/console 
        # console = Console()
        conWidth, conHeight = self._console.size

        # Is the terminal window big enough to hold the layout? Or does
        # user not want UI? If not, then we're done.
        if not enable or conWidth < APP_1COL_MIN_WIDTH or conHeight < APP_MIN_CLI_HEIGHT:
            return

        # Create fancy logo
        logo = Logo(
            int(conWidth * 2 / 3) if (conWidth >= APP_2COL_MIN_WIDTH) else conWidth,
            appNameLong,
            appNameShort,
            appVer,
        )

        # If terminal window is wide enough, then split 
        # header row and show fancy logo ...
        if conWidth >= APP_2COL_MIN_WIDTH:
            self._layout.split(
                Layout(name='header', size=logo.rows + 1),
                Layout(name='main', size=9),
                Layout(name='footer'),
            )
            self._layout['header'].split_row(
                Layout(name='logo', ratio=2), 
                Layout(name='action')
            )
        # ... else stack all panels without fancy logo
        else:
            self._layout.split(
                Layout(name='logo', size=logo.rows + 1, visible=(logo.rows > 1)),
                Layout(name='action', size=5),
                Layout(name='main', size=9),
                Layout(name='footer'),
            )

        self._layout['action'].split(
            Layout(name='actHdr', size=1),
            Layout(name='actNextUpld', size=1),
            Layout(name='actLastUpld', size=1),
            Layout(name='actNumUpld', size=1),
            Layout(name='actCurrent', size=1),
        )

        # Display fancy logo
        if logo.rows > 1:
            self._layout['logo'].update(logo)

        self._layout['actHdr'].update(Rule(title=self.statusHdr, style=COLOR_DEF, end=''))
        self._layout['actNextUpld'].update(Text(f'{self.statusLblNext}--:--:--'))
        self._layout['actLastUpld'].update(Text(f'{self.statusLblLast}--:--:--'))
        self._layout['actNumUpld'].update(Text(f'{self.statusLblTotUpld}-'))
        self._layout['actCurrent'].update(SenseMonUI._make_statusbar(self._console))

        # Display main row with data table
        self._layout['main'].update(render_table(dataRows, True))

        # Display footer row
        self._layout['footer'].update(_footer(logo.plain, conWidth))

        # Update properties for this object ... and then we're done
        self._conWidth = conWidth
        self._conHeight = conHeight
        self._active = True
        self.logo = logo

    def update_data(self, data):
        if self._active:
            self._layout['main'].update(render_table(data))

    def update_upload_num(self, num, maxNum=0):
        if self._active:
            maxNumStr = f"/{maxNum}" if maxNum > 0 else ''
            self._layout['actNumUpld'].update(Text(
                f"{self.statusLblTotUpld}{num}{maxNumStr}",
                style=COLOR_DEF
            ))

    def update_upload_next(self, nextTime):
        if self._active:
            self._layout['actNextUpld'].update(Text(
                f"{self.statusLblNext}{self._make_time_str(nextTime)}",
                style=COLOR_DEF
            ))

    def update_upload_last(self, lastTime, lastStatus=STATUS_OK):
        if self._active:
            text = Text()
            text.append(
                f"{self.statusLblLast}{self._make_time_str(lastTime)} ",
                style=COLOR_DEF
            )

            if lastStatus == STATUS_OK:
                text.append('[OK]', style=COLOR_OK)
            else:
                text.append('[Error]', style=COLOR_ERROR)

            self._layout['actLastUpld'].update(text)

    def update_upload_status(self, lastTime, lastStatus, nextTime, numUploads, maxUploads=0):
        if self._active:
            self.update_upload_next(nextTime)
            self.update_upload_last(lastTime, lastStatus)
            self.update_upload_num(numUploads, maxUploads)

    def update_action(self, actMsg=None):
        if self._active:
            msgStr = STATUS_LBL_WAIT if actMsg is None else actMsg
            self._layout['actCurrent'].update(self._make_statusbar(self._console, msgStr))

    def update_progress(self, progUpdate=None, progMsg=None):
        if self._active:
            if progUpdate is None or self._progBar is None:
                msgStr = STATUS_LBL_WAIT if progMsg is None else progMsg
                self._progBar = self._make_progressbar(self._console)
                self._progTaskID = self._progBar.add_task(description=msgStr, total=MAX_PROGBAR)
                self._layout['actCurrent'].update(self._progBar)
            else:
                self._progBar.update(self._progTaskID, completed=progUpdate) # type: ignore
                # assert False
