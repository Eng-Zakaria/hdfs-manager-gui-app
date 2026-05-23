#!/usr/bin/env python3
"""
HDFS & Linux File Manager
Dual-pane GUI for HDFS and local Linux filesystems.
Python 3.7 compatible — no emojis, thread-safe tkinter updates.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import subprocess
import threading
import os
import shutil
from datetime import datetime


# ── Colour palette ─────────────────────────────────────────────────────────────
BG_DARK   = "#0f1117"
BG_PANEL  = "#1a1d27"
BG_CARD   = "#21253a"
BG_HOVER  = "#2a2f4a"
ACCENT    = "#4f8ef7"
ACCENT2   = "#f7934f"
SUCCESS   = "#4fcf70"
DANGER    = "#f74f4f"
WARNING   = "#f7cf4f"
TEXT_PRI  = "#e8eaf6"
TEXT_SEC  = "#8892b0"
TEXT_DIM  = "#4a5568"
BORDER    = "#2d3152"

# ── Fonts (bigger, easier to read) ────────────────────────────────────────────
F_MONO_SM  = ("Courier New", 10)
F_MONO_MD  = ("Courier New", 11)
F_MONO_LG  = ("Courier New", 13, "bold")
F_MONO_XL  = ("Courier New", 15, "bold")
F_MONO_BTN = ("Courier New", 10, "bold")
F_TREE     = ("Courier New", 11)
F_LOG      = ("Courier New", 10)

# ── Prefixes stored in tree text ──────────────────────────────────────────────
DIR_PFX  = "DIR "   # 4 chars, no special chars that confuse lstrip
FILE_PFX = "FILE "  # 5 chars


def strip_prefix(text):
    """Safely remove DIR /FILE  prefix — never strips real filename chars."""
    if text.startswith(DIR_PFX):
        return text[len(DIR_PFX):]
    if text.startswith(FILE_PFX):
        return text[len(FILE_PFX):]
    return text


def run_cmd(cmd, shell=True, timeout=60):
    try:
        r = subprocess.run(cmd, shell=shell, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout)
        return (r.stdout.decode("utf-8", errors="replace"),
                r.stderr.decode("utf-8", errors="replace"),
                r.returncode)
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1


def _lighten(hex_color):
    try:
        r = min(255, int(hex_color[1:3], 16) + 30)
        g = min(255, int(hex_color[3:5], 16) + 30)
        b = min(255, int(hex_color[5:7], 16) + 30)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


# ─────────────────────────────────────────────────────────────────────────────
# Widgets
# ─────────────────────────────────────────────────────────────────────────────

class IconButton(tk.Button):
    def __init__(self, parent, text, command, color=ACCENT, width=None, **kw):
        dark_fg = (WARNING, SUCCESS, ACCENT)
        fg = BG_DARK if color in dark_fg else TEXT_PRI
        cfg = dict(text=text, command=command, bg=color, fg=fg,
                   activebackground=_lighten(color), activeforeground=fg,
                   relief=tk.FLAT, bd=0, cursor="hand2",
                   font=F_MONO_BTN, padx=10, pady=6)
        if width:
            cfg["width"] = width
        cfg.update(kw)
        super().__init__(parent, **cfg)
        self._color = color
        self.bind("<Enter>", lambda e: self.config(bg=_lighten(color)))
        self.bind("<Leave>", lambda e: self.config(bg=color))


class LogPanel(tk.Frame):
    """Thread-safe scrollable log. Use log_safe()/clear_safe() from threads."""
    def __init__(self, parent, height=10, **kw):
        super().__init__(parent, bg=BG_PANEL, **kw)
        self.text = tk.Text(self, bg="#090b14", fg="#a0f0a0",
                            font=F_LOG, height=height,
                            insertbackground=ACCENT, relief=tk.FLAT,
                            wrap=tk.WORD, state=tk.DISABLED)
        sb = ttk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.tag_config("err",  foreground=DANGER)
        self.text.tag_config("ok",   foreground=SUCCESS)
        self.text.tag_config("info", foreground=ACCENT)
        self.text.tag_config("warn", foreground=WARNING)

    def log(self, msg, tag=""):
        self.text.config(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self.text.insert(tk.END, f"[{ts}] {msg}\n", tag)
        self.text.see(tk.END)
        self.text.config(state=tk.DISABLED)

    def log_safe(self, msg, tag=""):
        self.after(0, lambda m=msg, t=tag: self.log(m, t))

    def clear(self):
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.config(state=tk.DISABLED)

    def clear_safe(self):
        self.after(0, self.clear)


class StatusBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_DARK, height=30)
        self.pack_propagate(False)
        self._label = tk.Label(self, text="Ready", fg=TEXT_SEC, bg=BG_DARK, font=F_MONO_SM)
        self._label.pack(side=tk.LEFT, padx=10)
        self._time  = tk.Label(self, fg=TEXT_DIM, bg=BG_DARK, font=F_MONO_SM)
        self._time.pack(side=tk.RIGHT, padx=10)
        self._tick()

    def set(self, msg, color=TEXT_SEC):
        self._label.config(text=msg, fg=color)

    def _tick(self):
        self._time.config(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick)


# ─────────────────────────────────────────────────────────────────────────────
# Services Tab
# ─────────────────────────────────────────────────────────────────────────────

class ServicesTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_DARK)
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG_DARK)
        hdr.pack(fill=tk.X, padx=20, pady=(20, 0))
        tk.Label(hdr, text="[H]  HADOOP SERVICES", fg=ACCENT,
                 bg=BG_DARK, font=F_MONO_XL).pack(side=tk.LEFT)

        self.hdfs_status = self._status_row("HDFS (NameNode + DataNode)", row=0)
        self.yarn_status = self._status_row("YARN (ResourceManager + NodeManager)", row=1)

        btn_frame = tk.Frame(self, bg=BG_DARK)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        for i, (label, cmd, color) in enumerate([
            (">  Start HDFS",   self._start_hdfs,   SUCCESS),
            ("[] Stop HDFS",    self._stop_hdfs,    DANGER),
            ("<< Restart HDFS", self._restart_hdfs, WARNING),
            (">  Start YARN",   self._start_yarn,   SUCCESS),
            ("[] Stop YARN",    self._stop_yarn,    DANGER),
            ("<< Restart YARN", self._restart_yarn, WARNING),
            (">  Start All",    self._start_all,    ACCENT),
            ("[] Stop All",     self._stop_all,     ACCENT2),
            ("~~ Refresh",      self._refresh,      TEXT_SEC),
        ]):
            r, c = divmod(i, 3)
            IconButton(btn_frame, label, cmd, color=color, width=18).grid(
                row=r, column=c, padx=5, pady=5, sticky="ew")
        for c in range(3):
            btn_frame.columnconfigure(c, weight=1)

        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X, padx=20, pady=10)
        tk.Label(self, text="DAEMON PROCESSES  (jps)", fg=TEXT_SEC,
                 bg=BG_DARK, font=F_MONO_MD).pack(anchor=tk.W, padx=20)
        self.daemon_box = LogPanel(self, height=8)
        self.daemon_box.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        tk.Label(self, text="COMMAND OUTPUT", fg=TEXT_SEC,
                 bg=BG_DARK, font=F_MONO_MD).pack(anchor=tk.W, padx=20)
        self.log = LogPanel(self, height=10)
        self.log.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        self.after(100, self._refresh)

    def _status_row(self, label, row):
        f = tk.Frame(self, bg=BG_PANEL, pady=8, padx=14)
        f.pack(fill=tk.X, padx=20, pady=(10 if row == 0 else 2, 2))
        dot = tk.Label(f, text="*", fg=TEXT_DIM, bg=BG_PANEL, font=("Courier New", 16))
        dot.pack(side=tk.LEFT)
        tk.Label(f, text=f"  {label}", fg=TEXT_PRI, bg=BG_PANEL, font=F_MONO_MD).pack(side=tk.LEFT)
        status = tk.Label(f, text="UNKNOWN", fg=TEXT_DIM, bg=BG_PANEL, font=F_MONO_BTN)
        status.pack(side=tk.RIGHT)
        return dot, status

    def _set_status(self, pair, running):
        dot, lbl = pair
        if running:
            dot.config(fg=SUCCESS); lbl.config(text="RUNNING", fg=SUCCESS)
        else:
            dot.config(fg=DANGER);  lbl.config(text="STOPPED", fg=DANGER)

    def _run_async(self, cmd, label):
        self.log.log(f"$ {cmd}", "info")
        def worker():
            out, err, rc = run_cmd(cmd, timeout=120)
            for line in (out or "").strip().splitlines():
                self.log.log_safe(line, "ok" if rc == 0 else "err")
            for line in (err or "").strip().splitlines():
                self.log.log_safe(line, "warn")
            self.log.log_safe(f"[{label}] exit {rc}", "ok" if rc == 0 else "err")
            self.after(800, self._refresh)
        threading.Thread(target=worker, daemon=True).start()

    def _start_hdfs(self):  self._run_async("$HADOOP_HOME/sbin/start-dfs.sh",  "Start HDFS")
    def _stop_hdfs(self):   self._run_async("$HADOOP_HOME/sbin/stop-dfs.sh",   "Stop HDFS")
    def _start_yarn(self):  self._run_async("$HADOOP_HOME/sbin/start-yarn.sh", "Start YARN")
    def _stop_yarn(self):   self._run_async("$HADOOP_HOME/sbin/stop-yarn.sh",  "Stop YARN")
    def _start_all(self):   self._run_async("$HADOOP_HOME/sbin/start-all.sh",  "Start All")
    def _stop_all(self):    self._run_async("$HADOOP_HOME/sbin/stop-all.sh",   "Stop All")
    def _restart_hdfs(self): self._stop_hdfs();  self.after(4000, self._start_hdfs)
    def _restart_yarn(self): self._stop_yarn();  self.after(4000, self._start_yarn)

    def _refresh(self):
        def worker():
            out, _, _ = run_cmd("jps")
            daemons  = out.strip().splitlines() if out.strip() else ["(no Java daemons running)"]
            hdfs_up  = any(x in out for x in ["NameNode", "DataNode"])
            yarn_up  = any(x in out for x in ["ResourceManager", "NodeManager"])
            known    = {"NameNode", "DataNode", "ResourceManager", "NodeManager", "SecondaryNameNode"}
            def update():
                self.daemon_box.clear()
                for d in daemons:
                    self.daemon_box.log(d, "ok" if any(k in d for k in known) else "")
                self._set_status(self.hdfs_status, hdfs_up)
                self._set_status(self.yarn_status,  yarn_up)
            self.after(0, update)
        threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# File Pane Base
# ─────────────────────────────────────────────────────────────────────────────

class FilePaneBase(tk.Frame):
    def __init__(self, parent, title, on_selection=None, on_file_open=None, **kw):
        super().__init__(parent, bg=BG_PANEL, **kw)
        self.on_selection  = on_selection   # called on single-click select
        self.on_file_open  = on_file_open   # called on double-click of a file
        self._current_path = self._root_path()
        self._build(title)

    def _root_path(self):  return "/"
    def _home_path(self):  return "/"

    def _build(self, title):
        # Header bar: title on left, nav buttons + Refresh on right
        hdr = tk.Frame(self, bg=BG_CARD, pady=6, padx=10)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=title, fg=ACCENT, bg=BG_CARD, font=F_MONO_LG).pack(side=tk.LEFT)
        # Pack RIGHT-to-LEFT so they appear as: Up | Home | [extra] | Refresh
        IconButton(hdr, "Refresh",  self.refresh,  color=BG_HOVER).pack(side=tk.RIGHT, padx=2)
        self._build_extra_nav(hdr)   # subclass adds its extra buttons to the right side
        IconButton(hdr, "~ Home",   self._go_home, color=BG_HOVER).pack(side=tk.RIGHT, padx=2)
        IconButton(hdr, "^ Up",     self._go_up,   color=BG_HOVER).pack(side=tk.RIGHT, padx=2)

        # Path bar
        path_bar = tk.Frame(self, bg=BG_DARK, pady=4, padx=8)
        path_bar.pack(fill=tk.X)
        tk.Label(path_bar, text="PATH:", fg=TEXT_DIM, bg=BG_DARK, font=F_MONO_SM).pack(side=tk.LEFT)
        self.path_var = tk.StringVar(value=self._current_path)
        pe = tk.Entry(path_bar, textvariable=self.path_var, bg="#090b14", fg=ACCENT,
                      insertbackground=ACCENT, relief=tk.FLAT, font=F_MONO_SM, bd=4)
        pe.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        pe.bind("<Return>", lambda e: self.navigate(self.path_var.get()))
        IconButton(path_bar, "GO", lambda: self.navigate(self.path_var.get()),
                   color=ACCENT, width=4).pack(side=tk.RIGHT)

        # File tree
        tree_frame = tk.Frame(self, bg=BG_PANEL)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.configure("Dark.Treeview",
            background=BG_PANEL, foreground=TEXT_PRI,
            fieldbackground=BG_PANEL, borderwidth=0, font=F_TREE,
            rowheight=24)
        style.configure("Dark.Treeview.Heading",
            background=BG_CARD, foreground=TEXT_SEC,
            borderwidth=0, font=F_MONO_BTN)
        style.map("Dark.Treeview",
            background=[("selected", BG_HOVER)],
            foreground=[("selected", ACCENT)])

        self.tree = ttk.Treeview(tree_frame, style="Dark.Treeview",
                                 columns=("size", "date"), selectmode="extended")
        self.tree.heading("#0",   text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("date", text="Modified")
        self.tree.column("#0",   width=240, minwidth=120)
        self.tree.column("size", width=90,  anchor=tk.E)
        self.tree.column("date", width=140)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,   command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>",         self._on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Operation buttons
        ops = tk.Frame(self, bg=BG_DARK, pady=4, padx=8)
        ops.pack(fill=tk.X)
        self._build_ops(ops)

        self.after(200, self.refresh)

    def _build_extra_nav(self, parent): pass   # subclass packs onto hdr RIGHT side
    def _build_ops(self, parent):       pass

    def navigate(self, path):
        self._current_path = path.strip() or "/"
        self.path_var.set(self._current_path)
        self.refresh()

    def _go_up(self):
        p = os.path.dirname(self._current_path.rstrip("/")) or "/"
        self.navigate(p)

    def _go_home(self):
        self.navigate(self._home_path())

    def _item_name(self, text):
        """Safely strip DIR /FILE  prefix without touching the filename."""
        return strip_prefix(text)

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0])
        tag  = (item.get("tags") or [""])[0]
        name = self._item_name(item["text"])
        path = os.path.join(self._current_path, name).replace("//", "/")
        if tag == "dir":
            self.navigate(path)
        elif tag == "file" and self.on_file_open:
            self.on_file_open(path, self._is_hdfs())

    def _is_hdfs(self):
        return False   # overridden in HDFSPane

    def _on_select(self, event):
        sel = self.tree.selection()
        if self.on_selection and sel:
            item = self.tree.item(sel[0])
            name = self._item_name(item["text"])
            path = os.path.join(self._current_path, name).replace("//", "/")
            tag  = (item.get("tags") or [""])[0]
            self.on_selection(path, tag, self)

    def selected_paths(self):
        paths = []
        for iid in self.tree.selection():
            item = self.tree.item(iid)
            name = self._item_name(item["text"])
            paths.append(os.path.join(self._current_path, name).replace("//", "/"))
        return paths

    def refresh(self): pass

    @staticmethod
    def _fmt_size(b):
        for unit in ("B", "K", "M", "G", "T"):
            if b < 1024: return f"{b:.1f}{unit}"
            b /= 1024
        return f"{b:.1f}P"


# ─────────────────────────────────────────────────────────────────────────────
# Local Pane
# ─────────────────────────────────────────────────────────────────────────────

class LocalPane(FilePaneBase):
    def __init__(self, parent, **kw):
        super().__init__(parent, "[L]  LOCAL FILESYSTEM", **kw)

    def _root_path(self):  return os.path.expanduser("~")
    def _home_path(self):  return os.path.expanduser("~")
    def _is_hdfs(self):    return False

    def _build_extra_nav(self, parent):
        # parent is now the header bar; pack to RIGHT so order is: Up | Home | Root | Refresh
        IconButton(parent, "/ Root", lambda: self.navigate("/"),
                   color=BG_HOVER).pack(side=tk.RIGHT, padx=2)

    def _build_ops(self, parent):
        for label, cmd, color in [
            ("+ Dir",    self._mkdir,  ACCENT),
            ("~ Rename", self._rename, WARNING),
            ("+ Copy",   self._copy,   ACCENT2),
            ("x Move",   self._move,   ACCENT2),
            ("- Delete", self._delete, DANGER),
        ]:
            IconButton(parent, label, cmd, color=color).pack(side=tk.LEFT, padx=2)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        try:
            entries = list(os.scandir(self._current_path))
        except PermissionError:
            messagebox.showerror("Permission Denied", f"Cannot access {self._current_path}")
            return
        dirs, files = [], []
        for e in entries:
            try:
                stat  = e.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                if e.is_dir():
                    dirs.append((DIR_PFX + e.name, "", mtime, "dir"))
                else:
                    dirs.append((FILE_PFX + e.name, self._fmt_size(stat.st_size), mtime, "file")) \
                        if False else files.append(
                            (FILE_PFX + e.name, self._fmt_size(stat.st_size), mtime, "file"))
            except (PermissionError, OSError):
                pass
        dirs.sort(); files.sort()
        for name, size, mtime, tag in dirs + files:
            self.tree.insert("", tk.END, text=name, values=(size, mtime), tags=(tag,))

    def _mkdir(self):
        name = simpledialog.askstring("New Directory", "Directory name:", parent=self)
        if not name: return
        try:
            os.makedirs(os.path.join(self._current_path, name), exist_ok=True)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _rename(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select a file/dir first"); return
        new = simpledialog.askstring("Rename", "New name:", parent=self)
        if not new: return
        try:
            os.rename(sel[0], os.path.join(self._current_path, new))
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _copy(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select file(s) first"); return
        dst = filedialog.askdirectory(title="Copy to...", initialdir=self._current_path)
        if not dst: return
        for src in sel:
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, os.path.join(dst, os.path.basename(src)))
                else:
                    shutil.copy2(src, dst)
            except Exception as e:
                messagebox.showerror("Error", str(e))
        self.refresh()

    def _move(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select file(s) first"); return
        dst = filedialog.askdirectory(title="Move to...", initialdir=self._current_path)
        if not dst: return
        for src in sel:
            try: shutil.move(src, dst)
            except Exception as e: messagebox.showerror("Error", str(e))
        self.refresh()

    def _delete(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select file(s) first"); return
        if not messagebox.askyesno("Confirm Delete",
                f"Delete {len(sel)} item(s)? This cannot be undone."): return
        for path in sel:
            try:
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
            except Exception as e:
                messagebox.showerror("Error", str(e))
        self.refresh()


# ─────────────────────────────────────────────────────────────────────────────
# HDFS Pane
# ─────────────────────────────────────────────────────────────────────────────

class HDFSPane(FilePaneBase):
    def __init__(self, parent, log_fn=None, **kw):
        self._log_fn = log_fn or (lambda m, t="": None)
        super().__init__(parent, "[H]  HDFS FILESYSTEM", **kw)

    def _root_path(self):  return "/"
    def _home_path(self):  return "/user/" + os.environ.get("USER", "hadoop")
    def _is_hdfs(self):    return True

    def _build_extra_nav(self, parent):
        # parent is the header bar; Right-pack so order is: Up | Home | HDFS Root | Refresh
        IconButton(parent, "/ HDFS Root", lambda: self.navigate("/"),
                   color=BG_HOVER).pack(side=tk.RIGHT, padx=2)

    def _build_ops(self, parent):
        for label, cmd, color in [
            ("+ Dir",     self._mkdir,    ACCENT),
            ("+ Parents", self._mkdir_p,  ACCENT),
            ("~ Rename",  self._rename,   WARNING),
            ("+ Copy",    self._copy,     ACCENT2),
            ("x Move",    self._move,     ACCENT2),
            ("- Del",     self._delete,   DANGER),
            ("-- Rm-r",   self._delete_r, DANGER),
            ("@ Chmod",   self._chmod,    TEXT_SEC),
            ("# Chown",   self._chown,    TEXT_SEC),
        ]:
            IconButton(parent, label, cmd, color=color).pack(side=tk.LEFT, padx=2)

    def _hdfs(self, args, log=True):
        cmd = f"hdfs dfs {args}"
        if log: self._log_fn(f"$ {cmd}", "info")
        return run_cmd(cmd)

    def refresh(self):
        path = self._current_path
        def worker():
            out, err, rc = run_cmd(f"hdfs dfs -ls {path}")
            def update():
                self.tree.delete(*self.tree.get_children())
                if rc != 0:
                    self._log_fn(f"ls {path}: {err.strip()}", "err")
                    return
                for line in out.strip().splitlines():
                    if line.startswith("Found") or not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) < 8: continue
                    perms, _, owner, group, size, date, time_, *rest = parts
                    name     = rest[0] if rest else "?"
                    basename = os.path.basename(name)
                    is_dir   = perms.startswith("d")
                    pfx      = DIR_PFX if is_dir else FILE_PFX
                    tag      = "dir"   if is_dir else "file"
                    sz       = "" if is_dir else (self._fmt_size(int(size)) if size.isdigit() else size)
                    self.tree.insert("", tk.END, text=pfx + basename,
                                     values=(sz, f"{date} {time_}"), tags=(tag,))
            self.after(0, update)
        threading.Thread(target=worker, daemon=True).start()

    def _mkdir(self):
        name = simpledialog.askstring("New HDFS Directory", "Directory name:", parent=self)
        if not name: return
        path = os.path.join(self._current_path, name).replace("//", "/")
        _, err, rc = self._hdfs(f"-mkdir {path}")
        self.refresh() if rc == 0 else messagebox.showerror("HDFS Error", err)

    def _mkdir_p(self):
        path = simpledialog.askstring("Make Parents",
            "Full HDFS path (parents created automatically):",
            parent=self, initialvalue=self._current_path + "/")
        if not path: return
        _, err, rc = self._hdfs(f"-mkdir -p {path}")
        self.refresh() if rc == 0 else messagebox.showerror("HDFS Error", err)

    def _rename(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select a file/dir first"); return
        new = simpledialog.askstring("Rename", "New name:", parent=self)
        if not new: return
        dst = os.path.join(self._current_path, new).replace("//", "/")
        _, err, rc = self._hdfs(f"-mv {sel[0]} {dst}")
        self.refresh() if rc == 0 else messagebox.showerror("HDFS Error", err)

    def _copy(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select file(s) first"); return
        dst = simpledialog.askstring("Copy to HDFS path", "Destination:",
            parent=self, initialvalue=self._current_path + "/")
        if not dst: return
        for src in sel:
            _, err, rc = self._hdfs(f"-cp {src} {dst}")
            if rc != 0: messagebox.showerror("HDFS Error", err)
        self.refresh()

    def _move(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select file(s) first"); return
        dst = simpledialog.askstring("Move to HDFS path", "Destination:",
            parent=self, initialvalue=self._current_path + "/")
        if not dst: return
        for src in sel:
            _, err, rc = self._hdfs(f"-mv {src} {dst}")
            if rc != 0: messagebox.showerror("HDFS Error", err)
        self.refresh()

    def _delete(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select file(s) first"); return
        if not messagebox.askyesno("Confirm", f"Delete {len(sel)} item(s) from HDFS?"): return
        for path in sel:
            _, err, rc = self._hdfs(f"-rm {path}")
            if rc != 0: messagebox.showerror("HDFS Error", err)
        self.refresh()

    def _delete_r(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select item(s) first"); return
        if not messagebox.askyesno("Confirm Recursive Delete",
                f"Recursively delete {len(sel)} item(s)?\nThis CANNOT be undone!"): return
        for path in sel:
            _, err, rc = self._hdfs(f"-rm -r {path}")
            if rc != 0: messagebox.showerror("HDFS Error", err)
        self.refresh()

    def _chmod(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select file(s) first"); return
        mode = simpledialog.askstring("Chmod", "Permissions (e.g. 755):", parent=self)
        if not mode: return
        for path in sel:
            _, err, rc = self._hdfs(f"-chmod {mode} {path}")
            if rc != 0: messagebox.showerror("HDFS Error", err)

    def _chown(self):
        sel = self.selected_paths()
        if not sel: messagebox.showwarning("Select", "Select file(s) first"); return
        owner = simpledialog.askstring("Chown", "owner[:group]:", parent=self)
        if not owner: return
        for path in sel:
            _, err, rc = self._hdfs(f"-chown {owner} {path}")
            if rc != 0: messagebox.showerror("HDFS Error", err)


# ─────────────────────────────────────────────────────────────────────────────
# Transfer Tab
# ─────────────────────────────────────────────────────────────────────────────

class TransferTab(tk.Frame):
    def __init__(self, parent, viewer_tab_ref=None):
        super().__init__(parent, bg=BG_DARK)
        self._viewer_ref     = viewer_tab_ref  # set after creation via set_viewer()
        self._sel_local      = None
        self._sel_hdfs       = None
        self._sel_local_type = None
        self._sel_hdfs_type  = None
        self._build()

    def set_viewer(self, viewer):
        """Wire the viewer after both tabs are created."""
        self._viewer_ref = viewer

    def _build(self):
        tk.Label(self, text="[~]  FILE TRANSFER & EXPLORER", fg=ACCENT,
                 bg=BG_DARK, font=F_MONO_XL).pack(anchor=tk.W, padx=20, pady=(15, 5))

        panes = tk.Frame(self, bg=BG_DARK)
        panes.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=0)
        panes.columnconfigure(2, weight=1)
        panes.rowconfigure(0, weight=1)

        self.local_pane = LocalPane(
            panes,
            on_selection=self._local_selected,
            on_file_open=self._open_local_file,
        )
        self.local_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        mid = tk.Frame(panes, bg=BG_DARK, width=130)
        mid.grid(row=0, column=1, sticky="ns", padx=4)
        mid.pack_propagate(False)
        tk.Label(mid, text="TRANSFER", fg=TEXT_DIM, bg=BG_DARK,
                 font=("Courier New", 8, "bold")).pack(pady=(20, 6))
        for label, cmd, color, tip in [
            ("-> PUT",           self._put,       ACCENT,  "Skip existing"),
            ("-> PUT overwrite", self._put_f,     SUCCESS, "Overwrite existing"),
            ("<- GET",           self._get,       ACCENT2, "Get selected"),
            ("<- GET overwrite", self._get_f,     WARNING, "Overwrite existing local"),
        ]:
            btn = IconButton(mid, label, cmd, color=color, width=14)
            btn.pack(pady=4, padx=4)
        tk.Label(mid, text="Select multiple\nitems with\nCtrl+Click",
                 fg=TEXT_DIM, bg=BG_DARK,
                 font=("Courier New", 7), justify=tk.CENTER).pack(pady=(10, 0))

        # Build log BEFORE HDFSPane so _log_fn is safe from the start
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X, padx=10)
        tk.Label(self, text="TRANSFER LOG", fg=TEXT_SEC,
                 bg=BG_DARK, font=F_MONO_MD).pack(anchor=tk.W, padx=20, pady=(5, 0))
        self.log = LogPanel(self, height=7)
        self.log.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.hdfs_pane = HDFSPane(
            panes,
            log_fn=self._log,
            on_selection=self._hdfs_selected,
            on_file_open=self._open_hdfs_file,
        )
        self.hdfs_pane.grid(row=0, column=2, sticky="nsew", padx=(4, 0))

    def _log(self, msg, tag=""):
        self.log.log_safe(msg, tag)

    def _local_selected(self, path, tag, pane):
        self._sel_local = path
        self._sel_local_type = tag

    def _hdfs_selected(self, path, tag, pane):
        self._sel_hdfs = path
        self._sel_hdfs_type = tag

    def _open_local_file(self, path, is_hdfs):
        """Double-click on local file -> load into viewer and auto-cat."""
        if self._viewer_ref:
            self._viewer_ref.open_and_cat(path, is_hdfs=False)

    def _open_hdfs_file(self, path, is_hdfs):
        """Double-click on HDFS file -> load into viewer and auto-cat."""
        if self._viewer_ref:
            self._viewer_ref.open_and_cat(path, is_hdfs=True)

    # ── helpers ─────────────────────────────────────────────────────────────────

    def _local_sel_paths(self):
        paths = self.local_pane.selected_paths()
        if not paths:
            messagebox.showwarning("Select", "Select one or more local files/dirs (left pane)")
        return paths

    def _hdfs_sel_paths(self):
        paths = self.hdfs_pane.selected_paths()
        if not paths:
            messagebox.showwarning("Select", "Select one or more HDFS files/dirs (right pane)")
        return paths

    def _hdfs_exists(self, path):
        """Return True if path exists on HDFS."""
        _, _, rc = run_cmd(f"hdfs dfs -test -e {path}", timeout=10)
        return rc == 0

    # ── PUT (skip existing) ──────────────────────────────────────────────────
    def _put(self):
        srcs = self._local_sel_paths()
        if not srcs: return
        dst = self.hdfs_pane._current_path
        def worker():
            ok = skip = fail = 0
            for src in srcs:
                name    = os.path.basename(src.rstrip("/"))
                hdfs_dst = dst.rstrip("/") + "/" + name
                if self._hdfs_exists(hdfs_dst):
                    self.log.log_safe(f"  SKIP (exists): {hdfs_dst}", "warn")
                    skip += 1
                    continue
                self.log.log_safe(f"$ hdfs dfs -put '{src}' {dst}", "info")
                out, err, rc = run_cmd(f"hdfs dfs -put '{src}' {dst}", timeout=600)
                if rc == 0:
                    self.log.log_safe(f"  OK: {name}", "ok"); ok += 1
                else:
                    self.log.log_safe(f"  FAIL: {name} -- {err.strip()}", "err"); fail += 1
            self.log.log_safe(
                f"[PUT] done: {ok} uploaded, {skip} skipped, {fail} failed",
                "ok" if fail == 0 else "warn")
            self.after(0, self.hdfs_pane.refresh)
            self.after(0, self.local_pane.refresh)
        self.log.log(f"PUT {len(srcs)} item(s) -> {dst}  (skip existing)", "info")
        threading.Thread(target=worker, daemon=True).start()

    # ── PUT overwrite ────────────────────────────────────────────────────────
    def _put_f(self):
        srcs = self._local_sel_paths()
        if not srcs: return
        dst = self.hdfs_pane._current_path
        def worker():
            ok = fail = 0
            for src in srcs:
                self.log.log_safe(f"$ hdfs dfs -put -f '{src}' {dst}", "info")
                out, err, rc = run_cmd(f"hdfs dfs -put -f '{src}' {dst}", timeout=600)
                name = os.path.basename(src.rstrip("/"))
                if rc == 0:
                    self.log.log_safe(f"  OK: {name}", "ok"); ok += 1
                else:
                    self.log.log_safe(f"  FAIL: {name} -- {err.strip()}", "err"); fail += 1
            self.log.log_safe(
                f"[PUT overwrite] done: {ok} ok, {fail} failed",
                "ok" if fail == 0 else "warn")
            self.after(0, self.hdfs_pane.refresh)
            self.after(0, self.local_pane.refresh)
        self.log.log(f"PUT (overwrite) {len(srcs)} item(s) -> {dst}", "info")
        threading.Thread(target=worker, daemon=True).start()

    # ── GET (skip existing local) ────────────────────────────────────────────
    def _get(self):
        srcs = self._hdfs_sel_paths()
        if not srcs: return
        dst = self.local_pane._current_path
        def worker():
            ok = skip = fail = 0
            for src in srcs:
                name      = os.path.basename(src.rstrip("/"))
                local_dst = os.path.join(dst, name)
                if os.path.exists(local_dst):
                    self.log.log_safe(f"  SKIP (exists): {local_dst}", "warn")
                    skip += 1
                    continue
                self.log.log_safe(f"$ hdfs dfs -get '{src}' '{dst}'", "info")
                out, err, rc = run_cmd(f"hdfs dfs -get '{src}' '{dst}'", timeout=600)
                if rc == 0:
                    self.log.log_safe(f"  OK: {name}", "ok"); ok += 1
                else:
                    self.log.log_safe(f"  FAIL: {name} -- {err.strip()}", "err"); fail += 1
            self.log.log_safe(
                f"[GET] done: {ok} downloaded, {skip} skipped, {fail} failed",
                "ok" if fail == 0 else "warn")
            self.after(0, self.local_pane.refresh)
        self.log.log(f"GET {len(srcs)} item(s) -> {dst}  (skip existing)", "info")
        threading.Thread(target=worker, daemon=True).start()

    # ── GET overwrite ────────────────────────────────────────────────────────
    def _get_f(self):
        srcs = self._hdfs_sel_paths()
        if not srcs: return
        dst = self.local_pane._current_path
        def worker():
            ok = fail = 0
            for src in srcs:
                name      = os.path.basename(src.rstrip("/"))
                local_dst = os.path.join(dst, name)
                # remove existing so -get can overwrite
                try:
                    if os.path.isdir(local_dst):
                        import shutil; shutil.rmtree(local_dst)
                    elif os.path.exists(local_dst):
                        os.remove(local_dst)
                except Exception as e:
                    self.log.log_safe(f"  Could not remove {local_dst}: {e}", "warn")
                self.log.log_safe(f"$ hdfs dfs -get '{src}' '{dst}'", "info")
                out, err, rc = run_cmd(f"hdfs dfs -get '{src}' '{dst}'", timeout=600)
                if rc == 0:
                    self.log.log_safe(f"  OK: {name}", "ok"); ok += 1
                else:
                    self.log.log_safe(f"  FAIL: {name} -- {err.strip()}", "err"); fail += 1
            self.log.log_safe(
                f"[GET overwrite] done: {ok} ok, {fail} failed",
                "ok" if fail == 0 else "warn")
            self.after(0, self.local_pane.refresh)
        self.log.log(f"GET (overwrite) {len(srcs)} item(s) -> {dst}", "info")
        threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Viewer Tab
# ─────────────────────────────────────────────────────────────────────────────

class ViewerTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_DARK)
        self._tail_proc = None
        self._build()

    def _build(self):
        tk.Label(self, text="[V]  FILE VIEWER", fg=ACCENT,
                 bg=BG_DARK, font=F_MONO_XL).pack(anchor=tk.W, padx=20, pady=(15, 5))

        top = tk.Frame(self, bg=BG_PANEL, pady=8, padx=12)
        top.pack(fill=tk.X, padx=10)

        self.src_var = tk.StringVar(value="hdfs")
        for val, lbl in [("hdfs", "HDFS"), ("local", "Local")]:
            tk.Radiobutton(top, text=lbl, variable=self.src_var, value=val,
                bg=BG_PANEL, fg=TEXT_PRI, selectcolor=BG_DARK,
                activebackground=BG_PANEL, font=F_MONO_MD).pack(side=tk.LEFT)

        tk.Label(top, text="  File:", fg=TEXT_DIM, bg=BG_PANEL,
                 font=F_MONO_MD).pack(side=tk.LEFT, padx=(10, 0))
        self.path_var = tk.StringVar()
        tk.Entry(top, textvariable=self.path_var, bg="#090b14", fg=ACCENT,
                 insertbackground=ACCENT, relief=tk.FLAT,
                 font=F_MONO_SM, width=55).pack(side=tk.LEFT, padx=6)
        IconButton(top, "Browse", self._browse, color=ACCENT).pack(side=tk.LEFT)

        # Row 1 — view commands (output shown in the panel below)
        modes1 = tk.Frame(self, bg=BG_DARK, pady=3, padx=10)
        modes1.pack(fill=tk.X)
        tk.Label(modes1, text="VIEW:", fg=TEXT_DIM, bg=BG_DARK,
                 font=F_MONO_SM).pack(side=tk.LEFT, padx=(0, 4))
        for label, cmd in [
            ("cat",     self._cat),
            ("nl",      self._nl),
            ("head",    self._head),
            ("tail",    self._tail),
            ("tail -f", self._tail_f),
            ("wc -l",   self._wc),
            ("du -h",   self._du),
            ("stat",    self._stat),
            ("strings", self._strings),
            ("hexdump", self._hexdump),
        ]:
            IconButton(modes1, label, cmd, color=BG_CARD, fg=TEXT_PRI).pack(side=tk.LEFT, padx=2)

        # Row 2 — editors (open in a terminal window; local files only)
        modes2 = tk.Frame(self, bg=BG_DARK, pady=3, padx=10)
        modes2.pack(fill=tk.X)
        tk.Label(modes2, text="EDIT:", fg=TEXT_DIM, bg=BG_DARK,
                 font=F_MONO_SM).pack(side=tk.LEFT, padx=(0, 4))
        for label, cmd, color in [
            ("nano",          self._nano,         SUCCESS),
            ("vim",           self._vim,          ACCENT2),
            ("vim read-only", self._vim_readonly, BG_HOVER),
        ]:
            IconButton(modes2, label, cmd, color=color).pack(side=tk.LEFT, padx=2)
        tk.Label(modes2, text="  (local files only — opens in a new terminal window)",
                 fg=TEXT_DIM, bg=BG_DARK, font=F_MONO_SM).pack(side=tk.LEFT, padx=6)

        opts = tk.Frame(self, bg=BG_DARK, padx=10, pady=4)
        opts.pack(fill=tk.X)
        tk.Label(opts, text="Lines:", fg=TEXT_DIM, bg=BG_DARK, font=F_MONO_SM).pack(side=tk.LEFT)
        self.lines_var = tk.StringVar(value="200")
        tk.Entry(opts, textvariable=self.lines_var, width=6,
                 bg="#090b14", fg=ACCENT, insertbackground=ACCENT,
                 relief=tk.FLAT, font=F_MONO_SM).pack(side=tk.LEFT, padx=4)
        tk.Label(opts, text="  Search:", fg=TEXT_DIM, bg=BG_DARK, font=F_MONO_SM).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        se = tk.Entry(opts, textvariable=self.search_var, width=26,
                      bg="#090b14", fg=WARNING, insertbackground=WARNING,
                      relief=tk.FLAT, font=F_MONO_SM)
        se.pack(side=tk.LEFT, padx=4)
        se.bind("<Return>", lambda e: self._search())
        IconButton(opts, "Find",      self._search,       color=WARNING).pack(side=tk.LEFT, padx=2)
        IconButton(opts, "Clear",     self._clear_output, color=BG_CARD, fg=TEXT_PRI).pack(side=tk.LEFT, padx=2)
        IconButton(opts, "Save",      self._save_output,  color=BG_CARD, fg=TEXT_PRI).pack(side=tk.LEFT, padx=2)
        IconButton(opts, "Stop tail", self._stop_tail_f,  color=DANGER).pack(side=tk.LEFT, padx=2)

        out_frame = tk.Frame(self, bg=BG_PANEL)
        out_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        self.output = tk.Text(out_frame, bg="#090b14", fg="#c8d8e8",
                              font=F_LOG, insertbackground=ACCENT,
                              relief=tk.FLAT, wrap=tk.NONE, state=tk.DISABLED)
        vsb = ttk.Scrollbar(out_frame, orient=tk.VERTICAL,   command=self.output.yview)
        hsb = ttk.Scrollbar(out_frame, orient=tk.HORIZONTAL, command=self.output.xview)
        self.output.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.output.tag_config("match", background="#3a3000", foreground=WARNING)
        self.output.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        out_frame.rowconfigure(0, weight=1)
        out_frame.columnconfigure(0, weight=1)

        self.view_status = tk.Label(self, text="", fg=TEXT_SEC, bg=BG_DARK, font=F_MONO_SM)
        self.view_status.pack(anchor=tk.W, padx=14, pady=(0, 4))

    def open_file(self, path, is_hdfs):
        """Set file path without running any command (used by main app tab-switch hook)."""
        self.path_var.set(path)
        self.src_var.set("hdfs" if is_hdfs else "local")
        self.view_status.config(
            text=f"Loaded: {path}  ({'HDFS' if is_hdfs else 'Local'}) -- click a view button")

    def open_and_cat(self, path, is_hdfs):
        """Called on double-click: set the file AND immediately run cat."""
        self.path_var.set(path)
        self.src_var.set("hdfs" if is_hdfs else "local")
        # Trigger cat right away
        n = self.lines_var.get() or "500"
        if is_hdfs:
            cmd = f"hdfs dfs -cat {path} 2>/dev/null | head -{n}"
        else:
            cmd = f"head -{n} '{path}'"
        self.view_status.config(text=f"Loading: {path} ...")
        def worker():
            out, err, rc = run_cmd(cmd, timeout=120)
            combined = out if out else err
            lines  = combined.count("\n")
            status = (f"{'HDFS' if is_hdfs else 'Local'}: {path}  |  "
                      f"{lines} lines  |  {len(combined):,} chars")
            self.after(0, lambda: self._write_output(combined, status))
        threading.Thread(target=worker, daemon=True).start()

    def _browse(self):
        if self.src_var.get() == "local":
            p = filedialog.askopenfilename()
            if p: self.path_var.set(p)

    def _get_path(self):
        return self.path_var.get().strip()

    def _write_output(self, text, status=""):
        self.output.config(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        self.output.config(state=tk.DISABLED)
        if status:
            self.view_status.config(text=status)

    def _run_view(self, build_cmd_fn):
        """build_cmd_fn(path, is_hdfs) -> shell command string."""
        path = self._get_path()
        if not path:
            messagebox.showwarning("No file", "Enter or select a file path first"); return
        is_hdfs = (self.src_var.get() == "hdfs")
        cmd = build_cmd_fn(path, is_hdfs)
        self.view_status.config(text=f"Running: {cmd}")
        def worker():
            out, err, rc = run_cmd(cmd, timeout=120)
            combined = out
            if err and rc != 0:
                combined += "\n--- STDERR ---\n" + err
            lines  = combined.count("\n")
            status = f"Done | {lines} lines | {len(combined):,} chars | exit {rc}"
            self.after(0, lambda: self._write_output(combined, status))
        threading.Thread(target=worker, daemon=True).start()

    def _cat(self):
        self._run_view(lambda p, h: f"hdfs dfs -cat {p}" if h else f"cat '{p}'")

    def _head(self):
        n = self.lines_var.get() or "200"
        self._run_view(lambda p, h, n=n:
            f"hdfs dfs -cat {p} 2>/dev/null | head -{n}" if h
            else f"head -{n} '{p}'")

    def _tail(self):
        n = self.lines_var.get() or "200"
        self._run_view(lambda p, h, n=n:
            f"hdfs dfs -tail {p}" if h
            else f"tail -{n} '{p}'")

    def _wc(self):
        self._run_view(lambda p, h:
            f"hdfs dfs -count {p}" if h else f"wc -l '{p}'")

    def _du(self):
        self._run_view(lambda p, h:
            f"hdfs dfs -du -h {p}" if h else f"du -sh '{p}'")

    def _stat(self):
        self._run_view(lambda p, h:
            f"hdfs dfs -stat '%F %b %u %g %r %a' {p}" if h else f"stat '{p}'")

    def _strings(self):
        """strings only works on local files; for HDFS, pull to stdout first."""
        path = self._get_path()
        if not path:
            messagebox.showwarning("No file", "Enter or select a file path first"); return
        is_hdfs = (self.src_var.get() == "hdfs")
        if is_hdfs:
            cmd = f"hdfs dfs -cat {path} | strings"
        else:
            cmd = f"strings '{path}'"
        self.view_status.config(text=f"Running: {cmd}")
        def worker():
            out, err, rc = run_cmd(cmd, timeout=120)
            combined = out if out else (err or "(no printable strings found)")
            status = f"strings | {combined.count(chr(10))} lines | exit {rc}"
            self.after(0, lambda: self._write_output(combined, status))
        threading.Thread(target=worker, daemon=True).start()

    def _hexdump(self):
        path = self._get_path()
        if not path:
            messagebox.showwarning("No file", "Enter or select a file path first"); return
        is_hdfs = (self.src_var.get() == "hdfs")
        n = self.lines_var.get() or "200"
        if is_hdfs:
            cmd = f"hdfs dfs -cat {path} 2>/dev/null | hexdump -C | head -{n}"
        else:
            cmd = f"hexdump -C '{path}' | head -{n}"
        self.view_status.config(text=f"Running: {cmd}")
        def worker():
            out, err, rc = run_cmd(cmd, timeout=60)
            combined = out if out else err
            self.after(0, lambda: self._write_output(combined,
                f"hexdump | {combined.count(chr(10))} lines | exit {rc}"))
        threading.Thread(target=worker, daemon=True).start()

    def _nl(self):
        """nl — number lines. Works for both local and HDFS."""
        self._run_view(lambda p, h:
            f"hdfs dfs -cat {p} 2>/dev/null | nl" if h
            else f"nl '{p}'")

    # ── Editor launchers ──────────────────────────────────────────────────────
    # nano and vim are full-screen terminal apps; we open them in a new
    # terminal window (xterm preferred, falls back to gnome-terminal/konsole).

    def _open_in_terminal(self, editor_cmd):
        """Open editor_cmd in a new terminal window (local files only)."""
        path = self._get_path()
        if not path:
            messagebox.showwarning("No file", "Enter or select a local file path first"); return
        if self.src_var.get() == "hdfs":
            messagebox.showinfo(
                "Local only",
                f"{editor_cmd.split()[0]} works on local files only.\n\n"
                "To edit an HDFS file:\n"
                "  1. GET the file to local (Explorer tab)\n"
                "  2. Edit it here\n"
                "  3. PUT it back to HDFS"); return

        # Try terminal emulators in order of preference
        terminals = [
            ["xterm",           "-e", f"{editor_cmd} '{path}'"],
            ["gnome-terminal",  "--",  editor_cmd, path],
            ["konsole",         "-e",  f"{editor_cmd} '{path}'"],
            ["xfce4-terminal",  "-e",  f"{editor_cmd} '{path}'"],
            ["lxterminal",      "-e",  f"{editor_cmd} '{path}'"],
        ]
        launched = False
        for term_args in terminals:
            try:
                # Check the terminal exists first
                if subprocess.run(["which", term_args[0]],
                                  capture_output=True).returncode == 0:
                    subprocess.Popen(term_args)
                    launched = True
                    self.view_status.config(
                        text=f"Opened {path} in {term_args[0]} ({editor_cmd.split()[0]})")
                    break
            except Exception:
                continue
        if not launched:
            messagebox.showerror(
                "No terminal found",
                "Could not find a terminal emulator.\n"
                "Please install xterm:  sudo apt install xterm")

    def _nano(self):
        self._open_in_terminal("nano")

    def _vim(self):
        self._open_in_terminal("vim")

    def _vim_readonly(self):
        self._open_in_terminal("vim -R")

    def _tail_f(self):
        path = self._get_path()
        if not path:
            messagebox.showwarning("No file", "Enter or select a local file path first"); return
        if self.src_var.get() == "hdfs":
            messagebox.showinfo("Info", "tail -f is for local files only.\n"
                                        "Use the 'tail' button for HDFS."); return
        self._stop_tail_f()
        try:
            self._tail_proc = subprocess.Popen(
                ["tail", "-f", path], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True)
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        def reader():
            for line in self._tail_proc.stdout:
                def append(l=line):
                    self.output.config(state=tk.NORMAL)
                    self.output.insert(tk.END, l)
                    self.output.see(tk.END)
                    self.output.config(state=tk.DISABLED)
                self.after(0, append)
        threading.Thread(target=reader, daemon=True).start()
        self.view_status.config(text=f"tail -f {path}  -- click 'Stop tail' to stop")

    def _stop_tail_f(self):
        if self._tail_proc:
            try: self._tail_proc.terminate()
            except Exception: pass
            self._tail_proc = None
            self.view_status.config(text="tail -f stopped")

    def _search(self):
        query = self.search_var.get()
        if not query: return
        self.output.tag_remove("match", "1.0", tk.END)
        start, count = "1.0", 0
        while True:
            pos = self.output.search(query, start, stopindex=tk.END)
            if not pos: break
            end = f"{pos}+{len(query)}c"
            self.output.tag_add("match", pos, end)
            start = end
            count += 1
        ranges = self.output.tag_ranges("match")
        if ranges: self.output.see(ranges[0])
        self.view_status.config(text=f"Found {count} match(es) for '{query}'")

    def _clear_output(self):
        self.output.config(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.config(state=tk.DISABLED)
        self.view_status.config(text="")

    def _save_output(self):
        content = self.output.get("1.0", tk.END)
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if path:
            with open(path, "w") as f:
                f.write(content)


# ─────────────────────────────────────────────────────────────────────────────
# Terminal Tab
# ─────────────────────────────────────────────────────────────────────────────

class TerminalTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_DARK)
        self._history  = []
        self._hist_idx = 0
        self._build()

    def _build(self):
        tk.Label(self, text=">>  QUICK TERMINAL", fg=ACCENT,
                 bg=BG_DARK, font=F_MONO_XL).pack(anchor=tk.W, padx=20, pady=(15, 5))
        tk.Label(self, text="HDFS QUICK COMMANDS", fg=TEXT_SEC,
                 bg=BG_DARK, font=F_MONO_MD).pack(anchor=tk.W, padx=20)

        presets = tk.Frame(self, bg=BG_DARK)
        presets.pack(fill=tk.X, padx=10, pady=5)
        quick = [
            ("dfs -ls /",      "hdfs dfs -ls /"),
            ("dfs report",     "hdfs dfsadmin -report"),
            ("fs -df -h /",    "hdfs dfs -df -h /"),
            ("dfs -du -h /",   "hdfs dfs -du -h /"),
            ("yarn node list", "yarn node -list"),
            ("yarn apps",      "yarn application -list -appStates ALL"),
            ("jps",            "jps"),
            ("HDFS fsck",      "hdfs fsck / -files -blocks -locations 2>&1 | head -50"),
        ]
        for i, (label, cmd) in enumerate(quick):
            r, c = divmod(i, 4)
            IconButton(presets, label, lambda c=cmd: self._run_preset(c),
                       color=BG_CARD, fg=TEXT_PRI).grid(
                           row=r, column=c, padx=3, pady=3, sticky="ew")
        for c in range(4):
            presets.columnconfigure(c, weight=1)

        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X, padx=10, pady=5)

        self.log = LogPanel(self, height=22)
        self.log.pack(fill=tk.BOTH, expand=True, padx=10)

        inp = tk.Frame(self, bg=BG_PANEL, pady=6, padx=10)
        inp.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(inp, text="$", fg=SUCCESS, bg=BG_PANEL,
                 font=("Courier New", 14, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        self.cmd_var = tk.StringVar()
        cmd_entry = tk.Entry(inp, textvariable=self.cmd_var,
                             bg="#090b14", fg="#a0f0a0", insertbackground=SUCCESS,
                             relief=tk.FLAT, font=("Courier New", 12), bd=6)
        cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        cmd_entry.bind("<Return>", self._run_cmd)
        cmd_entry.bind("<Up>",     self._hist_up)
        cmd_entry.bind("<Down>",   self._hist_down)
        cmd_entry.focus()
        IconButton(inp, "RUN",   self._run_cmd,  color=SUCCESS).pack(side=tk.LEFT, padx=6)
        IconButton(inp, "Clear", self.log.clear, color=BG_HOVER).pack(side=tk.LEFT)

    def _run_preset(self, cmd):
        self.cmd_var.set(cmd)
        self._run_cmd()

    def _run_cmd(self, event=None):
        cmd = self.cmd_var.get().strip()
        if not cmd: return
        self._history.append(cmd)
        self._hist_idx = len(self._history)
        self.cmd_var.set("")
        self.log.log(f"$ {cmd}", "info")
        def worker():
            out, err, rc = run_cmd(cmd)
            for line in (out or "").strip().splitlines():
                self.log.log_safe(line)
            for line in (err or "").strip().splitlines():
                self.log.log_safe(line, "err" if rc != 0 else "warn")
            self.log.log_safe(f"exit {rc}", "ok" if rc == 0 else "err")
        threading.Thread(target=worker, daemon=True).start()

    def _hist_up(self, event):
        if self._hist_idx > 0:
            self._hist_idx -= 1
            self.cmd_var.set(self._history[self._hist_idx])

    def _hist_down(self, event):
        if self._hist_idx < len(self._history) - 1:
            self._hist_idx += 1
            self.cmd_var.set(self._history[self._hist_idx])
        else:
            self._hist_idx = len(self._history)
            self.cmd_var.set("")


# ─────────────────────────────────────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────────────────────────────────────

class HDFSManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HDFS Manager -- Hadoop File Explorer")
        self.geometry("1360x860")
        self.configure(bg=BG_DARK)
        self.minsize(960, 640)
        self._build_style()
        self._build_ui()

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook",     background=BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_PANEL, foreground=TEXT_SEC,
                         padding=(20, 9), font=F_MONO_BTN)
        style.map("TNotebook.Tab",
            background=[("selected", BG_CARD)],
            foreground=[("selected", ACCENT)])
        style.configure("TScrollbar", background=BG_CARD, troughcolor=BG_DARK,
                         borderwidth=0, arrowsize=14)

    def _build_ui(self):
        title_bar = tk.Frame(self, bg=BG_CARD, height=52)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)
        tk.Label(title_bar, text="[H]  HDFS MANAGER", fg=ACCENT, bg=BG_CARD,
                 font=("Courier New", 17, "bold")).pack(side=tk.LEFT, padx=20)
        tk.Label(title_bar, text="Hadoop File Explorer & Service Control",
                 fg=TEXT_DIM, bg=BG_CARD, font=F_MONO_MD).pack(side=tk.LEFT, padx=4)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True)

        self.svc_tab      = ServicesTab(self.nb)
        self.viewer_tab   = ViewerTab(self.nb)          # create viewer first
        self.transfer_tab = TransferTab(self.nb)        # then transfer
        self.transfer_tab.set_viewer(self.viewer_tab)   # wire viewer reference
        self.terminal_tab = TerminalTab(self.nb)

        self.nb.add(self.svc_tab,      text="  [S] Services  ")
        self.nb.add(self.transfer_tab, text="  [~] Explorer  ")
        self.nb.add(self.viewer_tab,   text="  [V] Viewer    ")
        self.nb.add(self.terminal_tab, text="  >> Terminal   ")

        # When a file is opened via double-click, auto-switch to Viewer tab
        orig_open_and_cat = self.viewer_tab.open_and_cat
        def open_cat_and_switch(path, is_hdfs):
            self.nb.select(self.viewer_tab)
            orig_open_and_cat(path, is_hdfs)
        self.viewer_tab.open_and_cat = open_cat_and_switch

        self.status = StatusBar(self)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)
        self.status.set("Ready  --  Double-click any file in Explorer to open it in Viewer")


def main():
    app = HDFSManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()