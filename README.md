# HDFS Manager

A dark-themed desktop GUI for Apache Hadoop : built with Python and Tkinter.  
Manage HDFS and your local Linux filesystem side by side, control Hadoop services, view and edit files, and run shell commands, all from one window.

![Python](https://img.shields.io/badge/Python-3.7%2B-blue?style=flat-square&logo=python)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-informational?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Linux-lightgrey?style=flat-square&logo=linux)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Features at a Glance

| Area | What you can do |
|---|---|
| **Services** | Start, stop, restart HDFS and YARN independently or all at once. Live daemon monitor via `jps`. |
| **Explorer** | Dual-pane file manager : local on the left, HDFS on the right. Navigate, create, rename, copy, move, delete on both sides. |
| **Transfer** | Multi-select PUT and GET with skip-existing or overwrite modes. Works on files and directories equally. |
| **Viewer** | cat, nl, head, tail, tail -f, wc, du, stat, strings, hexdump. In-viewer search with highlight. |
| **Editors** | Open local files in nano or vim in a new terminal window directly from the GUI. |
| **Terminal** | Quick-launch preset HDFS commands or type any shell command with Up/Down arrow history. |

---

## Requirements

| Dependency | Notes |
|---|---|
| Python 3.7+ | Tested on 3.7 and 3.9 |
| Tkinter | Usually bundled with Python : see install note below |
| Apache Hadoop | `hdfs`, `yarn`, and `jps` must be on your `$PATH` |
| `$HADOOP_HOME` | Must point to your Hadoop installation directory |
| xterm _(optional)_ | Used by the nano/vim launcher : falls back to gnome-terminal, konsole, etc. |

Install Tkinter if missing (Ubuntu/Debian):

```bash
sudo apt install python3-tk
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/eng-zakaria/hdfs-manager.git
cd hdfs-manager

# No pip install needed : pure stdlib + tkinter
python3 hdfs_manager.py
```

Make it executable and add to your PATH (optional):

```bash
chmod +x hdfs_manager.py
sudo ln -s $(pwd)/hdfs_manager.py /usr/local/bin/hdfs-manager

# Then launch from anywhere:
hdfs-manager
```

---

## Setup

The app calls `$HADOOP_HOME/sbin/start-dfs.sh` and similar scripts, so your environment must be configured before launching. Source your Hadoop profile first:

```bash
source ~/.bashrc        # or ~/.profile, ~/.bash_profile
python3 hdfs_manager.py
```

Or export manually:

```bash
export HADOOP_HOME=/opt/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
python3 hdfs_manager.py
```

### SSH + X11 Forwarding

If you connect to the machine via SSH, add `-X` so the GUI can display on your local screen:

```bash
ssh -X user@your-server
python3 hdfs_manager.py
```

On **Windows**: use MobaXterm (X server built in) or install VcXsrv.  
On **macOS**: install [XQuartz](https://www.xquartz.org/) first.

---

## How to Use

### Tab 1 : Services

Control HDFS and YARN from one place.

**Starting Hadoop:**

1. Click **> Start HDFS** to start the NameNode and DataNode.
2. Click **> Start YARN** to start the ResourceManager and NodeManager.
3. Or click **> Start All** to bring up everything at once.

**Status indicators** at the top of the tab show **RUNNING** (green) or **STOPPED** (red) for each service in real time.

**Daemon monitor:** The **DAEMON PROCESSES** panel lists all running Java daemons from `jps`. Known Hadoop daemons (NameNode, DataNode, ResourceManager, NodeManager, SecondaryNameNode) are highlighted green.

**Command output:** Every start/stop command streams its output into the **COMMAND OUTPUT** log as it runs, so you can see exactly what Hadoop is doing.

**Other buttons:**

| Button | Action |
|---|---|
| `[] Stop HDFS` | Stop NameNode + DataNode |
| `[] Stop YARN` | Stop ResourceManager + NodeManager |
| `<< Restart HDFS` | Stop HDFS, wait 4 seconds, start it again |
| `<< Restart YARN` | Stop YARN, wait 4 seconds, start it again |
| `[] Stop All` | Stop everything |
| `~~ Refresh` | Re-check service status and daemon list |

---

### Tab 2 : Explorer

A dual-pane file manager. Local filesystem on the left, HDFS on the right.

#### Navigation

Each pane has a header bar with navigation and a path bar below it:

| Button | Action |
|---|---|
| `^ Up` | Go to the parent directory |
| `~ Home` | Go to home (`~` for local, `/user/YOU` for HDFS) |
| `/ Root` | Go to `/` on the local filesystem |
| `/ HDFS Root` | Go to `/` on HDFS |
| `Refresh` | Reload the current directory listing |

Type any path in the **PATH** bar and press **Enter** or **GO** to jump there directly.

#### Selecting Files

- **Single-click** : select one item
- **Ctrl + click** : add/remove items from the selection (multi-select)
- **Shift + click** : select a range of items
- **Double-click a directory** : navigate into it
- **Double-click a file** : open it in the Viewer tab and `cat` it immediately

#### Local Filesystem Operations

| Button | What it does |
|---|---|
| `+ Dir` | Create a new directory here |
| `~ Rename` | Rename the selected file or directory |
| `+ Copy` | Copy selected items to a destination you choose |
| `x Move` | Move selected items to a destination you choose |
| `- Delete` | Permanently delete selected items (confirms first) |

#### HDFS Operations

| Button | What it does |
|---|---|
| `+ Dir` | Create a new HDFS directory |
| `+ Parents` | Create directory and all missing parents (`mkdir -p`) |
| `~ Rename` | Rename a file or directory on HDFS |
| `+ Copy` | Copy selected items to another HDFS path |
| `x Move` | Move selected items to another HDFS path |
| `- Del` | Delete selected files (`hdfs dfs -rm`) |
| `-- Rm-r` | Recursively delete directories (`hdfs dfs -rm -r`) |
| `@ Chmod` | Change permissions : enter a mode like `755` |
| `# Chown` | Change owner/group : enter `user` or `user:group` |

#### Transferring Files

Use the four **TRANSFER** buttons in the middle column between the two panes:

| Button | Behaviour |
|---|---|
| `-> PUT` | Upload selected local items to the current HDFS directory. **Skips** any that already exist on HDFS. |
| `-> PUT overwrite` | Upload selected local items. **Overwrites** existing items on HDFS. |
| `<- GET` | Download selected HDFS items to the current local directory. **Skips** any that already exist locally. |
| `<- GET overwrite` | Download selected HDFS items. **Removes existing local copy** then downloads fresh. |

**How to transfer:**

1. In the **left pane**, navigate to the folder containing what you want to upload, then select files/directories (use Ctrl+click for multiple).
2. In the **right pane**, navigate to the HDFS destination directory.
3. Click **-> PUT** (skip existing) or **-> PUT overwrite**.

To download, do the same in reverse: select items in the right pane, navigate the left pane to where you want them, then click **<- GET**.

**Notes:**
- PUT and GET work identically on files and directories : no special mode needed.
- When transferring multiple items, each one is processed one by one. If one fails the rest continue.
- The **TRANSFER LOG** shows a live per-item status: `OK`, `SKIP (exists)`, or `FAIL` for every item, followed by a summary line.

---

### Tab 3 : Viewer

Inspect file contents without opening a separate terminal.

#### Loading a File

The easiest way is to **double-click any file** in the Explorer tab : the app switches to the Viewer, sets the path, and runs `cat` automatically.

You can also load files manually:

1. Select **HDFS** or **Local** using the radio buttons.
2. Type the file path in the **File** field, or click **Browse** to pick a local file.
3. Click any view button.

#### View Commands

| Button | What it runs | HDFS | Local |
|---|---|---|---|
| `cat` | Full file contents | yes | yes |
| `nl` | Full file with line numbers | yes | yes |
| `head` | First N lines | yes | yes |
| `tail` | Last N lines | yes | yes |
| `tail -f` | Live-follow a growing file | no | yes |
| `wc -l` | Line count | yes | yes |
| `du -h` | Disk usage (human-readable) | yes | yes |
| `stat` | File metadata and permissions | yes | yes |
| `strings` | Printable strings from binary files | yes | yes |
| `hexdump` | Hex + ASCII dump | yes | yes |

The **Lines** field (default: 200) controls how many lines `head`, `tail`, and `hexdump` fetch.

#### Editors

Open local files directly in a full terminal editor:

| Button | Opens |
|---|---|
| `nano` | nano in a new terminal window |
| `vim` | vim in a new terminal window |
| `vim read-only` | vim with `-R` flag : safe browsing, no accidental writes |

> Editor buttons work on **local files only**. To edit an HDFS file: GET it to local, edit it, PUT it back.

The app tries terminal emulators in this order: `xterm` → `gnome-terminal` → `konsole` → `xfce4-terminal` → `lxterminal`. Install xterm if you have none:

```bash
sudo apt install xterm
```

#### Search

Type a term in the **Search** box and press Enter or click **Find**. All matches are highlighted in yellow and the view scrolls to the first one. The status bar shows how many matches were found.

#### Other Controls

| Button | Action |
|---|---|
| `Clear` | Wipe the output area |
| `Save` | Save the current output to a local file |
| `Stop tail` | Stop a running `tail -f` stream |

---

### Tab 4 : Terminal

Run any shell or HDFS command without leaving the app.

#### Quick Command Buttons

| Button | Command |
|---|---|
| `dfs -ls /` | List HDFS root directory |
| `dfs report` | `hdfs dfsadmin -report` : cluster health summary |
| `fs -df -h /` | HDFS total capacity and usage |
| `dfs -du -h /` | Per-directory sizes under HDFS root |
| `yarn node list` | List all YARN NodeManagers |
| `yarn apps` | All YARN applications (all states) |
| `jps` | Running Java processes |
| `HDFS fsck` | Filesystem check (first 50 lines) |

#### Shell Bar

Type any command and press **Enter** or click **RUN**:

```bash
hdfs dfs -ls /user/hadoop/data
hdfs dfs -du -h /warehouse
yarn application -kill application_1234567890_0001
hdfs fsck /user/hadoop -files -blocks
cat /etc/hadoop/core-site.xml
echo $HADOOP_HOME
```

- **Up arrow** : recall the previous command
- **Down arrow** : go forward through history
- **Clear** : wipe the output log

All commands run in a background thread so the UI stays responsive.

---

## Keyboard Shortcuts

| Key | Context | Action |
|---|---|---|
| `Enter` | PATH bar | Navigate to typed path |
| `Enter` | Terminal input | Run command |
| `Up / Down` | Terminal input | Browse command history |
| `Ctrl + Click` | File tree | Multi-select items |
| `Shift + Click` | File tree | Range-select items |
| `Double-click` | Directory | Navigate into it |
| `Double-click` | File | Open in Viewer and cat immediately |

---

## Architecture

```
hdfs_manager.py  (single file, no dependencies beyond stdlib + tkinter)
│
├── IconButton          Styled button with hover effect
├── LogPanel            Thread-safe scrollable log widget
├── StatusBar           Live clock + status message at the bottom
│
├── ServicesTab         Hadoop daemon control + jps monitor
│
├── FilePaneBase        Shared treeview, navigation, multi-select
│   ├── LocalPane       Local filesystem browser + CRUD operations
│   └── HDFSPane        HDFS browser + hdfs dfs operations
│
├── TransferTab         Dual-pane layout + PUT/GET transfer engine
├── ViewerTab           File viewer, editor launcher, search
├── TerminalTab         Shell runner with preset buttons + history
│
└── HDFSManagerApp      Root Tk window, notebook tabs, wires everything together
```

All long-running operations : service start/stop, HDFS directory listing, file transfers, view commands : run in **daemon threads**. UI updates are posted back to the main thread via `widget.after(0, fn)`, so the app never freezes or blocks.

---

## Troubleshooting

**`no display name and no $DISPLAY variable`**  
You are in an SSH session without X11 forwarding. Reconnect with `ssh -X user@server`.

**HDFS commands return `command not found`**  
Make sure `$HADOOP_HOME/bin` and `$HADOOP_HOME/sbin` are on your `$PATH` before launching the app. Source your `.bashrc` or export the variables first.

**nano/vim buttons say "No terminal found"**  
Install xterm: `sudo apt install xterm`

**`character U+XXXXX is above the range allowed by Tcl`**  
Your Python 3.7 Tcl/Tk does not support emoji. Make sure you are using the latest version of this file : it uses only ASCII characters.

**`RuntimeError: main thread is not in main loop`**  
A background thread made a direct tkinter call. All updates from threads must go through `widget.after(0, fn)`. Please open an issue if you encounter this.

---

## Contributing

Pull requests are welcome. A few guidelines:

- Target **Python 3.7** : avoid walrus operator, f-string `=` syntax, or anything from 3.8+.
- No characters above **U+FFFF** in string literals : Python 3.7's Tcl/Tk will crash with them.
- All tkinter updates that happen inside a thread **must** use `widget.after(0, fn)`.
- Keep it a **single file** with zero third-party dependencies.

---

## License

MIT : use it, modify it, ship it.
