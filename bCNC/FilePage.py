# $Id$
#
# Author: vvlachoudis@gmail.com
# Date: 18-Jun-2015

import os
import sys
from tkinter import (
    YES,
    W,
    E,
    EW,
    NSEW,
    BOTH,
    LEFT,
    TOP,
    RIGHT,
    BOTTOM,
    X,
    END,
    Frame,
    BooleanVar,
    Checkbutton,
    Label,
    Menu,
)
import CNCRibbon
import Ribbon
import tkExtra
import Utils
import bFileDialog
from tkinter import messagebox

from Helpers import N_

__author__ = "Vasilis Vlachoudis"
__email__ = "vvlachoudis@gmail.com"

try:
    from serial.tools.list_ports import comports
except Exception:
    print("Using fallback Utils.comports()!")
    from Utils import comports

BAUDS = [2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400]

# =============================================================================
# Recent Menu button
# =============================================================================


class _RecentMenuButton(Ribbon.MenuButton):
    # ----------------------------------------------------------------------
    def createMenu(self):
        menu = Menu(self, tearoff=0, activebackground=Ribbon._ACTIVE_COLOR)
        for i in range(Utils._maxRecent):
            filename = Utils.getRecent(i)
            if filename is None:
                break
            path = os.path.dirname(filename)
            fn = os.path.basename(filename)
            menu.add_command(
                label="%d %s" % (i + 1, fn),
                compound=LEFT,
                image=Utils.icons["new"],
                accelerator=path,  # Show as accelerator in order to be aligned
                command=lambda s=self, i=i: s.event_generate(
                    "<<Recent%d>>" % (i)),
            )
        if i == 0:  # no entry
            self.event_generate("<<Open>>")
            return None
        return menu


# =============================================================================
# File Group
# =============================================================================
class FileGroup(CNCRibbon.ButtonGroup):
    def __init__(self, master, app):
        CNCRibbon.ButtonGroup.__init__(self, master, N_("File"), app)
        self.grid3rows()

        # ---
        col, row = 0, 0
        b = Ribbon.LabelButton(
            self.frame,
            self,
            "<<New>>",
            image=Utils.icons["new32"],
            text=_("New"),
            compound=TOP,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, rowspan=3, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("New gcode/dxf file"))
        self.addWidget(b)

        # ---
        col, row = 1, 0
        b = Ribbon.LabelButton(
            self.frame,
            self,
            "<<Open>>",
            image=Utils.icons["open32"],
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, rowspan=2, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Open existing gcode/dxf file [Ctrl-O]"))
        self.addWidget(b)

        col, row = 1, 2
        b = _RecentMenuButton(
            self.frame,
            None,
            text=_("Open"),
            image=Utils.icons["triangle_down"],
            compound=RIGHT,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Open recent file"))
        self.addWidget(b)

        # ---
        col, row = 2, 0
        b = Ribbon.LabelButton(
            self.frame,
            self,
            "<<Import>>",
            image=Utils.icons["import32"],
            text=_("Import"),
            compound=TOP,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, rowspan=3, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Import gcode/dxf file"))
        self.addWidget(b)

        # ---
        col, row = 3, 0
        b = Ribbon.LabelButton(
            self.frame,
            self,
            "<<Save>>",
            image=Utils.icons["save32"],
            command=app.save,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, rowspan=2, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Save gcode/dxf file [Ctrl-S]"))
        self.addWidget(b)

        col, row = 3, 2
        b = Ribbon.LabelButton(
            self.frame,
            self,
            "<<SaveAs>>",
            text=_("Save"),
            image=Utils.icons["triangle_down"],
            compound=RIGHT,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Save gcode/dxf AS"))
        self.addWidget(b)


# =============================================================================
# Options Group
# =============================================================================
class OptionsGroup(CNCRibbon.ButtonGroup):
    def __init__(self, master, app):
        CNCRibbon.ButtonGroup.__init__(self, master, N_("Options"), app)
        self.grid3rows()

        # ===
        col, row = 1, 0
        b = Ribbon.LabelButton(
            self.frame,
            text=_("Report"),
            image=Utils.icons["debug"],
            compound=LEFT,
            command=Utils.ReportDialog.sendErrorReport,
            anchor=W,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, padx=0, pady=0, sticky=EW)
        tkExtra.Balloon.set(b, _("Send Error Report"))

        # ---
        col, row = 1, 1
        b = Ribbon.LabelButton(
            self.frame,
            text=_("Updates"),
            image=Utils.icons["global"],
            compound=LEFT,
            command=self.app.checkUpdates,
            anchor=W,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, padx=0, pady=0, sticky=EW)
        tkExtra.Balloon.set(b, _("Check Updates"))

        col, row = 1, 2
        b = Ribbon.LabelButton(
            self.frame,
            text=_("About"),
            image=Utils.icons["about"],
            compound=LEFT,
            command=self.app.about,
            anchor=W,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, padx=0, pady=0, sticky=EW)
        tkExtra.Balloon.set(b, _("About the program"))


# =============================================================================
# Pendant Group
# =============================================================================
class PendantGroup(CNCRibbon.ButtonGroup):
    def __init__(self, master, app):
        CNCRibbon.ButtonGroup.__init__(self, master, N_("Pendant"), app)
        self.grid3rows()

        col, row = 0, 0
        b = Ribbon.LabelButton(
            self.frame,
            text=_("Start"),
            image=Utils.icons["start_pendant"],
            compound=LEFT,
            anchor=W,
            command=app.startPendant,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Start pendant"))

        row += 1
        b = Ribbon.LabelButton(
            self.frame,
            text=_("Stop"),
            image=Utils.icons["stop_pendant"],
            compound=LEFT,
            anchor=W,
            command=app.stopPendant,
            background=Ribbon._BACKGROUND,
        )
        b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(b, _("Stop pendant"))


# =============================================================================
# Close Group
# =============================================================================
class CloseGroup(CNCRibbon.ButtonGroup):
    def __init__(self, master, app):
        CNCRibbon.ButtonGroup.__init__(self, master, N_("Close"), app)

        # ---
        b = Ribbon.LabelButton(
            self.frame,
            text=_("Exit"),
            image=Utils.icons["exit32"],
            compound=TOP,
            command=app.quit,
            anchor=W,
            background=Ribbon._BACKGROUND,
        )
        b.pack(fill=BOTH, expand=YES)
        tkExtra.Balloon.set(b, _("Close program [Ctrl-Q]"))


# =============================================================================
# Directory Jobs (table + controls)
# =============================================================================
class DirJobsFrame(CNCRibbon.PageLabelFrame):
    def __init__(self, master, app):
        CNCRibbon.PageLabelFrame.__init__(self, master, "DirJobs", _("Directory jobs"), app)

        self.current_dir = None
        # Controls row
        ctrl = Frame(self)
        ctrl.pack(side=TOP, fill=X)

        self.load_btn = Ribbon.LabelButton(
            ctrl,
            text=_("Load dir"),
            image=Utils.icons.get("open32"),
            compound=LEFT,
            command=self.load_dir,
            background=Ribbon._BACKGROUND,
        )
        self.load_btn.pack(side=LEFT, padx=2, pady=2)
        tkExtra.Balloon.set(self.load_btn, _("Choose a directory and list .nc files"))

        self.save_btn = Ribbon.LabelButton(
            ctrl,
            text=_("Save dir"),
            image=Utils.icons.get("save32"),
            compound=LEFT,
            command=self.save_dir,
            background=Ribbon._BACKGROUND,
        )
        self.save_btn.pack(side=LEFT, padx=2, pady=2)
        tkExtra.Balloon.set(self.save_btn, _("Save filename→tool mapping to dir.conf in the selected directory"))

        # Spacer expands to push move/delete buttons to right
        spacer = Frame(ctrl)
        spacer.pack(side=LEFT, expand=YES, fill=X)

        self.up_btn = Ribbon.LabelButton(
            ctrl,
            text=_("Up"),
            image=Utils.icons.get("up"),
            compound=LEFT,
            command=self.move_up,
            background=Ribbon._BACKGROUND,
        )
        self.up_btn.pack(side=LEFT, padx=2, pady=2)
        tkExtra.Balloon.set(self.up_btn, _("Move selected row up"))

        self.down_btn = Ribbon.LabelButton(
            ctrl,
            text=_("Down"),
            image=Utils.icons.get("down"),
            compound=LEFT,
            command=self.move_down,
            background=Ribbon._BACKGROUND,
        )
        self.down_btn.pack(side=LEFT, padx=2, pady=2)
        tkExtra.Balloon.set(self.down_btn, _("Move selected row down"))

        self.del_btn = Ribbon.LabelButton(
            ctrl,
            text=_("Delete"),
            image=Utils.icons.get("clear"),
            compound=LEFT,
            command=self.delete_rows,
            background=Ribbon._BACKGROUND,
        )
        self.del_btn.pack(side=LEFT, padx=2, pady=2)
        tkExtra.Balloon.set(self.del_btn, _("Remove selected row(s) from the table"))

        # Status label for selected directory and file count
        self.status_label = Label(self, text="", anchor=W)
        self.status_label.pack(side=TOP, fill=X, padx=2)

        # Table
        self.table = tkExtra.MultiListbox(
            self,
            ((_("Filename"), 40, None), (_("Tool"), 8, None)),
            height=12,
            header=True,
            stretch="last",
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
        )
        self.table.sortAssist = None  # disable sorting to keep manual order
        self.table.pack(side=TOP, expand=YES, fill=BOTH, padx=2, pady=2)

        # Edit tool on click/double-click in second column
        self.table.listbox(1).bind("<Double-1>", self.edit_tool)
        self.table.listbox(1).bind("<Return>", self.edit_tool)
        self.table.bindList("<Key-Delete>", lambda e: self.delete_rows())

    # ------------------------------------------------------------------
    def load_dir(self):
        # Choose directory, default to last used or File dir
        lastdir = Utils.getUtf("DirJobs", "lastdir", None)
        initial = lastdir or Utils.getUtf("File", "dir")
        path = bFileDialog.askdirectory(master=self, initialdir=initial)
        if not path:
            return
        try:
            path = os.path.abspath(path)
        except Exception:
            pass

        self.current_dir = path
        # Ensure config section exists before writing
        try:
            Utils.addSection("DirJobs")
        except Exception:
            pass
        Utils.setStr("DirJobs", "lastdir", self.current_dir)

        # Load existing config mapping if present
        conf = self._read_dir_conf(self.current_dir)

        # List accepted gcode files (case-insensitive), sorted alphabetically
        try:
            exts = {".nc", ".ngc", ".gcode", ".tap", ".cnc"}
            all_files = [
                f for f in os.listdir(self.current_dir)
                if os.path.isfile(os.path.join(self.current_dir, f))
            ]
            files = [
                f for f in all_files
                if os.path.splitext(f)[1].lower() in exts
            ]
            # Fallback: try simple endswith check if splitext found none
            if not files and all_files:
                alt = [f for f in all_files if any(f.lower().endswith(x) for x in exts)]
                if alt:
                    files = alt
            # Debug print to console to help diagnose filter issues
            try:
                print(f"[DirJobs] Scanned folder: {self.current_dir}")
                print(f"[DirJobs] Total files: {len(all_files)}, matched: {len(files)}")
                if all_files and not files:
                    print("[DirJobs] Sample file extensions:", [os.path.splitext(f)[1] for f in all_files[:10]])
            except Exception:
                pass
        except OSError as e:
            messagebox.showerror(_("Error"), str(e), parent=self)
            return

        files.sort(key=lambda s: s.lower())

        # Populate table
        self.table.delete(0, END)
        for fn in files:
            tool = conf.get(fn, "")
            self.table.insert(END, (fn, str(tool) if tool != "" else ""))
        # Update status label (matched/total)
        try:
            self.status_label.config(text=f"{self.current_dir}  (files: {len(files)}/{len(all_files)})")
        except Exception:
            pass
        if not files:
            try:
                messagebox.showinfo(_("No files"), _("No supported gcode files found in folder"), parent=self)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def save_dir(self):
        if not self.current_dir:
            messagebox.showwarning(_("No directory"), _("Load a directory first"), parent=self)
            return
        mapping = {}
        for i in range(self.table.size()):
            row = self.table.get(i)
            try:
                name = row[0]
                tool_str = row[1]
            except Exception:
                continue
            tool_str = (tool_str or "").strip()
            if tool_str == "":
                continue
            try:
                tool = int(tool_str)
            except Exception:
                # Skip non-integer entries
                continue
            mapping[name] = tool

        try:
            self._write_dir_conf(self.current_dir, mapping)
        except Exception as e:
            messagebox.showerror(_("Error"), str(e), parent=self)
            return
        messagebox.showinfo(_("Saved"), _("Saved dir.conf"), parent=self)

    # ------------------------------------------------------------------
    def edit_tool(self, event=None):
        # Edit active row tool cell as integer
        try:
            tkExtra.InPlaceInteger(self.table.listbox(1))
        except Exception:
            pass

    # ------------------------------------------------------------------
    def move_up(self):
        try:
            self.table.moveUp()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def move_down(self):
        try:
            self.table.moveDown()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def delete_rows(self):
        sel = list(map(int, self.table.curselection()))
        if not sel:
            return
        sel.sort(reverse=True)
        for i in sel:
            try:
                self.table.delete(i)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _conf_path(self, directory):
        return os.path.join(directory, "dir.conf")

    # ------------------------------------------------------------------
    def _read_dir_conf(self, directory):
        mapping = {}
        cfg = self._conf_path(directory)
        if not os.path.isfile(cfg):
            return mapping
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    # Expect format: filename,tool
                    parts = [p.strip() for p in s.split(",", 1)]
                    if len(parts) != 2:
                        continue
                    fn, tool_s = parts
                    try:
                        mapping[fn] = int(tool_s)
                    except Exception:
                        # ignore invalid entries
                        pass
        except Exception:
            # ignore read errors; start fresh
            return {}
        return mapping

    # ------------------------------------------------------------------
    def _write_dir_conf(self, directory, mapping):
        cfg = self._conf_path(directory)
        lines = [
            "# bCNC directory tool mapping\n",
            "# filename,tool_number\n",
        ]
        for fn, tool in mapping.items():
            lines.append(f"{fn},{int(tool)}\n")
        with open(cfg, "w", encoding="utf-8") as f:
            f.writelines(lines)


# =============================================================================
# Serial Frame
# =============================================================================
class SerialFrame(CNCRibbon.PageLabelFrame):
    def __init__(self, master, app):
        CNCRibbon.PageLabelFrame.__init__(
            self, master, "Serial", _("Serial"), app)
        self.autostart = BooleanVar()

        # ---
        col, row = 0, 0
        b = Label(self, text=_("Port:"))
        b.grid(row=row, column=col, sticky=E)
        self.addWidget(b)

        self.portCombo = tkExtra.Combobox(
            self,
            False,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            width=16,
            command=self.comportClean,
        )
        self.portCombo.grid(row=row, column=col + 1, sticky=EW)
        tkExtra.Balloon.set(
            self.portCombo, _("Select (or manual enter) port to connect")
        )
        self.portCombo.set(Utils.getStr("Connection", "port"))
        self.addWidget(self.portCombo)

        self.comportRefresh()

        # ---
        row += 1
        b = Label(self, text=_("Baud:"))
        b.grid(row=row, column=col, sticky=E)

        self.baudCombo = tkExtra.Combobox(
            self, True, background=tkExtra.GLOBAL_CONTROL_BACKGROUND
        )
        self.baudCombo.grid(row=row, column=col + 1, sticky=EW)
        tkExtra.Balloon.set(self.baudCombo, _("Select connection baud rate"))
        self.baudCombo.fill(BAUDS)
        self.baudCombo.set(Utils.getStr("Connection", "baud", "115200"))
        self.addWidget(self.baudCombo)

        # ---
        row += 1
        b = Label(self, text=_("Controller:"))
        b.grid(row=row, column=col, sticky=E)

        self.ctrlCombo = tkExtra.Combobox(
            self,
            True,
            background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            command=self.ctrlChange,
        )
        self.ctrlCombo.grid(row=row, column=col + 1, sticky=EW)
        tkExtra.Balloon.set(self.ctrlCombo, _("Select controller board"))
        self.ctrlCombo.fill(self.app.controllerList())
        self.ctrlCombo.set(app.controller)
        self.addWidget(self.ctrlCombo)

        # ---
        row += 1
        b = Checkbutton(self, text=_("Connect on startup"),
                        variable=self.autostart)
        b.grid(row=row, column=col, columnspan=2, sticky=W)
        tkExtra.Balloon.set(
            b, _("Connect to serial on startup of the program"))
        self.autostart.set(Utils.getBool("Connection", "openserial"))
        self.addWidget(b)

        # ---
        col += 2
        self.comrefBtn = Ribbon.LabelButton(
            self,
            image=Utils.icons["refresh"],
            text=_("Refresh"),
            compound=TOP,
            command=lambda s=self: s.comportRefresh(True),
            background=Ribbon._BACKGROUND,
        )
        self.comrefBtn.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
        tkExtra.Balloon.set(self.comrefBtn, _("Refresh list of serial ports"))

        # ---
        row = 0

        self.connectBtn = Ribbon.LabelButton(
            self,
            image=Utils.icons["serial48"],
            text=_("Open"),
            compound=TOP,
            command=lambda s=self: s.event_generate("<<Connect>>"),
            background=Ribbon._BACKGROUND,
        )
        self.connectBtn.grid(
            row=row, column=col, rowspan=3, padx=0, pady=0, sticky=NSEW
        )
        tkExtra.Balloon.set(self.connectBtn, _("Open/Close serial port"))
        self.grid_columnconfigure(1, weight=1)

    # -----------------------------------------------------------------------
    def ctrlChange(self):
        self.app.controllerSet(self.ctrlCombo.get())

    # -----------------------------------------------------------------------
    def comportClean(self, event=None):
        clean = self.portCombo.get().split("\t")[0]
        if self.portCombo.get() != clean:
            print("comport fix")
            self.portCombo.set(clean)

    # -----------------------------------------------------------------------
    def comportsGet(self):
        try:
            return comports(include_links=True)
        except TypeError:
            print("Using old style comports()!")
            return comports()

    def comportRefresh(self, dbg=False):
        # Detect devices
        hwgrep = []
        for i in self.comportsGet():
            if dbg:
                # Print list to console if requested
                comport = ""
                for j in i:
                    comport += j + "\t"
                print(comport)
            for hw in i[2].split(" "):
                hwgrep += ["hwgrep://" + hw + "\t" + i[1]]

        # Populate combobox
        devices = sorted(x[0] + "\t" + x[1] for x in self.comportsGet())
        devices += [""]
        devices += sorted(set(hwgrep))
        devices += [""]
        # Pyserial raw spy currently broken in python3
        # TODO: search for python3 replacement for raw spy
        if sys.version_info[0] != 3:
            devices += sorted(
                "spy://" + x[0] + "?raw&color" + "\t(Debug) " + x[1]
                for x in self.comportsGet()
            )
        else:
            devices += sorted(
                "spy://" + x[0] + "?color" + "\t(Debug) " + x[1]
                for x in self.comportsGet()
            )
        devices += ["", "socket://localhost:23", "rfc2217://localhost:2217"]

        # Clean neighbour duplicates
        devices_clean = []
        devprev = ""
        for i in devices:
            if i.split("\t")[0] != devprev:
                devices_clean += [i]
            devprev = i.split("\t")[0]

        self.portCombo.fill(devices_clean)

    # -----------------------------------------------------------------------
    def saveConfig(self):
        # Connection
        Utils.setStr("Connection", "controller", self.app.controller)
        Utils.setStr("Connection", "port", self.portCombo.get().split("\t")[0])
        Utils.setStr("Connection", "baud", self.baudCombo.get())
        Utils.setBool("Connection", "openserial", self.autostart.get())


# =============================================================================
# File Page
# =============================================================================
class FilePage(CNCRibbon.Page):
    __doc__ = _("File I/O and configuration")
    _name_ = N_("File")
    _icon_ = "new"

    # ----------------------------------------------------------------------
    # Add a widget in the widgets list to enable disable during the run
    # ----------------------------------------------------------------------
    def register(self):
        # Register groups and frames (creates instances in global dictionaries)
        self._register(
            (FileGroup, PendantGroup, OptionsGroup, CloseGroup), (SerialFrame, DirJobsFrame)
        )
        # Explicitly add frames so Ribbon.changePage packs them
        # (Serial first, then directory jobs below)
        try:
            self.addPageFrame("Serial", side=TOP, fill=BOTH)
        except Exception:
            pass
        try:
            self.addPageFrame("DirJobs", side=TOP, fill=BOTH)
        except Exception:
            pass
