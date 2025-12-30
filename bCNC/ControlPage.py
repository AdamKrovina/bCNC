# $Id$
#
# Author: vvlachoudis@gmail.com
# Date: 18-Jun-2015

import math
import time
from tkinter import (
    TclError,
    FALSE,
    YES,
    N,
    S,
    W,
    E,
    EW,
    NSEW,
    CENTER,
    X,
    BOTH,
    LEFT,
    TOP,
    RIGHT,
    BOTTOM,
    FLAT,
    HORIZONTAL,
    END,
    NORMAL,
    DISABLED,
    #  UNITS,
    IntVar,
    BooleanVar,
    Button,
    Checkbutton,
    Entry,
    Frame,
    Label,
    Menu,
    Radiobutton,
    Scale,
    messagebox,
)

from CNC import CNC
import CNCRibbon
import Ribbon
import Sender
import tkExtra
import Unicode
import Utils
from CNC import DISTANCE_MODE, FEED_MODE, PLANE, WCS
from _GenericGRBL import ERROR_CODES

from Helpers import N_

__author__ = "Vasilis Vlachoudis"
__email__ = "vvlachoudis@gmail.com"

# Fallback definition of translation function _ if not provided by runtime
try:
    _  # noqa: F821
except NameError:  # pragma: no cover
    try:
        from gettext import gettext as _
    except Exception:
        _ = lambda s: s


# ----------------------------------------------------------------------
# Helper: run_lines_and_wait
#
# Module-level helper so any page/frame can submit a small sequence via
# Application.run() and wait for it to finish. This avoids attaching the
# helper method only to ControlPage instances (which caused attribute
# errors when other frames tried to call it).
def run_lines_and_wait(app, lines, wait_before=5.0, wait_after=10.0):
    """Run a small ad-hoc lines sequence through app.run and wait for it.

    - app: Application instance (must implement .run() and have .running/.update())
    - lines: list of lines (strings and/or %wait tokens)
    - wait_before: seconds to wait for any previous run to finish
    - wait_after: seconds to wait for the started run to complete

    Returns True if the run completed, False on timeout or failure.
    """
    t0 = time.time()
    while time.time() - t0 < wait_before and getattr(app, "running", False):
        try:
            app.update()
        except Exception:
            pass
        time.sleep(0.05)

    if getattr(app, "running", False):
        try:
            app.log.put((Sender.Sender.MSG_ERROR, "ATC: previous run did not finish before starting next sequence"))
        except Exception:
            pass
        return False

    try:
        app.run(lines=lines)
    except Exception:
        try:
            app.log.put((Sender.Sender.MSG_ERROR, "ATC: failed to start run sequence"))
        except Exception:
            pass
        return False

    # Capture expected runLines immediately after starting run so we can
    # detect if the run terminates prematurely (no progress).
    try:
        expected_run_lines = getattr(app, "_runLines", None)
    except Exception:
        expected_run_lines = None

    # clear any previous ATC-abort flag and add debug reporting
    try:
        app._atc_aborted = False
    except Exception:
        pass

    # Debug: report queued size and preview (helpful to see what's been enqueued)
    try:
        try:
            qsize = app.queue.qsize()
        except Exception:
            qsize = None
        app.log.put((Sender.Sender.MSG_SEND, f"DEBUG: run started; queue size={qsize}"))
        try:
            app.log.put((Sender.Sender.MSG_SEND, f"DEBUG: run state after app.run: _runLines={getattr(app,'_runLines',None)} _gcount={getattr(app,'_gcount',None)} running={getattr(app,'running',None)}"))
        except Exception:
            pass
        try:
            preview = list(app.queue.queue)[:10]
            app.log.put((Sender.Sender.MSG_SEND, "DEBUG: queue preview types=" + 
                         str([type(x).__name__ for x in preview]) ))
        except Exception:
            pass
    except Exception:
        pass

    t1 = time.time()
    while time.time() - t1 < wait_after and getattr(app, "running", False):
        try:
            app.update()
        except Exception:
            print("app.update() failed during run wait");
            pass
        time.sleep(0.05)

    if getattr(app, "running", False):
        try:
            app.log.put((Sender.Sender.MSG_ERROR, "ATC: run sequence timeout"))
        except Exception:
            print("app.log.put() failed during run wait");
            pass
        return False
    # Run finished (app.running is False). Check whether it finished with
    # expected progress. If the sender did not execute any lines (or fewer
    # than expected), mark ATC aborted so callers can stop their routines.
    try:
        # The sender resets _gcount to 0 in runEnded(). Prefer the
        # stored final count if available.
        gcount = getattr(app, "_last_run_completed", None)
        if gcount is None:
            gcount = getattr(app, "_gcount", None)

        # If we recorded expected_run_lines and it was positive, but gcount is
        # None or less than expected (especially zero), treat it as aborted.
        if expected_run_lines and expected_run_lines > 0 and (gcount is None or gcount < expected_run_lines):
            # Before aborting immediately, perform a single retry after a short delay
            # to handle transient controller resets or transient comms errors.
            retry_sleep = 1.0  # seconds (user-requested)
            try:
                app.log.put((Sender.Sender.MSG_SEND, f"DEBUG: ATC: detected premature end (gcount={gcount} expected={expected_run_lines}); retrying after {retry_sleep}s"))
            except Exception:
                pass
            # Small delay then try the run again once
            time.sleep(retry_sleep)
            try:
                # Clear previous abort flag and re-run
                try:
                    app._atc_aborted = False
                except Exception:
                    pass
                app.run(lines=lines)
            except Exception:
                pass

            # Wait again for the run to finish (same wait_after)
            t2 = time.time()
            while time.time() - t2 < wait_after and getattr(app, "running", False):
                try:
                    app.update()
                except Exception:
                    pass
                time.sleep(0.05)

            # Check final completed count again (prefer stored final value)
            gcount = getattr(app, "_last_run_completed", None)
            if gcount is None:
                gcount = getattr(app, "_gcount", None)

            if expected_run_lines and expected_run_lines > 0 and (gcount is None or gcount < expected_run_lines):
                try:
                    app._atc_aborted = True
                except Exception:
                    pass
                try:
                    app.log.put((Sender.Sender.MSG_ERROR, "ATC: run ended prematurely - aborting ATC routine"))
                except Exception:
                    pass
                return False
    except Exception:
        pass
    return True


# ----------------------------------------------------------------------
# Helper: persist current tool to the Control page (single place)
def persist_current_tool(app, tool):
    """Persist tool using the Control page's persist_tool() if available.

    - app: Application instance
    - tool: tool number to persist

    This centralizes the lookup so callers (from other frames) don't have
    to duplicate the lookup and error handling.
    """
    try:
        pages = getattr(app, "pages", {}) or {}
        control_page = pages.get("Control")
        if control_page and hasattr(control_page, "persist_tool"):
            try:
                res = control_page.persist_tool(tool)
                # If the page returns a boolean, respect it. If it raises,
                # allow exception to be caught below and return False.
                if res is False:
                    return False
                return True
            except Exception:
                try:
                    app.log.put((Sender.Sender.MSG_ERROR, "ATC: persist_tool raised an exception"))
                except Exception:
                    pass
                return False
        # fallback: find any page that implements persist_tool
        for page in pages.values():
            try:
                if hasattr(page, "persist_tool"):
                    try:
                        res = page.persist_tool(tool)
                        if res is False:
                            return False
                        return True
                    except Exception:
                        continue
            except Exception:
                continue
        try:
            # best-effort logging if no persist implementation found
            app.log.put((Sender.Sender.MSG_ERROR, "ATC: persist_tool not found on any page"))
        except Exception:
            pass
    except Exception:
        try:
            app.log.put((Sender.Sender.MSG_ERROR, "ATC: persist_current_tool failed"))
        except Exception:
            pass
    return False



_LOWSTEP = 0.0001
_HIGHSTEP = 1000.0
_HIGHZSTEP = 10.0
_NOZSTEP = "XY"
_HIGHASTEP = 90.0
_NOASTEP = "BC"

OVERRIDES = ["Feed", "Rapid", "Spindle"]

# override for init
UNITS = {"G20": "inch", "G21": "mm"}

# =============================================================================
# Connection Group
# =============================================================================


class ConnectionGroup(CNCRibbon.ButtonMenuGroup):
    def __init__(self, master, app):
        CNCRibbon.ButtonMenuGroup.__init__(
            self,
            master,
            N_("Connection"),
            app,
            [(_("Hard Reset"), "reset", app.hardReset)],
        )
        self.grid2rows()

        # ---
        col, row = 0, 1
        b = Ribbon.LabelButton(
            self.frame,
            image=Utils.icons["home32"],
            text=_("Home"),
            compound=BOTTOM,
            anchor=W,
            command=app.home,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, rowspan=2, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Perform a homing cycle [$H] now"))
        self.addWidget(b)

        # ---
        col, row = 1, 0
        b = Ribbon.LabelButton(
            self.frame,
            image=Utils.icons["unlock"],
            text=_("Unlock"),
            compound=LEFT,
            anchor=W,
            command=app.unlock,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Unlock controller [$X]"))
        self.addWidget(b)

        row += 1
        b = Ribbon.LabelButton(
            self.frame,
            image=Utils.icons["serial"],
            text=_("Connection"),
            compound=LEFT,
            anchor=W,
            command=lambda s=self: s.event_generate("<<Connect>>"),
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Open/Close connection"))
        self.addWidget(b)

        row += 1
        b = Ribbon.LabelButton(
            self.frame,
            image=Utils.icons["reset"],
            text=_("Reset"),
            compound=LEFT,
            anchor=W,
            command=app.softReset,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Software reset of controller [ctrl-x]"))
        self.addWidget(b)


# =============================================================================
# User Group
# =============================================================================
class UserGroup(CNCRibbon.ButtonGroup):
    def __init__(self, master, app):
        CNCRibbon.ButtonGroup.__init__(self, master, "User", app)
        self.grid3rows()

        n = Utils.getInt("Buttons", "n", 6)
        for i in range(1, n):
            b = Utils.UserButton(
                self.frame, self.app, i, anchor=W,
                background=Ribbon._BACKGROUND
            )
            col, row = divmod(i - 1, 3)
            b.grid(row=row, column=col, sticky=NSEW)
            self.addWidget(b)


# =============================================================================
# Run Group
# =============================================================================
class RunGroup(CNCRibbon.ButtonGroup):
    def __init__(self, master, app):
        CNCRibbon.ButtonGroup.__init__(self, master, "Run", app)

        b = Ribbon.LabelButton(
            self.frame,
            self,
            "<<Run>>",
            image=Utils.icons["start32"],
            text=_("Start"),
            compound=TOP,
            background=Ribbon._BACKGROUND,
        )
        b.pack(side=LEFT, fill=BOTH)
        tkExtra.Balloon.set(
            b, _("Run g-code commands from editor to controller"))
        self.addWidget(b)

        b = Ribbon.LabelButton(
            self.frame,
            self,
            "<<Pause>>",
            image=Utils.icons["pause32"],
            text=_("Pause"),
            compound=TOP,
            background=Ribbon._BACKGROUND,
        )
        b.pack(side=LEFT, fill=BOTH)
        tkExtra.Balloon.set(
            b,
            _("Pause running program. Sends either FEED_HOLD ! "
              + "or CYCLE_START ~")
        )

        b = Ribbon.LabelButton(
            self.frame,
            self,
            "<<Stop>>",
            image=Utils.icons["stop32"],
            text=_("Stop"),
            compound=TOP,
            background=Ribbon._BACKGROUND,
        )
        b.pack(side=LEFT, fill=BOTH)
        tkExtra.Balloon.set(
            b, _("Pause running program and soft reset controller to "
                 + "empty the buffer.")
        )


# =============================================================================
# DRO Frame
# =============================================================================
class DROFrame(CNCRibbon.PageFrame):
    dro_status = ("Helvetica", 12, "bold")
    dro_wpos = ("Helvetica", 12, "bold")
    dro_mpos = ("Helvetica", 12)

    def __init__(self, master, app):
        CNCRibbon.PageFrame.__init__(self, master, "DRO", app)

        DROFrame.dro_status = Utils.getFont("dro.status", DROFrame.dro_status)
        DROFrame.dro_wpos = Utils.getFont("dro.wpos", DROFrame.dro_wpos)
        DROFrame.dro_mpos = Utils.getFont("dro.mpos", DROFrame.dro_mpos)

        row = 0
        col = 0
        Label(self, text=_("Status:")).grid(row=row, column=col, sticky=E)
        col += 1
        self.state = Button(
            self,
            text=Sender.NOT_CONNECTED,
            font=DROFrame.dro_status,
            command=self.showState,
            cursor="hand1",
            background=Sender.STATECOLOR[Sender.NOT_CONNECTED],
            activebackground="LightYellow",
        )
        self.state.grid(row=row, column=col, columnspan=3, sticky=EW)
        tkExtra.Balloon.set(
            self.state,
            _(
                "Show current state of the machine\n"
                "Click to see details\n"
                "Right-Click to clear alarm/errors"
            ),
        )
        self.state.bind("<Button-3>", self.stateMenu)

        row += 1
        col = 0
        Label(self, text=_("WPos:")).grid(row=row, column=col, sticky=E)

        # work
        col += 1
        self.xwork = Entry(
            self,
            font=DROFrame.dro_wpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            relief=FLAT,
            borderwidth=0,
            justify=RIGHT,
        )
        self.xwork.grid(row=row, column=col, padx=1, sticky=EW)
        tkExtra.Balloon.set(self.xwork, _("X work position (click to set)"))
        self.xwork.bind("<FocusIn>", self.workFocus)
        self.xwork.bind("<Return>", self.setX)
        self.xwork.bind("<KP_Enter>", self.setX)

        # ---
        col += 1
        self.ywork = Entry(
            self,
            font=DROFrame.dro_wpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            relief=FLAT,
            borderwidth=0,
            justify=RIGHT,
        )
        self.ywork.grid(row=row, column=col, padx=1, sticky=EW)
        tkExtra.Balloon.set(self.ywork, _("Y work position (click to set)"))
        self.ywork.bind("<FocusIn>", self.workFocus)
        self.ywork.bind("<Return>", self.setY)
        self.ywork.bind("<KP_Enter>", self.setY)

        # ---
        col += 1
        self.zwork = Entry(
            self,
            font=DROFrame.dro_wpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            relief=FLAT,
            borderwidth=0,
            justify=RIGHT,
        )
        self.zwork.grid(row=row, column=col, padx=1, sticky=EW)
        tkExtra.Balloon.set(self.zwork, _("Z work position (click to set)"))
        self.zwork.bind("<FocusIn>", self.workFocus)
        self.zwork.bind("<Return>", self.setZ)
        self.zwork.bind("<KP_Enter>", self.setZ)

        # Machine
        row += 1
        col = 0
        Label(self, text=_("MPos:")).grid(row=row, column=col, sticky=E)

        col += 1
        self.xmachine = Label(
            self,
            font=DROFrame.dro_mpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            anchor=E,
        )
        self.xmachine.grid(row=row, column=col, padx=1, sticky=EW)

        col += 1
        self.ymachine = Label(
            self,
            font=DROFrame.dro_mpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            anchor=E,
        )
        self.ymachine.grid(row=row, column=col, padx=1, sticky=EW)

        col += 1
        self.zmachine = Label(
            self,
            font=DROFrame.dro_mpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            anchor=E,
        )
        self.zmachine.grid(row=row, column=col, padx=1, sticky=EW)

        # Set buttons
        row += 1
        col = 1

        self.xzero = Button(
            self,
            text=_("X=0"),
            command=self.setX0,
            activebackground="LightYellow",
            padx=2,
            pady=1,
        )
        self.xzero.grid(row=row, column=col, pady=0, sticky=EW)
        tkExtra.Balloon.set(
            self.xzero, _("Set X coordinate to zero "
                          + "(or to typed coordinate in WPos)")
        )
        self.addWidget(self.xzero)

        col += 1
        self.yzero = Button(
            self,
            text=_("Y=0"),
            command=self.setY0,
            activebackground="LightYellow",
            padx=2,
            pady=1,
        )
        self.yzero.grid(row=row, column=col, pady=0, sticky=EW)
        tkExtra.Balloon.set(
            self.yzero, _("Set Y coordinate to zero "
                          + "(or to typed coordinate in WPos)")
        )
        self.addWidget(self.yzero)

        col += 1
        self.zzero = Button(
            self,
            text=_("Z=0"),
            command=self.setZ0,
            activebackground="LightYellow",
            padx=2,
            pady=1,
        )
        self.zzero.grid(row=row, column=col, pady=0, sticky=EW)
        tkExtra.Balloon.set(
            self.zzero, _("Set Z coordinate to zero "
                          + "(or to typed coordinate in WPos)")
        )
        self.addWidget(self.zzero)

        # Set buttons
        row += 1
        col = 1
        f = Frame(self)
        f.grid(row=row, column=col, columnspan=3, pady=0, sticky=EW)

        b = Button(
            f,
            text=_("Set WPOS"),
            image=Utils.icons["origin"],
            compound=LEFT,
            activebackground="LightYellow",
            command=lambda s=self: s.event_generate("<<SetWPOS>>"),
            padx=2,
            pady=1,
        )
        b.pack(side=LEFT, fill=X, expand=YES)
        tkExtra.Balloon.set(b, _("Set WPOS to mouse location"))
        self.addWidget(b)

        b = Button(
            f,
            text=_("Move Gantry"),
            image=Utils.icons["gantry"],
            compound=LEFT,
            activebackground="LightYellow",
            command=lambda s=self: s.event_generate("<<MoveGantry>>"),
            padx=2,
            pady=1,
        )
        b.pack(side=RIGHT, fill=X, expand=YES)
        tkExtra.Balloon.set(b, _("Move gantry to mouse location [g]"))
        self.addWidget(b)

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)

    # ----------------------------------------------------------------------
    def stateMenu(self, event=None):
        menu = Menu(self, tearoff=0)

        menu.add_command(
            label=_("Show Info"),
            image=Utils.icons["info"],
            compound=LEFT,
            command=self.showState,
        )
        menu.add_command(
            label=_("Clear Message"),
            image=Utils.icons["clear"],
            compound=LEFT,
            command=lambda s=self: s.event_generate("<<AlarmClear>>"),
        )
        menu.add_separator()

        menu.add_command(
            label=_("Feed hold"),
            image=Utils.icons["pause"],
            compound=LEFT,
            command=lambda s=self: s.event_generate("<<FeedHold>>"),
        )
        menu.add_command(
            label=_("Resume"),
            image=Utils.icons["start"],
            compound=LEFT,
            command=lambda s=self: s.event_generate("<<Resume>>"),
        )

        menu.tk_popup(event.x_root, event.y_root)

    # ----------------------------------------------------------------------
    def updateState(self):
        msg = self.app._msg or CNC.vars["state"]
        if CNC.vars["pins"] is not None and CNC.vars["pins"] != "":
            msg += " [" + CNC.vars["pins"] + "]"
        self.state.config(text=msg, background=CNC.vars["color"])

    # ----------------------------------------------------------------------
    def updateCoords(self):
        try:
            focus = self.focus_get()
        except Exception:
            focus = None
        if focus is not self.xwork:
            self.xwork.delete(0, END)
            self.xwork.insert(0, self.padFloat(CNC.drozeropad, CNC.vars["wx"]))
        if focus is not self.ywork:
            self.ywork.delete(0, END)
            self.ywork.insert(0, self.padFloat(CNC.drozeropad, CNC.vars["wy"]))
        if focus is not self.zwork:
            self.zwork.delete(0, END)
            self.zwork.insert(0, self.padFloat(CNC.drozeropad, CNC.vars["wz"]))

        self.xmachine["text"] = self.padFloat(CNC.drozeropad, CNC.vars["mx"])
        self.ymachine["text"] = self.padFloat(CNC.drozeropad, CNC.vars["my"])
        self.zmachine["text"] = self.padFloat(CNC.drozeropad, CNC.vars["mz"])
        self.app.abcdro.updateCoords()

    # ----------------------------------------------------------------------
    def padFloat(self, decimals, value):
        if decimals > 0:
            return f"{value:0.{decimals}f}"
        else:
            return value

    # ----------------------------------------------------------------------
    # Do not give the focus while we are running
    # ----------------------------------------------------------------------
    def workFocus(self, event=None):
        if self.app.running:
            self.app.focus_set()

    # ----------------------------------------------------------------------
    def setX0(self, event=None):
        self.app.mcontrol._wcsSet("0", None, None, None, None, None)

    # ----------------------------------------------------------------------
    def setY0(self, event=None):
        self.app.mcontrol._wcsSet(None, "0", None, None, None, None)

    # ----------------------------------------------------------------------
    def setZ0(self, event=None):
        self.app.mcontrol._wcsSet(None, None, "0", None, None, None)

    # ----------------------------------------------------------------------
    def setXY0(self, event=None):
        self.app.mcontrol._wcsSet("0", "0", None, None, None, None)

    # ----------------------------------------------------------------------
    def setXYZ0(self, event=None):
        self.app.mcontrol._wcsSet("0", "0", "0", None, None, None)

    # ----------------------------------------------------------------------
    def setX(self, event=None):
        if self.app.running:
            return
        try:
            value = round(eval(self.xwork.get(), None, CNC.vars), 3)
            self.app.mcontrol._wcsSet(value, None, None, None, None, None)
        except Exception:
            pass

    # ----------------------------------------------------------------------
    def setY(self, event=None):
        if self.app.running:
            return
        try:
            value = round(eval(self.ywork.get(), None, CNC.vars), 3)
            self.app.mcontrol._wcsSet(None, value, None, None, None, None)
        except Exception:
            pass

    # ----------------------------------------------------------------------
    def setZ(self, event=None):
        if self.app.running:
            return
        try:
            value = round(eval(self.zwork.get(), None, CNC.vars), 3)
            self.app.mcontrol._wcsSet(None, None, value, None, None, None)
        except Exception:
            pass

    # ----------------------------------------------------------------------
    def showState(self):
        err = CNC.vars["errline"]
        if err:
            msg = _("Last error: {}\n").format(CNC.vars["errline"])
        else:
            msg = ""

        state = CNC.vars["state"]
        msg += ERROR_CODES.get(
            state, _("No info available.\nPlease contact the author.")
        )
        messagebox.showinfo(_("State: {}").format(state), msg, parent=self)


    def doNothing(self, event=None):
        return
# =============================================================================
# DRO Frame ABC
# =============================================================================
class abcDROFrame(CNCRibbon.PageExLabelFrame):

    dro_status = ("Helvetica", 12, "bold")
    dro_wpos = ("Helvetica", 12, "bold")
    dro_mpos = ("Helvetica", 12)

    def __init__(self, master, app):
        CNCRibbon.PageExLabelFrame.__init__(
            self, master, "abcDRO", _("abcDRO"), app)

        frame = Frame(self())
        frame.pack(side=TOP, fill=X)

        abcDROFrame.dro_status = Utils.getFont(
            "dro.status", abcDROFrame.dro_status)
        abcDROFrame.dro_wpos = Utils.getFont("dro.wpos", abcDROFrame.dro_wpos)
        abcDROFrame.dro_mpos = Utils.getFont("dro.mpos", abcDROFrame.dro_mpos)

        row = 0
        col = 0
        Label(frame, text=_("abcWPos:")).grid(row=row, column=col)

        # work
        col += 1
        self.awork = Entry(
            frame,
            font=abcDROFrame.dro_wpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            width=8,
            relief=FLAT,
            borderwidth=0,
            justify=RIGHT,
        )
        self.awork.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(self.awork, _("A work position (click to set)"))
        self.awork.bind("<FocusIn>", self.workFocus)
        self.awork.bind("<Return>", self.setA)
        self.awork.bind("<KP_Enter>", self.setA)

        # ---
        col += 1
        self.bwork = Entry(
            frame,
            font=abcDROFrame.dro_wpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            width=8,
            relief=FLAT,
            borderwidth=0,
            justify=RIGHT,
        )
        self.bwork.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(self.bwork, _("B work position (click to set)"))
        self.bwork.bind("<FocusIn>", self.workFocus)
        self.bwork.bind("<Return>", self.setB)
        self.bwork.bind("<KP_Enter>", self.setB)

        # ---
        col += 1
        self.cwork = Entry(
            frame,
            font=abcDROFrame.dro_wpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            width=8,
            relief=FLAT,
            borderwidth=0,
            justify=RIGHT,
        )
        self.cwork.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(self.cwork, _("C work position (click to set)"))
        self.cwork.bind("<FocusIn>", self.workFocus)
        self.cwork.bind("<Return>", self.setC)
        self.cwork.bind("<KP_Enter>", self.setC)

        # Machine
        row += 1
        col = 0
        Label(frame, text=_("MPos:")).grid(row=row, column=col, sticky=E),

        col += 1
        self.amachine = Label(
            frame,
            font=abcDROFrame.dro_mpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            anchor=E,
        )
        self.amachine.grid(row=row, column=col, padx=1, sticky=EW)
        col += 1
        self.bmachine = Label(
            frame,
            font=abcDROFrame.dro_mpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            anchor=E,
        )
        self.bmachine.grid(row=row, column=col, padx=1, sticky=EW)

        col += 1
        self.cmachine = Label(
            frame,
            font=abcDROFrame.dro_mpos,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            anchor=E,
        )
        self.cmachine.grid(row=row, column=col, padx=1, sticky=EW)

        # Set buttons
        row += 1
        col = 1

        azero = Button(
            frame,
            text=_("A=0"),
            command=self.setA0,
            activebackground="LightYellow",
            padx=2,
            pady=1,
        )
        azero.grid(row=row, column=col, pady=0, sticky=EW)
        tkExtra.Balloon.set(
            azero, _("Set A coordinate to zero "
                     + "(or to typed coordinate in WPos)")
        )
        self.addWidget(azero)

        col += 1
        bzero = Button(
            frame,
            text=_("B=0"),
            command=self.setB0,
            activebackground="LightYellow",
            padx=2,
            pady=1,
        )
        bzero.grid(row=row, column=col, pady=0, sticky=EW)
        tkExtra.Balloon.set(
            bzero, _("Set B coordinate to zero "
                     + "(or to typed coordinate in WPos)")
        )
        self.addWidget(bzero)

        col += 1
        czero = Button(
            frame,
            text=_("C=0"),
            command=self.setC0,
            activebackground="LightYellow",
            padx=2,
            pady=1,
        )
        czero.grid(row=row, column=col, pady=0, sticky=EW)
        tkExtra.Balloon.set(
            czero, _("Set C coordinate to zero "
                     + "(or to typed coordinate in WPos)")
        )
        self.addWidget(czero)

        # Set buttons
        row += 1
        col = 1
        bczero = Button(
            frame,
            text=_("BC=0"),
            command=self.setBC0,
            activebackground="LightYellow",
            padx=2,
            pady=1,
        )
        bczero.grid(row=row, column=col, pady=0, sticky=EW)
        tkExtra.Balloon.set(
            bczero, _("Set BC coordinate to zero "
                      + "(or to typed coordinate in WPos)")
        )
        self.addWidget(bczero)

        col += 1
        abczero = Button(
            frame,
            text=_("ABC=0"),
            command=self.setABC0,
            activebackground="LightYellow",
            padx=2,
            pady=1,
        )
        abczero.grid(row=row, column=col, pady=0, sticky=EW, columnspan=2)
        tkExtra.Balloon.set(
            abczero, _("Set ABC coordinate to zero "
                       + "(or to typed coordinate in WPos)")
        )
        self.addWidget(abczero)

    # ----------------------------------------------------------------------

    def updateCoords(self):
        try:
            focus = self.focus_get()
        except Exception:
            focus = None
            if focus is not self.awork:
                self.awork.delete(0, END)
                self.awork.insert(0, self.padFloat(CNC.drozeropad,
                                                   CNC.vars["wa"]))
            if focus is not self.bwork:
                self.bwork.delete(0, END)
                self.bwork.insert(0, self.padFloat(CNC.drozeropad,
                                                   CNC.vars["wb"]))
            if focus is not self.cwork:
                self.cwork.delete(0, END)
                self.cwork.insert(0, self.padFloat(CNC.drozeropad,
                                                   CNC.vars["wc"]))

            self.amachine["text"] = self.padFloat(CNC.drozeropad,
                                                  CNC.vars["ma"])
            self.bmachine["text"] = self.padFloat(CNC.drozeropad,
                                                  CNC.vars["mb"])
            self.cmachine["text"] = self.padFloat(CNC.drozeropad,
                                                  CNC.vars["mc"])

    # ----------------------------------------------------------------------

    def padFloat(self, decimals, value):
        if decimals > 0:
            return f"{value:0.{decimals}f}"
        else:
            return value

    # ----------------------------------------------------------------------
    # Do not give the focus while we are running
    # ----------------------------------------------------------------------

    def workFocus(self, event=None):
        if self.app.running:
            self.app.focus_set()

    # ----------------------------------------------------------------------

    def setA0(self, event=None):
        self.app.mcontrol._wcsSet(None, None, None, "0", None, None)

    # ----------------------------------------------------------------------
    def setB0(self, event=None):
        self.app.mcontrol._wcsSet(None, None, None, None, "0", None)

    # ----------------------------------------------------------------------
    def setC0(self, event=None):
        self.app.mcontrol._wcsSet(None, None, None, None, None, "0")

    # ----------------------------------------------------------------------
    def setBC0(self, event=None):
        self.app.mcontrol._wcsSet(None, None, None, "0", "0", None)

    # ----------------------------------------------------------------------
    def setABC0(self, event=None):
        self.app.mcontrol._wcsSet(None, None, None, "0", "0", "0")

    # ----------------------------------------------------------------------
    def setA(self, event=None):
        if self.app.running:
            return
        try:
            value = round(eval(self.awork.get(), None, CNC.vars), 3)
            self.app.mcontrol._wcsSet(None, None, None, value, None, None)
        except Exception:
            pass

    # ----------------------------------------------------------------------
    def setB(self, event=None):
        if self.app.running:
            return
        try:
            value = round(eval(self.bwork.get(), None, CNC.vars), 3)
            self.app.mcontrol._wcsSet(None, None, None, None, value, None)
        except Exception:
            pass

    # ----------------------------------------------------------------------
    def setC(self, event=None):
        if self.app.running:
            return
        try:
            value = round(eval(self.cwork.get(), None, CNC.vars), 3)
            self.app.mcontrol._wcsSet(None, None, None, None, None, value)
        except Exception:
            pass

    # ----------------------------------------------------------------------
    def showState(self):
        err = CNC.vars["errline"]
        if err:
            msg = _("Last error: {}\n").format(CNC.vars["errline"])
        else:
            msg = ""

            state = CNC.vars["state"]
            msg += ERROR_CODES.get(
                state, _("No info available.\nPlease contact the author.")
            )
            messagebox.showinfo(_("State: {}").format(state), msg, parent=self)


# =============================================================================
# ControlFrame
# =============================================================================
class ControlFrame(CNCRibbon.PageExLabelFrame):
    def __init__(self, master, app):
        CNCRibbon.PageExLabelFrame.__init__(
            self, master, "Control", _("Control"), app)

        frame = Frame(self())
        frame.pack(side=TOP, fill=X)

        row, col = 0, 0
        Label(frame, text=_("Z")).grid(row=row, column=col)

        col += 3
        Label(frame, text=_("Y")).grid(row=row, column=col)

        # ---
        row += 1
        col = 0

        width = 3
        height = 2

        b = Button(
            frame,
            text=Unicode.BLACK_UP_POINTING_TRIANGLE,
            command=self.moveZup,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move +Z"))
        self.addWidget(b)

        col += 2
        b = Button(
            frame,
            text=Unicode.UPPER_LEFT_TRIANGLE,
            command=self.moveXdownYup,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move -X +Y"))
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.BLACK_UP_POINTING_TRIANGLE,
            command=self.moveYup,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move +Y"))
        self.addWidget(b)
        col += 1
        b = Button(
            frame,
            text=Unicode.UPPER_RIGHT_TRIANGLE,
            command=self.moveXupYup,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move +X +Y"))
        self.addWidget(b)

        col += 2
        b = Button(
            frame, text="\u00D710", command=self.mulStep,
            width=3, padx=1, pady=1
        )
        b.grid(row=row, column=col, sticky=EW + S)
        tkExtra.Balloon.set(b, _("Multiply step by 10"))
        self.addWidget(b)

        col += 1
        b = Button(frame, text=_("+"), command=self.incStep,
                   width=3, padx=1, pady=1)
        b.grid(row=row, column=col, sticky=EW + S)
        tkExtra.Balloon.set(b, _("Increase step by 1 unit"))
        self.addWidget(b)

        # ---
        row += 1

        col = 1
        Label(frame, text=_("X"),
              width=3, anchor=E).grid(row=row, column=col, sticky=E)

        col += 1
        b = Button(
            frame,
            text=Unicode.BLACK_LEFT_POINTING_TRIANGLE,
            command=self.moveXdown,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move -X"))
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.LARGE_CIRCLE,
            command=self.doNothing,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(
            b,
            _("Move to Origin.\nUser configurable button.\n"
              + "Right click to configure."),
        )
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.BLACK_RIGHT_POINTING_TRIANGLE,
            command=self.moveXup,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move +X"))
        self.addWidget(b)

        # --
        col += 1
        Label(frame, "", width=2).grid(row=row, column=col)

        col += 1
        self.step = tkExtra.Combobox(
            frame, width=6, background=tkExtra.GLOBAL_CONTROL_BACKGROUND
        )
        self.step.grid(row=row, column=col, columnspan=2, sticky=EW)
        self.step.set(Utils.config.get("Control", "step"))
        self.step.fill(
            map(float, Utils.config.get("Control", "steplist").split()))
        tkExtra.Balloon.set(self.step, _("Step for every move operation"))
        self.addWidget(self.step)

        # -- Separate zstep --
        try:
            zstep = Utils.config.get("Control", "zstep")
            self.zstep = tkExtra.Combobox(
                frame, width=4, background=tkExtra.GLOBAL_CONTROL_BACKGROUND
            )
            self.zstep.grid(row=row, column=0, columnspan=1, sticky=EW)
            self.zstep.set(zstep)
            zsl = [_NOZSTEP]
            zsl.extend(
                map(float, Utils.config.get("Control", "zsteplist").split()))
            self.zstep.fill(zsl)
            tkExtra.Balloon.set(self.zstep, _("Step for Z move operation"))
            self.addWidget(self.zstep)
        except Exception:
            self.zstep = self.step

        # Default steppings
        try:
            self.step1 = Utils.getFloat("Control", "step1")
        except Exception:
            self.step1 = 0.1

        try:
            self.step2 = Utils.getFloat("Control", "step2")
        except Exception:
            self.step2 = 1

        try:
            self.step3 = Utils.getFloat("Control", "step3")
        except Exception:
            self.step3 = 10

        # ---
        row += 1
        col = 0

        b = Button(
            frame,
            text=Unicode.BLACK_DOWN_POINTING_TRIANGLE,
            command=self.moveZdown,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move -Z"))
        self.addWidget(b)

        col += 2
        b = Button(
            frame,
            text=Unicode.LOWER_LEFT_TRIANGLE,
            command=self.moveXdownYdown,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move -X -Y"))
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.BLACK_DOWN_POINTING_TRIANGLE,
            command=self.moveYdown,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move -Y"))
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.LOWER_RIGHT_TRIANGLE,
            command=self.moveXupYdown,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move +X -Y"))
        self.addWidget(b)

        col += 2
        b = Button(
            frame, text="\u00F710", command=self.divStep, padx=1, pady=1)
        b.grid(row=row, column=col, sticky=EW + N)
        tkExtra.Balloon.set(b, _("Divide step by 10"))
        self.addWidget(b)

        col += 1
        b = Button(frame, text=_("-"), command=self.decStep, padx=1, pady=1)
        b.grid(row=row, column=col, sticky=EW + N)
        tkExtra.Balloon.set(b, _("Decrease step by 1 unit"))
        self.addWidget(b)

        try:
            self.tk.call("grid", "anchor", self, CENTER)
        except TclError:
            pass

    # ----------------------------------------------------------------------
    def saveConfig(self):
        Utils.setFloat("Control", "step", self.step.get())
        if self.zstep is not self.step:
            Utils.setFloat("Control", "zstep", self.zstep.get())

    # ----------------------------------------------------------------------
    # Jogging
    # ----------------------------------------------------------------------
    def getStep(self, axis="x"):
        if axis == "z":
            zs = self.zstep.get()
            if zs == _NOZSTEP:
                return self.step.get()
            else:
                return zs
        else:
            return self.step.get()

    def moveXup(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"X{self.step.get()}")

    def moveXdown(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"X-{self.step.get()}")

    def moveYup(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"Y{self.step.get()}")

    def moveYdown(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"Y-{self.step.get()}")

    def moveXdownYup(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"X-{self.step.get()}Y{self.step.get()}")

    def moveXupYup(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"X{self.step.get()}Y{self.step.get()}")

    def moveXdownYdown(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"X-{self.step.get()}Y-{self.step.get()}")

    def moveXupYdown(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"X{self.step.get()}Y-{self.step.get()}")

    def moveZup(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"Z{self.getStep('z')}")

    def moveZdown(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"Z-{self.getStep('z')}")

    def go2origin(self, event=None):
        self.sendGCode("G90")
        self.sendGCode("G0Z%d" % (CNC.vars["safe"]))
        self.sendGCode("G0X0Y0")
        self.sendGCode("G0Z0")

    # ----------------------------------------------------------------------
    def setStep(self, s, zs=None):
        self.step.set(f"{s:.4g}")
        if self.zstep is self.step or zs is None:
            self.event_generate("<<Status>>", data=_("Step: {:g}").format(s))
        else:
            self.zstep.set(f"{zs:.4g}")
            self.event_generate(
                "<<Status>>", data=_("Step: {:g}  Zstep: {:g} ").format(s, zs))

    # ----------------------------------------------------------------------
    @staticmethod
    def _stepPower(step):
        try:
            step = float(step)
            if step <= 0.0:
                step = 1.0
        except Exception:
            step = 1.0
        power = math.pow(10.0, math.floor(math.log10(step)))
        return round(step / power) * power, power

    # ----------------------------------------------------------------------
    def incStep(self, event=None):
        if event is not None and not self.acceptKey():
            return
        step, power = ControlFrame._stepPower(self.step.get())
        s = step + power
        if s < _LOWSTEP:
            s = _LOWSTEP
        elif s > _HIGHSTEP:
            s = _HIGHSTEP
        if self.zstep is not self.step and self.zstep.get() != _NOZSTEP:
            step, power = ControlFrame._stepPower(self.zstep.get())
            zs = step + power
            if zs < _LOWSTEP:
                zs = _LOWSTEP
            elif zs > _HIGHZSTEP:
                zs = _HIGHZSTEP
        else:
            zs = None
        self.setStep(s, zs)

    # ----------------------------------------------------------------------
    def decStep(self, event=None):
        if event is not None and not self.acceptKey():
            return
        step, power = ControlFrame._stepPower(self.step.get())
        s = step - power
        if s <= 0.0:
            s = step - power / 10.0
        if s < _LOWSTEP:
            s = _LOWSTEP
        elif s > _HIGHSTEP:
            s = _HIGHSTEP
        if self.zstep is not self.step and self.zstep.get() != _NOZSTEP:
            step, power = ControlFrame._stepPower(self.zstep.get())
            zs = step - power
            if zs <= 0.0:
                zs = step - power / 10.0
            if zs < _LOWSTEP:
                zs = _LOWSTEP
            elif zs > _HIGHZSTEP:
                zs = _HIGHZSTEP
        else:
            zs = None
        self.setStep(s, zs)

    # ----------------------------------------------------------------------
    def mulStep(self, event=None):
        if event is not None and not self.acceptKey():
            return
        step, power = ControlFrame._stepPower(self.step.get())
        s = step * 10.0
        if s < _LOWSTEP:
            s = _LOWSTEP
        elif s > _HIGHSTEP:
            s = _HIGHSTEP
        if self.zstep is not self.step and self.zstep.get() != _NOZSTEP:
            step, power = ControlFrame._stepPower(self.zstep.get())
            zs = step * 10.0
            if zs < _LOWSTEP:
                zs = _LOWSTEP
            elif zs > _HIGHZSTEP:
                zs = _HIGHZSTEP
        else:
            zs = None
        self.setStep(s, zs)

    # ----------------------------------------------------------------------
    def divStep(self, event=None):
        if event is not None and not self.acceptKey():
            return
        step, power = ControlFrame._stepPower(self.step.get())
        s = step / 10.0
        if s < _LOWSTEP:
            s = _LOWSTEP
        elif s > _HIGHSTEP:
            s = _HIGHSTEP
        if self.zstep is not self.step and self.zstep.get() != _NOZSTEP:
            step, power = ControlFrame._stepPower(self.zstep.get())
            zs = step / 10.0
            if zs < _LOWSTEP:
                zs = _LOWSTEP
            elif zs > _HIGHZSTEP:
                zs = _HIGHZSTEP
        else:
            zs = None
        self.setStep(s, zs)

    # ----------------------------------------------------------------------
    def setStep1(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.setStep(self.step1, self.step1)

    # ----------------------------------------------------------------------
    def setStep2(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.setStep(self.step2, self.step2)

    # ----------------------------------------------------------------------
    def setStep3(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.setStep(self.step3, self.step2)
        
    # ----------------------------------------------------------------------
    def doNothing(self, event=None):
        return

# =============================================================================
# abc ControlFrame
# =============================================================================


class abcControlFrame(CNCRibbon.PageExLabelFrame):
    def __init__(self, master, app):
        CNCRibbon.PageExLabelFrame.__init__(
            self, master, "abcControl", _("abcControl"), app
        )

        frame = Frame(self())
        frame.pack(side=TOP, fill=X)

        row, col = 0, 0
        Label(frame, text=_("A")).grid(row=row, column=col)

        col += 3
        Label(frame, text=_("C")).grid(row=row, column=col)

        # ---
        row += 1
        col = 0

        width = 3
        height = 2

        b = Button(
            frame,
            text=Unicode.BLACK_UP_POINTING_TRIANGLE,
            command=self.moveAup,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move +A"))
        self.addWidget(b)

        col += 2
        b = Button(
            frame,
            text=Unicode.UPPER_LEFT_TRIANGLE,
            command=self.moveBdownCup,
            width=width,
            height=height,
            activebackground="LightYellow",
        )

        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move -B +C"))
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.BLACK_UP_POINTING_TRIANGLE,
            command=self.moveCup,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move +C"))
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.UPPER_RIGHT_TRIANGLE,
            command=self.moveBupCup,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move +B +C"))
        self.addWidget(b)

        col += 2
        b = Button(
            frame, text="\u00D710", command=self.mulStep,
            width=3, padx=1, pady=1
        )
        b.grid(row=row, column=col, sticky=EW + S)
        tkExtra.Balloon.set(b, _("Multiply step by 10"))
        self.addWidget(b)

        col += 1
        b = Button(
            frame, text=_("+"), command=self.incStep, width=3, padx=1, pady=1)
        b.grid(row=row, column=col, sticky=EW + S)
        tkExtra.Balloon.set(b, _("Increase step by 1 unit"))
        self.addWidget(b)

        # ---
        row += 1

        col = 1
        Label(frame, text=_("B"),
              width=3, anchor=E).grid(row=row, column=col, sticky=E)

        col += 1
        b = Button(
            frame,
            text=Unicode.BLACK_LEFT_POINTING_TRIANGLE,
            command=self.moveBdown,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move -B"))
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.LARGE_CIRCLE,
            command=self.go2abcorigin,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Return ABC to 0."))
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.BLACK_RIGHT_POINTING_TRIANGLE,
            command=self.moveBup,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move +B"))
        self.addWidget(b)

        # --
        col += 1
        Label(frame, "", width=2).grid(row=row, column=col)

        col += 1
        self.step = tkExtra.Combobox(
            frame, width=6, background=tkExtra.GLOBAL_CONTROL_BACKGROUND
        )
        self.step.grid(row=row, column=col, columnspan=2, sticky=EW)
        self.step.set(Utils.config.get("abcControl", "step"))
        self.step.fill(
            map(float, Utils.config.get("abcControl", "abcsteplist").split())
        )
        tkExtra.Balloon.set(self.step, _("Step for every move operation"))
        self.addWidget(self.step)

        # -- Separate astep --
        try:
            astep = Utils.config.get("abcControl", "astep")
            self.astep = tkExtra.Combobox(
                frame, width=4, background=tkExtra.GLOBAL_CONTROL_BACKGROUND
            )
            self.astep.grid(row=row, column=0, columnspan=1, sticky=EW)
            self.astep.set(astep)
            asl = [_NOASTEP]
            asl.extend(
                map(float,
                    Utils.config.get("abcControl", "asteplist").split()))
            self.astep.fill(asl)
            tkExtra.Balloon.set(self.astep, _("Step for A move operation"))
            self.addWidget(self.astep)
        except Exception:
            self.astep = self.step

        # Default steppings
        try:
            self.step1 = Utils.getFloat("abcControl", "step1")
        except Exception:
            self.step1 = 0.1

        try:
            self.step2 = Utils.getFloat("abcControl", "step2")
        except Exception:
            self.step2 = 1

        try:
            self.step3 = Utils.getFloat("abcControl", "step3")
        except Exception:
            self.step3 = 10

        # ---
        row += 1
        col = 0

        b = Button(
            frame,
            text=Unicode.BLACK_DOWN_POINTING_TRIANGLE,
            command=self.moveAdown,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move -A"))
        self.addWidget(b)

        col += 2
        b = Button(
            frame,
            text=Unicode.LOWER_LEFT_TRIANGLE,
            command=self.moveBdownCdown,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move -B -C"))
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.BLACK_DOWN_POINTING_TRIANGLE,
            command=self.moveCdown,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move -C"))
        self.addWidget(b)

        col += 1
        b = Button(
            frame,
            text=Unicode.LOWER_RIGHT_TRIANGLE,
            command=self.moveBupCdown,
            width=width,
            height=height,
            activebackground="LightYellow",
        )
        b.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(b, _("Move +B -C"))
        self.addWidget(b)

        col += 2
        b = Button(
            frame, text="\u00F710", command=self.divStep, padx=1, pady=1)
        b.grid(row=row, column=col, sticky=EW + N)
        tkExtra.Balloon.set(b, _("Divide step by 10"))
        self.addWidget(b)

        col += 1
        b = Button(frame, text=_("-"), command=self.decStep, padx=1, pady=1)
        b.grid(row=row, column=col, sticky=EW + N)
        tkExtra.Balloon.set(b, _("Decrease step by 1 unit"))
        self.addWidget(b)

        try:
            self.tk.call("grid", "anchor", self, CENTER)
        except TclError:
            pass

    # ----------------------------------------------------------------------
    def saveConfig(self):
        Utils.setFloat("abcControl", "step", self.step.get())
        if self.astep is not self.step:
            Utils.setFloat("abcControl", "astep", self.astep.get())

    # ----------------------------------------------------------------------
    # Jogging
    # ----------------------------------------------------------------------
    def getStep(self, axis="a"):
        if axis == "a":
            aas = self.astep.get()
            if aas == _NOASTEP:
                return self.step.get()
            else:
                return aas
        else:
            return self.step.get()

    def moveBup(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"B{self.step.get()}")

    def moveBdown(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"B-{self.step.get()}")

    def moveCup(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"C{self.step.get()}")

    def moveCdown(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"C-{self.step.get()}")

    def moveBdownCup(self, event=None):
        if event is not None and not self.acceptKey():
            return
        # XXX: Possible error in original code lead to %C string; fixed by guessing from methods below.
        # Original: self.app.mcontrol.jog("B-%C%s"%(self.step.get(),self.step.get()))
        self.app.mcontrol.jog(f"B-{self.step.get()}C{self.step.get()}")

    def moveBupCup(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"B{self.step.get()}C{self.step.get()}")

    def moveBdownCdown(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"B-{self.step.get()}C-{self.step.get()}")

    def moveBupCdown(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"B{self.step.get()}C-{self.step.get()}")

    def moveAup(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"A{self.getStep('z')}")

    def moveAdown(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.app.mcontrol.jog(f"A-{self.getStep('z')}")

    def go2abcorigin(self, event=None):
        self.sendGCode("G90")
        self.sendGCode("G0B0C0")
        self.sendGCode("G0A0")

    # ----------------------------------------------------------------------
    def setStep(self, s, aas=None):
        self.step.set(f"{s:.4g}")
        if self.astep is self.step or aas is None:
            self.event_generate("<<Status>>", data=_("Step: {:g}").format(s))
        else:
            self.astep.set(f"{aas:.4g}")
            self.event_generate(
                "<<Status>>", data=_("Step: {:g}   Astep:{:g} ").format(s, aas)
            )

    # ----------------------------------------------------------------------
    @staticmethod
    def _stepPower(step):
        try:
            step = float(step)
            if step <= 0.0:
                step = 1.0
        except Exception:
            step = 1.0
        power = math.pow(10.0, math.floor(math.log10(step)))
        return round(step / power) * power, power

    # ----------------------------------------------------------------------
    def incStep(self, event=None):
        if event is not None and not self.acceptKey():
            return
        step, power = abcControlFrame._stepPower(self.step.get())
        s = step + power
        if s < _LOWSTEP:
            s = _LOWSTEP
        elif s > _HIGHSTEP:
            s = _HIGHSTEP
        if self.astep is not self.step and self.astep.get() != _NOASTEP:
            step, power = abcControlFrame._stepPower(self.astep.get())
            aas = step + power
            if aas < _LOWSTEP:
                aas = _LOWSTEP
            elif aas > _HIGHASTEP:
                aas = _HIGHASTEP
        else:
            aas = None
        self.setStep(s, aas)

    # ----------------------------------------------------------------------
    def decStep(self, event=None):
        if event is not None and not self.acceptKey():
            return
        step, power = abcControlFrame._stepPower(self.step.get())
        s = step - power
        if s <= 0.0:
            s = step - power / 10.0
        if s < _LOWSTEP:
            s = _LOWSTEP
        elif s > _HIGHSTEP:
            s = _HIGHSTEP
        if self.astep is not self.step and self.astep.get() != _NOASTEP:
            step, power = abcControlFrame._stepPower(self.astep.get())
            aas = step - power
            if aas <= 0.0:
                aas = step - power / 10.0
            if aas < _LOWSTEP:
                aas = _LOWSTEP
            elif aas > _HIGHASTEP:
                aas = _HIGHASTEP
        else:
            aas = None
        self.setStep(s, aas)

    # ----------------------------------------------------------------------
    def mulStep(self, event=None):
        if event is not None and not self.acceptKey():
            return
        step, power = abcControlFrame._stepPower(self.step.get())
        s = step * 10.0
        if s < _LOWSTEP:
            s = _LOWSTEP
        elif s > _HIGHSTEP:
            s = _HIGHSTEP
        if self.astep is not self.step and self.astep.get() != _NOASTEP:
            step, power = abcControlFrame._stepPower(self.astep.get())
            aas = step * 10.0
            if aas < _LOWSTEP:
                aas = _LOWSTEP
            elif aas > _HIGHASTEP:
                aas = _HIGHASTEP
        else:
            aas = None
        self.setStep(s, aas)

    # ----------------------------------------------------------------------
    def divStep(self, event=None):
        if event is not None and not self.acceptKey():
            return
        step, power = abcControlFrame._stepPower(self.step.get())
        s = step / 10.0
        if s < _LOWSTEP:
            s = _LOWSTEP
        elif s > _HIGHSTEP:
            s = _HIGHSTEP
        if self.astep is not self.step and self.astep.get() != _NOASTEP:
            step, power = abcControlFrame._stepPower(self.astep.get())
            aas = step / 10.0
            if aas < _LOWSTEP:
                aas = _LOWSTEP
            elif aas > _HIGHASTEP:
                aas = _HIGHASTEP
        else:
            aas = None
        self.setStep(s, aas)

    # ----------------------------------------------------------------------
    def setStep1(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.setStep(self.step1, self.step1)

    # ----------------------------------------------------------------------
    def setStep2(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.setStep(self.step2, self.step2)

    # ----------------------------------------------------------------------

    def setStep3(self, event=None):
        if event is not None and not self.acceptKey():
            return
        self.setStep(self.step3, self.step2)


# =============================================================================
# StateFrame
# =============================================================================


class StateFrame(CNCRibbon.PageExLabelFrame):
    def __init__(self, master, app):
        global wcsvar
        CNCRibbon.PageExLabelFrame.__init__(
            self, master, "State", _("State"), app)
        self._gUpdate = False

        # State
        f = Frame(self())
        f.pack(side=TOP, fill=X)

        # ===
        col, row = 0, 0
        f2 = Frame(f)
        f2.grid(row=row, column=col, columnspan=9, sticky=EW)
        for p, w in enumerate(WCS):
            col += 1
            b = Radiobutton(
                f2,
                text=w,
                foreground="DarkRed",
                font="Helvetica,14",
                padx=1,
                pady=1,
                variable=wcsvar,
                value=p,
                indicatoron=FALSE,
                activebackground="LightYellow",
                command=self.wcsChange,
            )
            b.pack(side=LEFT, fill=X, expand=YES)
            tkExtra.Balloon.set(b, _("Switch to workspace {}").format(w))
            self.addWidget(b)

        # Absolute or relative mode
        row += 1
        col = 0
        Label(f, text=_("Distance:")).grid(row=row, column=col, sticky=E)
        col += 1
        self.distance = tkExtra.Combobox(
            f,
            True,
            command=self.distanceChange,
            width=1,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
        )
        self.distance.fill(sorted(DISTANCE_MODE.values()))
        self.distance.grid(row=row, column=col, columnspan=2, sticky=EW)
        tkExtra.Balloon.set(self.distance, _("Distance Mode [G90,G91]"))
        self.addWidget(self.distance)

        # populate gstate dictionary
        self.gstate = {}  # $G state results widget dictionary
        for k, v in DISTANCE_MODE.items():
            self.gstate[k] = (self.distance, v)

        # Units mode
        col += 2
        Label(f, text=_("Units:")).grid(row=row, column=col, sticky=E)
        col += 1
        self.units = tkExtra.Combobox(
            f,
            True,
            command=self.unitsChange,
            width=1,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
        )
        self.units.fill(sorted(UNITS.values()))
        self.units.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(self.units, _("Units [G20, G21]"))
        for k, v in UNITS.items():
            self.gstate[k] = (self.units, v)
        self.addWidget(self.units)

        # Tool
        row += 1
        col = 0
        Label(f, text=_("Tool:")).grid(row=row, column=col, sticky=E)

        col += 1
        self.toolEntry = tkExtra.IntegerEntry(
            f, background=tkExtra.GLOBAL_CONTROL_BACKGROUND, width=5
        )
        self.toolEntry.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(self.toolEntry, _("Tool number [T#]"))
        self.addWidget(self.toolEntry)

        col += 1
        b = Button(f, text=_("set"), command=self.setTool, padx=1, pady=1)
        b.grid(row=row, column=col, sticky=W)
        self.addWidget(b)

        # Update-only option: skip measuring current tool, adopt new tool measurement directly
        col += 1
        try:
            self.atc_update_only = BooleanVar(value=False)
            cb_upd = Checkbutton(
                f,
                text=_("upd-only"),
                variable=self.atc_update_only,
                padx=1,
                pady=1,
                onvalue=True,
                offvalue=False,
            )
            cb_upd.grid(row=row, column=col, sticky=W)
            tkExtra.Balloon.set(
                cb_upd,
                _("ATC: Skip measuring current tool; measure new tool and write measured TLO into table without tolerance checks."),
            )
            self.addWidget(cb_upd)
        except Exception:
            pass

        # Plane
        col += 1
        Label(f, text=_("Plane:")).grid(row=row, column=col, sticky=E)
        col += 1
        self.plane = tkExtra.Combobox(
            f,
            True,
            command=self.planeChange,
            width=1,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
        )
        self.plane.fill(sorted(PLANE.values()))
        self.plane.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(self.plane, _("Plane [G17,G18,G19]"))
        self.addWidget(self.plane)

        for k, v in PLANE.items():
            self.gstate[k] = (self.plane, v)

        # Feed speed
        row += 1
        col = 0
        Label(f, text=_("Feed:")).grid(row=row, column=col, sticky=E)

        col += 1
        self.feedRate = tkExtra.FloatEntry(
            f,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            disabledforeground="Black",
            width=1,
        )
        self.feedRate.grid(row=row, column=col, sticky=EW)
        self.feedRate.bind("<Return>", self.setFeedRate)
        self.feedRate.bind("<KP_Enter>", self.setFeedRate)
        tkExtra.Balloon.set(self.feedRate, _("Feed Rate [F#]"))
        self.addWidget(self.feedRate)

        col += 1
        b = Button(f, text=_("set"), command=self.setFeedRate, padx=1, pady=1)
        b.grid(row=row, column=col, columnspan=2, sticky=W)
        self.addWidget(b)

        # Feed mode
        col += 1
        Label(f, text=_("Mode:")).grid(row=row, column=col, sticky=E)

        col += 1
        self.feedMode = tkExtra.Combobox(
            f,
            True,
            command=self.feedModeChange,
            width=1,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
        )
        self.feedMode.fill(sorted(FEED_MODE.values()))
        self.feedMode.grid(row=row, column=col, sticky=EW)
        tkExtra.Balloon.set(self.feedMode, _("Feed Mode [G93, G94, G95]"))
        for k, v in FEED_MODE.items():
            self.gstate[k] = (self.feedMode, v)
        self.addWidget(self.feedMode)

        # TLO
        row += 1
        col = 0
        Label(f, text=_("TLO:")).grid(row=row, column=col, sticky=E)

        col += 1
        self.tlo = tkExtra.FloatEntry(
            f,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            disabledforeground="Black",
            width=1,
        )
        self.tlo.grid(row=row, column=col, sticky=EW)
        self.tlo.bind("<Return>", self.setTLO)
        self.tlo.bind("<KP_Enter>", self.setTLO)
        tkExtra.Balloon.set(self.tlo, _("Tool length offset [G43.1#]"))
        self.addWidget(self.tlo)

        col += 1
        b = Button(f, text=_("set"), command=self.setTLO, padx=1, pady=1)
        b.grid(row=row, column=col, columnspan=2, sticky=W)
        self.addWidget(b)
        
#        col += 1
#        b = Button(f, text=_("Save TLOs"), command=self.saveConfig, padx=1, pady=1)
#        b.grid(row=row, column=col, columnspan=2, sticky=W)
#        self.addWidget(b)

        # g92
        col += 1
        Label(f, text=_("G92:")).grid(row=row, column=col, sticky=E)

        col += 1
        self.g92 = Label(f, text="")
        self.g92.grid(row=row, column=col, columnspan=3, sticky=EW)
        tkExtra.Balloon.set(self.g92, _("Set position [G92 X# Y# Z#]"))
        self.addWidget(self.g92)


        from functools import partial
        self.tlo1 = []
        tloColCnt = 3
        tloRowCnt = 4
        tloCount = tloColCnt*tloRowCnt
        tloNum = 0;
        row = row+1
        for col in range(tloColCnt):
            for row_i in range(tloRowCnt):
                

                Label(f, text=_(f"TLO {tloNum+1}:")).grid(row=row+row_i, column=col*3, sticky=E)
        
                self.tlo1.append(
                    tkExtra.FloatEntry(
                        f,
                        background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
                        disabledforeground="Black",
                        width=2,
                    )
                )
                self.tlo1[tloNum].grid(row=row+row_i, column=col*3+1, sticky=EW)
                f.grid_columnconfigure(col*3+1, weight=2)
                tkExtra.Balloon.set(self.tlo1[tloNum], _("Tool length offset [G43.1#]"))
                self.addWidget(self.tlo1[tloNum])
        
                b = Button(f, text=_("set"), command=partial(self.setTLO1, tloNum), padx=1, pady=1)
                b.grid(row=row+row_i, column=col*3+2, columnspan=1, sticky=W)
                self.addWidget(b)

                tloNum = tloNum + 1 



        # ---

        # Spindle
        f = Frame(self())
        f.pack(side=BOTTOM, fill=X)

        self.override = IntVar()
        self.override.set(100)
        self.spindle = BooleanVar()
        self.spindleSpeed = IntVar()

        col, row = 0, 0
        self.overrideCombo = tkExtra.Combobox(
            f, width=8, command=self.overrideComboChange
        )
        self.overrideCombo.fill(OVERRIDES)
        self.overrideCombo.grid(row=row, column=col, pady=0, sticky=EW)
        tkExtra.Balloon.set(self.overrideCombo, _("Select override type."))

        b = Button(f, text=_("Reset"), pady=0, command=self.resetOverride)
        b.grid(row=row + 1, column=col, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Reset override to 100%"))

        col += 1
        self.overrideScale = Scale(
            f,
            command=self.overrideChange,
            variable=self.override,
            showvalue=True,
            orient=HORIZONTAL,
            from_=25,
            to_=200,
            resolution=1,
        )
        self.overrideScale.bind("<Double-1>", self.resetOverride)
        self.overrideScale.bind("<Button-3>", self.resetOverride)
        self.overrideScale.grid(
            row=row, column=col, rowspan=2, columnspan=4, sticky=EW)
        tkExtra.Balloon.set(
            self.overrideScale,
            _("Set Feed/Rapid/Spindle Override. "
              + "Right or Double click to reset."),
        )

        self.overrideCombo.set(OVERRIDES[0])

        # ---
        row += 2
        col = 0
        b = Checkbutton(
            f,
            text=_("Spindle"),
            image=Utils.icons["spinningtop"],
            command=self.spindleControl,
            compound=LEFT,
            indicatoron=False,
            variable=self.spindle,
            padx=1,
            pady=0,
        )
        tkExtra.Balloon.set(b, _("Start/Stop spindle (M3/M5)"))
        b.grid(row=row, column=col, pady=0, sticky=NSEW)
        self.addWidget(b)

        col += 1
        b = Scale(
            f,
            variable=self.spindleSpeed,
            command=self.spindleControl,
            showvalue=True,
            orient=HORIZONTAL,
            from_=Utils.config.get("CNC", "spindlemin"),
            to_=Utils.config.get("CNC", "spindlemax"),
        )
        tkExtra.Balloon.set(b, _("Set spindle RPM"))
        b.grid(row=row, column=col, sticky=EW, columnspan=3)
        self.addWidget(b)

        f.grid_columnconfigure(1, weight=1)

        # Coolant control

        self.coolant = BooleanVar()
        self.mist = BooleanVar()
        self.flood = BooleanVar()

        row += 1
        col = 0
        Label(f, text=_("Coolant:")).grid(row=row, column=col, sticky=E)
        col += 1

        coolantDisable = Checkbutton(
            f,
            text=_("OFF"),
            command=self.coolantOff,
            indicatoron=False,
            variable=self.coolant,
            padx=1,
            pady=0,
        )
        tkExtra.Balloon.set(coolantDisable, _("Stop cooling (M9)"))
        coolantDisable.grid(row=row, column=col, pady=0, sticky=NSEW)
        self.addWidget(coolantDisable)

        col += 1
        floodEnable = Checkbutton(
            f,
            text=_("Flood"),
            command=self.coolantFlood,
            indicatoron=False,
            variable=self.flood,
            padx=1,
            pady=0,
        )
        tkExtra.Balloon.set(floodEnable, _("Start flood (M8)"))
        floodEnable.grid(row=row, column=col, pady=0, sticky=NSEW)
        self.addWidget(floodEnable)

        col += 1
        mistEnable = Checkbutton(
            f,
            text=_("Mist"),
            command=self.coolantMist,
            indicatoron=False,
            variable=self.mist,
            padx=1,
            pady=0,
        )
        tkExtra.Balloon.set(mistEnable, _("Start mist (M7)"))
        mistEnable.grid(row=row, column=col, pady=0, sticky=NSEW)
        self.addWidget(mistEnable)
        f.grid_columnconfigure(1, weight=1)

    # ----------------------------------------------------------------------
    def overrideChange(self, event=None):
        n = self.overrideCombo.get()
        c = self.override.get()
        CNC.vars["_Ov" + n] = c
        CNC.vars["_OvChanged"] = True

    # ----------------------------------------------------------------------
    def resetOverride(self, event=None):
        self.override.set(100)
        self.overrideChange()

    # ----------------------------------------------------------------------
    def overrideComboChange(self):
        n = self.overrideCombo.get()
        if n == "Rapid":
            self.overrideScale.config(to_=100, resolution=25)
        else:
            self.overrideScale.config(to_=200, resolution=1)
        self.override.set(CNC.vars["_Ov" + n])

    # ----------------------------------------------------------------------
    def _gChange(self, value, dictionary):
        for k, v in dictionary.items():
            if v == value:
                self.sendGCode(k)
                return

    # ----------------------------------------------------------------------
    def distanceChange(self):
        if self._gUpdate:
            return
        self._gChange(self.distance.get(), DISTANCE_MODE)

    # ----------------------------------------------------------------------
    def unitsChange(self):
        if self._gUpdate:
            return
        self._gChange(self.units.get(), UNITS)

    # ----------------------------------------------------------------------
    def feedModeChange(self):
        if self._gUpdate:
            return
        self._gChange(self.feedMode.get(), FEED_MODE)

    # ----------------------------------------------------------------------
    def planeChange(self):
        if self._gUpdate:
            return
        self._gChange(self.plane.get(), PLANE)

    # ----------------------------------------------------------------------
    def setFeedRate(self, event=None):
        if self._gUpdate:
            return
        try:
            feed = float(self.feedRate.get())
            self.sendGCode(f"F{feed:g}")
            self.event_generate("<<CanvasFocus>>")
        except ValueError:
            pass

    # ----------------------------------------------------------------------
    def setTLO(self, event=None):
        try:
            new_tlo = float(self.tlo.get())
            # Get current tool and its TLO
            cur_tool = int(CNC.vars.get("tool", 0) or 0)
            try:
                old_tlo = float(self.tlo1[cur_tool - 1].get()) if cur_tool > 0 else 0.0
            except Exception:
                old_tlo = 0.0
            
            # Get current machine and work position Z
            current_mz = float(CNC.vars.get("mz", 0.0))
            current_wz = float(CNC.vars.get("wz", 0.0))
            # Calculate WCS Z offset: preserve work position, adjust for tool change
            # wcoz = mz - wz - old_tlo + new_tlo
            wcoz = current_mz - current_wz - old_tlo + new_tlo
            print(f"DEBUG setTLO: current_mz={current_mz}, current_wz={current_wz}, old_tlo={old_tlo}, new_tlo={new_tlo}, wcoz={wcoz}")
            # Use G10 L2 to set absolute Z offset in WCS (persists in EEPROM)
            self.sendGCode(f"G10 L2 P1 Z{wcoz:g}")
            
            # Update tool number to 0 (manual/unknown tool)
            CNC.vars["tool"] = 0
            self.toolEntry.set(0)
            if not persist_current_tool(self.app, 0):
                print("WARNING: Failed to persist tool number 0")
            
            self.app.mcontrol.viewParameters()
            self.event_generate("<<CanvasFocus>>")
        except ValueError:
            pass
        
    # ----------------------------------------------------------------------
    def setTLO1(self, index, event=None):
        try:
            new_tlo = float(self.tlo1[index].get())
            new_tool = index + 1  # Table is 0-indexed, tools are 1-indexed
            
            # Get current tool and its TLO
            cur_tool = int(CNC.vars.get("tool", 0) or 0)
            try:
                old_tlo = float(self.tlo1[cur_tool - 1].get()) if cur_tool > 0 else 0.0
            except Exception:
                old_tlo = 0.0
            
            # Get current machine and work position Z
            current_mz = float(CNC.vars.get("mz", 0.0))
            current_wz = float(CNC.vars.get("wz", 0.0))
            # Calculate WCS Z offset: preserve work position, adjust for tool change
            # wcoz = mz - wz - old_tlo + new_tlo
            wcoz = current_mz - current_wz - old_tlo + new_tlo
            print(f"DEBUG setTLO1[{index}]: current_mz={current_mz}, current_wz={current_wz}, old_tlo={old_tlo}, new_tlo={new_tlo}, wcoz={wcoz}")
            # Use G10 L2 to set absolute Z offset in WCS (persists in EEPROM)
            self.sendGCode(f"G10 L2 P1 Z{wcoz:g}")
            
            # Update tool number to the selected tool
            CNC.vars["tool"] = new_tool
            self.toolEntry.set(new_tool)
            if not persist_current_tool(self.app, new_tool):
                print(f"WARNING: Failed to persist tool number {new_tool}")
            
            self.app.mcontrol.viewParameters()
            self.event_generate("<<CanvasFocus>>")
        except ValueError:
            pass
        
    # ----------------------------------------------------------------------
    def saveConfig(self):
        print("debug adam")
        for i in range(len(self.tlo1)):
            print(self.tlo1[i].get())
            Utils.setFloat("Control", "TLO%d" % i, self.tlo1[i].get())
            
    # ----------------------------------------------------------------------        
    def loadConfig(self):
        print("debug adam1")
        for i in range(len(self.tlo1)):
            print(Utils.getFloat("Control", "TLO%d" % i))
            self.tlo1[i].set(Utils.getFloat("Control", "TLO%d" % i))  
        # load ATC holder positions and setter (optional)
        self.loadATCConfig()
        # If a current tool was persisted in config, restore it so the
        # application knows which tool is presently loaded (prevents crash).
        try:
            cur = Utils.getStr("ATC", "current_tool", "")
            print("Loading actual tool from file ")
            if cur:
                try:
                    print(cur)
                    tool = int(cur)  # Validate it's a valid integer
                    CNC.vars["tool"] = tool
                    self.toolEntry.set(CNC.vars.get("tool", 0))
                except ValueError:
                    print(f"Error: Invalid tool number in config: {cur}")
                except Exception as e:
                    print(f"Error setting tool entry: {str(e)}")
        except Exception as e:
            print(f"Could not load current tool from config: {str(e)}")
        print("debug adam2")
    # ----------------------------------------------------------------------
    def loadATCConfig(self):
        # Load ATC configuration: holder positions and setter position
        # Holder positions: ATC.holderX1 / ATC.holderY1, holderX2/Y2 ... (1-based)
        # Approach positions: ATC.approachX1 / approachY1 / approachZ1 ... (1-based, optional)
        # Setter position: ATC.setterX / ATC.setterY / ATC.setterZ
        # Tolerance: ATC.tol
        try:
            holders = []
            for i in range(len(self.tlo1)):
                try:
                    x = Utils.getFloat("ATC", f"holderX{i+1}")
                    y = Utils.getFloat("ATC", f"holderY{i+1}")
                except Exception:
                    x = None
                    y = None
                # Load optional approach positions
                try:
                    ax = Utils.getFloat("ATC", f"approachX{i+1}")
                except Exception:
                    ax = None
                try:
                    ay = Utils.getFloat("ATC", f"approachY{i+1}")
                except Exception:
                    ay = None
                try:
                    az = Utils.getFloat("ATC", f"approachZ{i+1}")
                except Exception:
                    az = None
                holders.append((x, y, ax, ay, az))
            self.atc_holders = holders
        except Exception:
            self.atc_holders = []

        try:
            sx = Utils.getFloat("ATC", "setterX", Utils.getFloat("Probe", "toolprobex", 0.0))
        except Exception:
            sx = Utils.getFloat("Probe", "toolprobex", 0.0)
        try:
            sy = Utils.getFloat("ATC", "setterY", Utils.getFloat("Probe", "toolprobey", 0.0))
        except Exception:
            sy = Utils.getFloat("Probe", "toolprobey", 0.0)
        try:
            sz = Utils.getFloat("ATC", "setterZ", Utils.getFloat("Probe", "toolprobez", 0.0))
        except Exception:
            sz = Utils.getFloat("Probe", "toolprobez", 0.0)
        self.atc_setter = (sx, sy, sz)

        self.atc_tol = Utils.getFloat("ATC", "tol", 0.5)

    # ----------------------------------------------------------------------
    def _probeMeasure(self, timeout=100.0, expected_tlo=None, update_only=False):
        print("_probeMeasure called")
        self.app.log.put((Sender.Sender.MSG_OK, "ATC: _probeMeasure called"))
        # Run a probe sequence to measure tool on the tool setter.
        # Returns True if probe completed and CNC.vars['prbz'] updated, else None.
        old_prbz = CNC.vars.get("prbz", None)
        lines = [
            # go to probe change area and probe point (machine coords)
            "G53 G0 Z-1",
            "%wait",
            "g53 g0 x[toolprobex] y[toolprobey]",
            "%wait",
            "g53 g0 z[toolprobez]",
            "%wait",
        ]
        
        # Add slow approach if expected_tlo is provided and conditions are met
        if expected_tlo is not None and not update_only:
            toolprobez = CNC.vars.get("toolprobez", 0.0)
            # Calculate target Z: expected_tlo + toolprobez + 5mm reserve
            target_z = expected_tlo - toolprobez + 5.0
            # Only approach if target is below toolprobez (tool is shorter than probe position)
            if target_z < 0.0: # only if below current probe Z - only downwards
                print("_probeMeasure adding slow approach Z (relative) %.3f" % (target_z))
                lines.extend([
                    f"G54 G1 Z{target_z:.3f} F200",
                    "%wait",
                ])
        
        lines.extend([
            # single probe pass at configured probe feed
            "g91",
            "[prbcmd] f[70] z[-60]",
            "g4 p1",
            "%wait",
            "g90",
            "G53 G0 Z-1",
            "%wait",
            # export measured probe z to a global variable we can poll
            "%global atc_prbz; atc_prbz=prbz",
            "%update atc_prbz",
        ])

        ok = run_lines_and_wait(self.app, lines, wait_before=10, wait_after=timeout)
        if not ok:
            print("_probeMeasure failed to run probe");
            return None

        result = None
 
        # prefer explicit atc_prbz
        if "atc_prbz" in CNC.vars and CNC.vars.get("atc_prbz") is not None:
            result = CNC.vars.get("atc_prbz")
        elif CNC.vars.get("prbz") is not None and CNC.vars.get("prbz") != old_prbz:
            result = CNC.vars.get("prbz")
                
        print("_probeMeasure result %.3f" % (result) )
        return result
        
    # ----------------------------------------------------------------------
    def setTool(self, event=None, new_tool=None, update_only=False):
        # Semi-automatic ATC helper.
        # Sequence:
        #  1) measure current tool on tool setter (probe)
        #  2) compare measured TLO with table self.tlo1 for current tool
        #  3) if ok, move spindle to holder position for current tool
        #  4) prompt user to remove tool and insert new tool
        #  5) measure new tool on tool setter and compare with table
        #  6) if ok, update tool number and set TLO (G43.1)
        #print("ATC start");
        self.app.log.put((Sender.Sender.MSG_SEND, "ATC: Starting tool change routine"))
        #print("ATC start1");
        # Use class method persist_tool to save current tool to configuration
        # Allow callers to pass the desired tool programmatically
        if new_tool is None:
            try:
                new_tool = int(self.toolEntry.get())
            except Exception:
                messagebox.showerror(_("ATC error"), _("Invalid tool number"))
                return False
            
        # Allow UI checkbox to force update-only behavior (skip measuring current tool
        # and just adopt measured new tool TLO into table without comparison).
        if not update_only:
            try:
                # Checkbox may be created later; ignore if absent
                if getattr(self, "atc_update_only", None) is not None and self.atc_update_only.get():
                    update_only = True
            except Exception:
                pass

        cur_tool = int(CNC.vars.get("tool", 0) or 0)
        if cur_tool == new_tool:
            #messagebox.showinfo(_("ATC"), _("Already using requested tool"))
            #just continue silently
            return True

        # Use class helper self._run_lines_and_wait to submit sequences and wait

        # Ensure probe/toolmz info exists
        if CNC.vars.get("toolmz", None) is None:
            messagebox.showwarning(
                _("ATC"),
                _(
                    "Reference probe value (toolmz) not set. Please run Tools->Probe->Tool->Calibrate first."
                ),
            )
            return False
        
        print("ATCa");

        # Get old tool TLO from table for WCS offset calculation
        try:
            old_tool_tlo = float(self.tlo1[cur_tool - 1].get()) if cur_tool > 0 else 0.0
        except Exception:
            old_tool_tlo = 0.0

        # measure current tool (skip entirely if update_only)
        if not update_only:
            # Get expected TLO for current tool from table
            try:
                expected_old_tlo = float(self.tlo1[cur_tool - 1].get()) if cur_tool > 0 else None
            except Exception:
                expected_old_tlo = None
            
            measured_old = self._probeMeasure(expected_tlo=expected_old_tlo, update_only=False)
            if measured_old is None:
                messagebox.showerror(_("ATC"), _("Failed to measure current tool"))
                return False
            
            print("ATCb");

            # compute measured TLO using probe (prbz) minus reference toolmz
            measured_tlo_old = float(CNC.vars.get("prbz", 0.0)) - float(CNC.vars.get("toolmz", 0.0))

            print("measured_old %.3f" % (measured_old))
            print("toolmz %.2f" % float(CNC.vars.get("toolmz", 0.0)))
            print("prbz %.3f" % float(CNC.vars.get("prbz", 0.0)))
            print("measured_tlo_old %.3f" % (measured_tlo_old))

            # expected from table (tlo1 indexed from 0, tools usually numbered from 1)
            try:
                expected_old = float(self.tlo1[cur_tool - 1].get())
            except Exception:
                expected_old = None


            print("expected_old %.3f" % (expected_old))

            print("ATCc");

            tol = getattr(self, "atc_tol", Utils.getFloat("ATC", "tol", 0.5))

            print("cur_tool %.2f" % (cur_tool))

            print("tol %.3f" % (tol))

            if expected_old is None:
                # Just log and continue silently when no expected value exists
                self.app.log.put((Sender.Sender.MSG_SEND, "ATC: No expected old TLO; continuing"))
            else:
                if abs(measured_tlo_old - expected_old) > tol:
                    ans = messagebox.askyesno(
                        _("ATC Error"),
                        _(
                            "Current tool measurement {:.3f} differs from expected {:.3f} by more than tolerance {:.3f}. Continue?"
                        ).format(measured_tlo_old, expected_old, tol),
                    )
                    if not ans:
                        self.app.log.put((Sender.Sender.MSG_ERROR, "ATC: Aborted - current tool measurement out of tolerance"))
                        return False


        print("ATCd");

        # move to holder position for current tool to allow removal
        holder = None
        if hasattr(self, "atc_holders"):
            try:
                holder = self.atc_holders[cur_tool - 1]
            except Exception:
                holder = None

        print("ATCe");

        if holder and holder[0] is not None and holder[1] is not None:
            # Prefer automatic unload/load sequence using machine-specific G-code
            # provided by the user. If anything goes wrong, fall back to the
            # original simple holder moves.
            try:
                # Check if approach position is fully defined
                if len(holder) >= 5 and holder[2] is not None and holder[3] is not None and holder[4] is not None:
                    approach_x = holder[2]
                    approach_y = holder[3]
                    approach_z = holder[4]
                else:
                    # Approach position not configured: abort with error
                    messagebox.showerror(
                        _("ATC Error"),
                        _("Approach position (approachX, approachY, approachZ) not configured for holder {}. Please configure in bCNC.ini [ATC] section.").format(cur_tool)
                    )
                    return False

                unload_lines = [
                    ("G53 G0 Z-1", True),
                    (f"G53 G0 X{approach_x:g} Y{approach_y:g}", True),
                    (f"G53 G0 Z{approach_z:g}", True),
                    (f"G53 G0 Y{holder[1]:g}", True),
                    ("G4 P0", True),
                    ("M106 ;release", False),
                    ("G4 P0.2", True),
                    (f"G53 G0 Z{approach_z + 70:g}", True),
                    ("G4 P0", True),
                    ("M107 ;clamp", False),
                    ("G53 G0 Z-1", True),
                ]

                print("ATC run unload lines");

                # Submit unload sequence through the run/compile pipeline so the
                # sender thread will actually transmit the commands. Wait a
                # short time (timeout) for the sequence to finish.
                unload_run_lines = []
                for cmd, do_wait in unload_lines:
                    unload_run_lines.append(cmd)
                    if do_wait:
                        unload_run_lines.append("%wait")

                ok = run_lines_and_wait(self.app, unload_run_lines, wait_before=5.0, wait_after=40.0)
                if not ok:
                    # failed to run unload sequence in time
                    print("Failed to run unload sequence in time");
                    return False

            except Exception as e:
                # Do not perform automatic fallback. Ask user whether to try
                # the manual fallback (original simple moves). Abort if declined.
                try:
                    ans = messagebox.askyesno(
                        _("ATC"),
                        _(
                            "Automatic unload failed: %s\nDo you want to try the manual fallback moves to holder?"
                        ) % str(e),
                    )
                except Exception:
                    ans = False
                if ans:
                    # perform original simple moves as a user-approved fallback
                    self.sendGCode("G53 G0 Z%g" % (CNC.vars.get("safe", 0)))
                    self.sendGCode(f"G53 G0 X{holder[0]:g} Y{holder[1]:g}")
                    self.sendGCode("G53 G0 Z%g" % (CNC.vars.get("toolchangez", CNC.vars.get("toolmz", 0))))
                else:
                    # user declined fallback: abort operation
                    return False
        else:
            messagebox.showerror(
                _("ATC Error"),
                _("Holder position not configured for current tool {}. Please configure in bCNC.ini [ATC] section.").format(cur_tool)   
            )
            return False
            

        print("ATC set new tool");

        # move to holder position for new tool to allow loading
        holder = None
        if hasattr(self, "atc_holders"):
            try:
                holder = self.atc_holders[new_tool - 1]
            except Exception:
                holder = None


        print("ATC run load lines");

        # Try automatic load sequence to grab the new tool and measure it
        if holder and holder[0] is not None and holder[1] is not None:
            try:
                # Check if approach position is fully defined
                if len(holder) >= 5 and holder[2] is not None and holder[3] is not None and holder[4] is not None:
                    approach_x = holder[2]
                    approach_y = holder[3]
                    approach_z = holder[4]
                else:
                    # Approach position not configured: abort with error
                    messagebox.showerror(
                        _("ATC Error"),
                        _("Approach position (approachX, approachY, approachZ) not configured for holder {}. Please configure in bCNC.ini [ATC] section.").format(new_tool)
                    )
                    return False

                # Load sequence provided by user
                load_lines = [
                    ("G53 G0 Z-1", True),
                    (f"G53 G0 X{holder[0]:g} Y{holder[1]:g}", True),
                    (f"G53 G0 Z{approach_z + 70:g}", True),
                    ("G4 P0", False),
                    ("M106 ;release", False),
                    (f"G53 G0 Z{approach_z:g}", True),
                    ("G4 P0", False),
                    ("M107 ;clamp", False),
                    ("G4 P0.4", False),
                    (f"G53 G0 X{approach_x:g} Y{approach_y:g}", True),
                    ("G53 G0 Z-1", True),
                ]

                load_run_lines = []
                for cmd, do_wait in load_lines:
                    load_run_lines.append(cmd)
                    if do_wait:
                        load_run_lines.append("%wait")
                    self.app.log.put((Sender.Sender.MSG_SEND, "ATC: " + cmd))

                self.app.log.put((Sender.Sender.MSG_SEND, "ATC: Starting measurement of new tool"))
                ok = run_lines_and_wait(self.app, load_run_lines, wait_before=5.0, wait_after=80.0)
                if not ok:
                    return False

                # Update tool number immediately after successful load, before measurement
                CNC.vars["tool"] = new_tool
                self.toolEntry.set(new_tool)  # Update UI
                if not persist_current_tool(self.app, new_tool):
                    try:
                        messagebox.showerror(
                            _("ATC"),
                            _("Fatal: failed to persist current tool to disk. Aborting ATC.")
                        )
                    except Exception:
                        pass
                    return False

                # After automatic load, measure the new tool
                # Get expected TLO for new tool from table
                try:
                    expected_new_tlo = float(self.tlo1[new_tool - 1].get())
                except Exception:
                    expected_new_tlo = None
                
                measured_new = self._probeMeasure(expected_tlo=expected_new_tlo, update_only=update_only)
                if measured_new is None:
                    messagebox.showerror(_("ATC"), _("Failed to measure new tool"))
                    return False

                measured_tlo_new = float(CNC.vars.get("prbz", 0.0)) - float(CNC.vars.get("toolmz", 0.0))
                try:
                    existing_cell = self.tlo1[new_tool - 1]
                    expected_new = float(existing_cell.get())
                except Exception:
                    expected_new = None

                if update_only:
                    # Directly adopt measured value: update table cell and skip comparisons
                    try:
                        self.tlo1[new_tool - 1].set(f"{measured_tlo_new:.3f}")
                    except Exception:
                        pass
                    final_tlo = measured_tlo_new
                else:
                    if expected_new is None:
                        final_tlo = measured_tlo_new
                    else:
                        if abs(measured_tlo_new - expected_new) > tol:
                            messagebox.showerror(
                                _("ATC"),
                                _("New tool measurement not within tolerance. Aborting ATC."),
                            )
                            return False
                        final_tlo = expected_new

                # Get current machine and work position Z
                current_mz = float(CNC.vars.get("mz", 0.0))
                current_wz = float(CNC.vars.get("wz", 0.0))
                # Calculate WCS Z offset to preserve work position relative to workpiece
                # Current WCS offset = mz - wz, then adjust for tool change
                # wcoz_new = wcoz_old - old_tlo + new_tlo
                wcoz = current_mz - current_wz - old_tool_tlo + final_tlo
                print(f"DEBUG setTool auto: current_mz={current_mz}, current_wz={current_wz}, old_tool_tlo={old_tool_tlo}, final_tlo={final_tlo}, wcoz={wcoz}")
                # Use G10 L2 to set absolute Z offset in WCS (persists in EEPROM)
                gcode_cmd = f"G10 L2 P1 Z{wcoz:g}"
                print(f"DEBUG: About to send G-code: {gcode_cmd}")
                # Use run_lines_and_wait to send during program run (sendGCode blocked by self.running)
                ok = run_lines_and_wait(self.app, [gcode_cmd, "%wait"], wait_before=5, wait_after=3.0)
                if not ok:
                    print(f"WARNING: Failed to send G10 command: {gcode_cmd}")
                print(f"DEBUG: G-code sent: {gcode_cmd}")
                print("setting wz to %f" % (wcoz));

                # Persist TLO table change immediately when update_only active
                if update_only:
                    try:
                        self.saveConfig()
                    except Exception:
                        pass
                self.app.mcontrol.viewParameters()
                # Success: do not show the manual swap messagebox
                return True
            except Exception as e:
                # Do not automatically fallback. Ask user whether to proceed
                # with manual tool replacement and measurement. Abort if declined.
                try:
                    ans = messagebox.askyesno(
                        _("ATC"),
                        _(
                            "Automatic load failed: %s\nDo you want to try manual tool replacement and measurement?"
                        ) % str(e),
                    )
                except Exception:
                    ans = False
                if not ans:
                    return False

                # User accepted manual fallback: prompt them to swap tools
                messagebox.showinfo(
                    _("ATC"),
                    _(
                        "Please remove the old tool and insert the new tool T%02d. Click OK when ready."
                    ) % new_tool,
                )

                # Update tool number immediately after manual swap confirmation, before measurement
                CNC.vars["tool"] = new_tool
                self.toolEntry.set(new_tool)  # Update UI
                if not persist_current_tool(self.app, new_tool):
                    try:
                        messagebox.showerror(
                            _("ATC"),
                            _("Fatal: failed to persist current tool to disk. Aborting ATC.")
                        )
                    except Exception:
                        pass
                    return False

                # After user replaced tool, measure new tool
                measured_new = self._probeMeasure()
                if measured_new is None:
                    messagebox.showerror(_("ATC"), _("Failed to measure new tool"))
                    return False

                measured_tlo_new = float(CNC.vars.get("prbz", 0.0)) - float(CNC.vars.get("toolmz", 0.0))
                try:
                    existing_cell = self.tlo1[new_tool - 1]
                    expected_new = float(existing_cell.get())
                except Exception:
                    expected_new = None

                if update_only:
                    try:
                        self.tlo1[new_tool - 1].set(f"{measured_tlo_new:.3f}")
                    except Exception:
                        pass
                    final_tlo = measured_tlo_new
                else:
                    if expected_new is None:
                        ans2 = messagebox.askyesno(
                            _("ATC"),
                            _(
                                "No expected TLO for new tool in table. Accept measured value and continue?"
                            ),
                        )
                        if not ans2:
                            return False
                        final_tlo = measured_tlo_new
                    else:
                        if abs(measured_tlo_new - expected_new) > tol:
                            messagebox.showerror(
                                _("ATC"),
                                _("New tool measurement not within tolerance. Aborting ATC."),
                            )
                            return False
                        final_tlo = expected_new

                # Get current machine and work position Z
                current_mz = float(CNC.vars.get("mz", 0.0))
                current_wz = float(CNC.vars.get("wz", 0.0))
                # Calculate WCS Z offset to preserve work position relative to workpiece
                # Current WCS offset = mz - wz, then adjust for tool change
                # wcoz_new = wcoz_old - old_tlo + new_tlo
                wcoz = current_mz - current_wz - old_tool_tlo + final_tlo
                print(f"DEBUG setTool manual: current_mz={current_mz}, current_wz={current_wz}, old_tool_tlo={old_tool_tlo}, final_tlo={final_tlo}, wcoz={wcoz}")
                # Use G10 L2 to set absolute Z offset in WCS (persists in EEPROM)
                gcode_cmd = f"G10 L2 P1 Z{wcoz:g}"
                print(f"DEBUG: About to send G-code: {gcode_cmd}")
                # Use run_lines_and_wait to send during program run (sendGCode blocked by self.running)
                ok = run_lines_and_wait(self.app, [gcode_cmd, "%wait"], wait_before=5, wait_after=3.0)
                if not ok:
                    print(f"WARNING: Failed to send G10 command: {gcode_cmd}")
                print(f"DEBUG: G-code sent: {gcode_cmd}")

                if update_only:
                    try:
                        self.saveConfig()
                    except Exception:
                        pass
                self.app.mcontrol.viewParameters()
                return True

    # ----------------------------------------------------------------------
    def spindleControl(self, event=None):
        if self._gUpdate:
            return
        # Avoid sending commands before unlocking
        if CNC.vars["state"] in (Sender.CONNECTED, Sender.NOT_CONNECTED):
            return
        if self.spindle.get():
            self.sendGCode("M3 S%d" % (self.spindleSpeed.get()))
        else:
            self.sendGCode("M5")

    # ----------------------------------------------------------------------
    def coolantMist(self, event=None):
        if self._gUpdate:
            return
        # Avoid sending commands before unlocking
        if CNC.vars["state"] in (Sender.CONNECTED, Sender.NOT_CONNECTED):
            self.mist.set(False)
            return
        self.coolant.set(False)
        self.mist.set(True)
        self.sendGCode("M7")

    # ----------------------------------------------------------------------
    def coolantFlood(self, event=None):
        if self._gUpdate:
            return
        # Avoid sending commands before unlocking
        if CNC.vars["state"] in (Sender.CONNECTED, Sender.NOT_CONNECTED):
            self.flood.set(False)
            return
        self.coolant.set(False)
        self.flood.set(True)
        self.sendGCode("M8")

    # ----------------------------------------------------------------------
    def coolantOff(self, event=None):
        if self._gUpdate:
            return
        # Avoid sending commands before unlocking
        if CNC.vars["state"] in (Sender.CONNECTED, Sender.NOT_CONNECTED):
            self.coolant.set(False)
            return
        self.flood.set(False)
        self.mist.set(False)
        self.coolant.set(True)
        self.sendGCode("M9")

    # ----------------------------------------------------------------------
    def updateG(self):
        global wcsvar
        self._gUpdate = True

        try:
            wcsvar.set(WCS.index(CNC.vars["WCS"]))
            self.feedRate.set(str(CNC.vars["feed"]))
            self.feedMode.set(FEED_MODE[CNC.vars["feedmode"]])
            self.spindle.set(CNC.vars["spindle"] == "M3")
            self.spindleSpeed.set(int(CNC.vars["rpm"]))
            self.toolEntry.set(CNC.vars["tool"])
            self.units.set(UNITS[CNC.vars["units"]])
            self.distance.set(DISTANCE_MODE[CNC.vars["distance"]])
            self.plane.set(PLANE[CNC.vars["plane"]])
            # TLO no longer used - managed via WCS offsets (G10 L20) instead
            self.g92.config(text=str(CNC.vars["G92"]))
        except KeyError:
            pass

        self._gUpdate = False

    # ----------------------------------------------------------------------
    def updateFeed(self):
        if self.feedRate.cget("state") == DISABLED:
            self.feedRate.config(state=NORMAL)
            self.feedRate.delete(0, END)
            self.feedRate.insert(0, CNC.vars["curfeed"])
            self.feedRate.config(state=DISABLED)

    # ----------------------------------------------------------------------
    def wcsChange(self):
        global wcsvar
        self.sendGCode(WCS[wcsvar.get()])
        self.app.mcontrol.viewState()


# =============================================================================
# Control Page
# =============================================================================
class ControlPage(CNCRibbon.Page):
    __doc__ = _("CNC communication and control")
    _name_ = N_("Control")
    _icon_ = "control"

    # ----------------------------------------------------------------------
    # Add a widget in the widgets list to enable disable during the run
    # ----------------------------------------------------------------------
    def register(self):
        global wcsvar
        wcsvar = IntVar()
        wcsvar.set(0)

        self._register(
            (ConnectionGroup, UserGroup, RunGroup),
            (DROFrame, abcDROFrame, ControlFrame, abcControlFrame, StateFrame),
        )
        
    def persist_tool(self, tool=None):
        """Persist current tool number to configuration"""
        if tool is None:
            tool = CNC.vars.get("tool", 0)
        try:
            # Update in-memory configuration and write to disk immediately
            # using a safe saver that does not remove PhotoImage objects.
            Utils.setStr("ATC", "current_tool", str(tool))
            # Immediate safe on-disk save (doesn't call delIcons)
            saved = False
            try:
                saved = Utils.saveConfiguration_safe()
            except Exception:
                saved = False

            # If we failed to save to disk, treat this as a fatal error for
            # callers (they may abort ATC). Raise so higher-level helpers
            # can detect and handle the fatal condition.
            if not saved:
                raise RuntimeError("Failed to save configuration to disk")
        except Exception:
            # Non-fatal: just continue
            pass