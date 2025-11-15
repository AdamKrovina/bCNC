# $Id$
#
# Author: vvlachoudis@gmail.com
# Date: 18-Jun-2015

import os
import sys
import time

from typing import Optional
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
    NORMAL,
    DISABLED,
)
import CNCRibbon
import Ribbon
import tkExtra
import Utils
import bFileDialog
from tkinter import messagebox

from Helpers import N_
# We'll access the Control page instance directly from app.pages['Control'].
# Avoid importing ControlPage here to prevent class identity mismatches.

__author__ = "Vasilis Vlachoudis"
__email__ = "vvlachoudis@gmail.com"

# Ensure translation function _ is defined for lint/static analysis; runtime may set it earlier.
try:
    _  # type: ignore[name-defined]
except NameError:  # pragma: no cover
    try:
        from gettext import gettext as _  # fallback
    except Exception:  # pragma: no cover
        _ = lambda s: s

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
        self._dir_running = False  # prevent re-entrancy
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

        self.run_btn = Ribbon.LabelButton(
            ctrl,
            text=_("Run dir"),
            image=Utils.icons.get("start32"),
            compound=LEFT,
            command=self.run_dir,
            background=Ribbon._BACKGROUND,
        )
        self.run_btn.pack(side=LEFT, padx=2, pady=2)
        tkExtra.Balloon.set(self.run_btn, _("Sequentially run each file: set tool then load and start job"))

        # Spacer expands to push move/delete buttons to right
        spacer = Frame(ctrl)
        spacer.pack(side=LEFT, expand=YES, fill=X)

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
    def run_dir(self):
        # Validate directory
        if not self.current_dir:
            messagebox.showwarning(_("No directory"), _("Load a directory first"), parent=self)
            return
        # Prevent re-entrancy
        if getattr(self, "_dir_running", False):
            messagebox.showwarning(_("Busy"), _("Directory run already in progress"), parent=self)
            return
        # Prevent starting while a run is in progress
        if getattr(self.app, "running", False):
            messagebox.showwarning(_("Busy"), _("Controller already running"), parent=self)
            return
        jobs = []
        for i in range(self.table.size()):
            try:
                fn, tool_str = self.table.get(i)
            except Exception:
                continue
            tool_str = (tool_str or "").strip()
            if tool_str == "":
                messagebox.showerror(_("Tool missing"), _("Row {} has no tool number").format(i + 1), parent=self)
                return
            try:
                tool = int(tool_str)
            except Exception:
                messagebox.showerror(_("Invalid tool"), _("Row {} has invalid tool number: {}").format(i + 1, tool_str), parent=self)
                return
            jobs.append((fn, tool))
        if not jobs:
            messagebox.showinfo(_("No jobs"), _("No rows to run"), parent=self)
            return
        self._dir_run_jobs = jobs
        self._dir_running = True
        self.run_btn.config(state=DISABLED)
        try:
            print(f"[DirJobs] Starting directory run with {len(jobs)} jobs")
        except Exception:
            pass
        self._run_next_job()

    # ------------------------------------------------------------------
    def _run_next_job(self):
        if not getattr(self, "_dir_run_jobs", None):
            self.run_btn.config(state=NORMAL)
            self._dir_running = False
            messagebox.showinfo(_("Done"), _("Directory run completed"), parent=self)
            try:
                print("[DirJobs] All jobs completed")
            except Exception:
                pass
            return
        fn, tool = self._dir_run_jobs.pop(0)
        fullpath = os.path.join(self.current_dir, fn)
        if not os.path.isfile(fullpath):
            messagebox.showerror(_("Missing file"), _("File not found: {}\nAborting run.").format(fullpath), parent=self)
            self._dir_run_jobs = []
            self.run_btn.config(state=NORMAL)
            self._dir_running = False
            return
        control_target = self._locate_control_tool_frame()
        try:
            page_info = [(name, type(p).__name__, hasattr(p, 'setTool')) for name, p in getattr(self.app, 'pages', {}).items()]
            print(f"[DirJobs] Page inventory: {page_info}")
        except Exception:
            pass
        if not control_target:
            try:
                print("[DirJobs] ControlFrame unavailable. Existing pages:", list(self.app.pages.keys()))
            except Exception:
                pass
            messagebox.showerror(_("ATC"), _("Control page tool change unavailable"), parent=self)
            self._dir_run_jobs = []
            self.run_btn.config(state=NORMAL)
            self._dir_running = False
            return
        try:
            ok = control_target.setTool(new_tool=tool)
        except Exception as e:
            messagebox.showerror(_("ATC"), _("Tool change failed: {}\nAborting.").format(e), parent=self)
            self._dir_run_jobs = []
            self.run_btn.config(state=NORMAL)
            self._dir_running = False
            return
        if not ok:
            messagebox.showerror(_("ATC"), _("Tool change failed or aborted. Stopping."), parent=self)
            self._dir_run_jobs = []
            self.run_btn.config(state=NORMAL)
            self._dir_running = False
            return
        # Small recovery pause after tool change/probe before loading next file
        try:
            print("[DirJobs] Post-ATC pause 1.0s before loading next file")
        except Exception:
            pass
        t_atc = time.time()
        while time.time() - t_atc < 1.0:
            try:
                self.app.update()
            except Exception:
                pass
            time.sleep(0.05)
        try:
            print(f"[DirJobs] Job start: tool {tool} file {fn}")
        except Exception:
            pass
        # Run file with synchronous wait + post-run pause
        if not self._run_file_and_wait(fullpath, pause_after=7.0):
            self._dir_run_jobs = []
            self.run_btn.config(state=NORMAL)
            self._dir_running = False
            return
        # Schedule next job after a tiny idle tick to avoid recursion depth
        self.after(10, self._run_next_job)

    # ------------------------------------------------------------------
    def _wait_job_complete(self):
        # Deprecated: synchronous _run_file_and_wait handles waiting & pause
        pass

    # ------------------------------------------------------------------
    def _locate_control_tool_frame(self) -> Optional[object]:
        """Return the frame (not the page) that implements setTool.
        ControlPage itself does not define setTool; the method lives on ControlFrame.
        """
        pages = getattr(self.app, 'pages', {})
        ctrl_page = pages.get('Control')
        if ctrl_page is not None:
            # ctrl_page.frames is list of (frame, args)
            for frame, _args in getattr(ctrl_page, 'frames', []):
                if hasattr(frame, 'setTool'):
                    try:
                        print(f"[DirJobs] Found setTool on frame '{getattr(frame,'name', type(frame).__name__)}' type={type(frame).__name__}")
                    except Exception:
                        pass
                    return frame
        # Global fallback: scan all page.frame tuples
        for page in pages.values():
            for frame, _args in getattr(page, 'frames', []):
                if hasattr(frame, 'setTool'):
                    try:
                        print(f"[DirJobs] Fallback found setTool on frame '{getattr(frame,'name', type(frame).__name__)}' in page '{getattr(page,'name','?')}'")
                    except Exception:
                        pass
                    return frame
        return None

    # ------------------------------------------------------------------
    def _conf_path(self, directory):
        return os.path.join(directory, "dir.conf")

    # ------------------------------------------------------------------
    def _run_file_and_wait(self, fullpath, wait_before=5.0, wait_after=360000.0, pause_after=1.0):
        """Synchronne spustí g-code súbor a aktívne čaká na dokončenie.

        Kroky:
        1. Počká (max wait_before sekúnd), kým predchádzajúci beh skončí.
        2. Načíta súbor (self.app.load).
        3. Spustí beh (self.app.run) – ten pripraví frontu a nastaví _runLines.
        4. Polling slučka s self.app.update() kým self.app.running je True alebo nevyprší wait_after.
        5. Overí, či bol počet vykonaných riadkov (_last_run_completed) >= očakávané (_runLines).
        6. Vloží pauzu pause_after sekúnd na zotavenie kontroléra.

        Vráti True na úspech, False na zlyhanie (už s UI hláškou).
        """
        try:
            print(f"[DirJobs] Preparing to run file: {fullpath}")
        except Exception:
            pass
        # 1. počkaj na predchádzajúci beh
        t0 = time.time()
        while time.time() - t0 < wait_before and getattr(self.app, 'running', False):
            try:
                self.app.update()
            except Exception:
                pass
            time.sleep(0.05)
        if getattr(self.app, 'running', False):
            messagebox.showerror(_("Run error"), _("Previous run still active; aborting."), parent=self)
            return False
        # 2. load
        try:
            self.app.load(fullpath)
        except Exception as e:
            messagebox.showerror(_("Load error"), _("Failed to load {}: {}\nAborting.").format(fullpath, e), parent=self)
            return False
        # 3. run
        try:
            self.app.run()
        except Exception as e:
            messagebox.showerror(_("Run error"), _("Failed to start run: {}\nAborting.").format(e), parent=self)
            return False
        expected = getattr(self.app, '_runLines', None)
        try:
            print(f"[DirJobs] Active wait: expected_run_lines={expected}")
        except Exception:
            pass
        # 4. čakaj na dokončenie alebo timeout
        t1 = time.time()
        while time.time() - t1 < wait_after and getattr(self.app, 'running', False):
            try:
                self.app.update()
            except Exception:
                pass
            time.sleep(0.05)
        if getattr(self.app, 'running', False):
            messagebox.showerror(_("Run timeout"), _("File run timeout"), parent=self)
            return False
        # 5. over počet riadkov
        gcount = getattr(self.app, '_last_run_completed', None)
        try:
            print(f"[DirJobs] Run finished (initial): gcount={gcount} expected={expected}")
        except Exception:
            pass
        # Stabilization loop: allow gcount to settle/increase for up to 1s (reset timer on change)
        stab_deadline = time.time() + 1.0
        last = gcount
        while time.time() < stab_deadline:
            try:
                self.app.update()
            except Exception:
                pass
            time.sleep(0.05)
            current = getattr(self.app, '_last_run_completed', None)
            if current != last:
                last = current
                stab_deadline = time.time() + 0.5  # extend a bit after each change
            # Early break if we already reached expected
            if expected and current is not None and current >= expected:
                break
        gcount = last
        try:
            print(f"[DirJobs] Run finished (stabilized): gcount={gcount} expected={expected}")
        except Exception:
            pass
        # Strict validation with single zero-line retry + finalization wait for late increments
        if expected is not None and gcount is not None and gcount != expected:
            if gcount == 0 and expected > 0 and not getattr(self, '_retried_once', False):
                # Zero-line premature end: first observe for late activity before retrying
                try:
                    print(f"[DirJobs] Detected zero-line premature end (expected={expected}). Observing 2s for late activity...")
                except Exception:
                    pass
                t_obs = time.time()
                late_progress = False
                while time.time() - t_obs < 2.0:
                    try:
                        self.app.update()
                    except Exception:
                        pass
                    time.sleep(0.05)
                    if getattr(self.app, 'running', False):
                        late_progress = True
                        break
                    cur = getattr(self.app, '_last_run_completed', 0) or 0
                    if cur > 0:
                        late_progress = True
                        break
                if late_progress:
                    try:
                        print("[DirJobs] Late activity detected; waiting for first run to finalize (skip retry)")
                    except Exception:
                        pass
                    # Wait for completion of the original run
                    t_wait = time.time()
                    while time.time() - t_wait < wait_after and getattr(self.app, 'running', False):
                        try:
                            self.app.update()
                        except Exception:
                            pass
                        time.sleep(0.05)
                    # Short finalization window to capture last gcount
                    t_fin = time.time()
                    while time.time() - t_fin < 1.0:
                        try:
                            self.app.update()
                        except Exception:
                            pass
                        time.sleep(0.05)
                    gcount = getattr(self.app, '_last_run_completed', None)
                    try:
                        print(f"[DirJobs] First run finalized: gcount={gcount} expected={expected}")
                    except Exception:
                        pass
                else:
                    # Proceed with a single retry after cooldown
                    self._retried_once = True
                    try:
                        print(f"[DirJobs] No late activity; retrying run once after 2s cooldown…")
                    except Exception:
                        pass
                    t_retry = time.time()
                    while time.time() - t_retry < 2.0:  # extended cooldown
                        try:
                            self.app.update()
                        except Exception:
                            pass
                        time.sleep(0.05)
                    try:
                        self.app.emptyQueue()
                    except Exception:
                        pass
                    try:
                        self.app.run()
                    except Exception as e:
                        messagebox.showerror(_("Run error"), _("Retry failed to start: {}\nAborting.").format(e), parent=self)
                        return False
                    expected = getattr(self.app, '_runLines', expected)
                    try:
                        print(f"[DirJobs] Retry active wait: expected_run_lines={expected}")
                    except Exception:
                        pass
                    t1b = time.time()
                    while time.time() - t1b < wait_after and getattr(self.app, 'running', False):
                        try:
                            self.app.update()
                        except Exception:
                            pass
                        time.sleep(0.05)
                    gcount = getattr(self.app, '_last_run_completed', None)
                    try:
                        print(f"[DirJobs] Retry finished: gcount={gcount} expected={expected}")
                    except Exception:
                        pass
                    self._retried_once = False
            # Finalization wait for partial completion (allow late increments)
            if gcount is not None and expected is not None and 0 < gcount < expected:
                try:
                    print(f"[DirJobs] Finalization wait: current={gcount} expected={expected} (up to 2s)")
                except Exception:
                    pass
                fin_deadline = time.time() + 2.0
                prev = gcount
                while time.time() < fin_deadline and prev < expected:
                    try:
                        self.app.update()
                    except Exception:
                        pass
                    time.sleep(0.05)
                    cur = getattr(self.app, '_last_run_completed', prev)
                    if cur != prev:
                        prev = cur
                        try:
                            print(f"[DirJobs] Finalization progress: {prev}/{expected}")
                        except Exception:
                            pass
                gcount = prev
                try:
                    print(f"[DirJobs] Finalization done: gcount={gcount} expected={expected}")
                except Exception:
                    pass
            if expected is not None and gcount is not None and gcount != expected:
                messagebox.showerror(_("Run error"), _("Run ended prematurely ({} != {})").format(gcount, expected), parent=self)
                return False
        # 6. post-run pauza
        try:
            print(f"[DirJobs] Post-run pause {pause_after}s for controller recovery")
        except Exception:
            pass
        t2 = time.time()
        while time.time() - t2 < pause_after:
            try:
                self.app.update()
            except Exception:
                pass
            time.sleep(0.05)
        return True

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
