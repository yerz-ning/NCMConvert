import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext
from tkinter import ttk

from src.core.constants import APP_NAME, APP_REPO
from src.core.decryptor import collect_inputs, process_files
from src.core.errors import NcmError
from src.core.settings import load_settings
from src.ui import dialogs
from src.utils.system import open_directory, open_url

TAG_OK = "#0a7d28"
TAG_BAD = "#b00020"
TAG_INFO = "#1a4f9c"
TAG_DIM = "#666666"


class GuiApp(object):
    POLL_INTERVAL_MS = 80
    MAX_LOG_LINES = 4000

    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None
        self.files = []
        self.row_ids = {}
        self.total = 0
        self.last_out_dir = ""
        self.locked_widgets = []
        self.settings = load_settings()
        self._build()
        self._log("%s 图形界面已就绪。" % APP_NAME, "info")
        self._log("请用上方按钮选择 NCM 文件或文件夹，输出目录用文件选择器指定。", "dim")
        self.root.after(self.POLL_INTERVAL_MS, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self):
        self.root.title("%s - NCM 解密工具" % APP_NAME)
        self.root.geometry("920x680")
        self.root.minsize(780, 580)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.to_source_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="就绪")

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=3)
        main.rowconfigure(3, weight=2)

        path_frame = ttk.LabelFrame(main, text="路径", padding=8)
        path_frame.grid(row=0, column=0, sticky="ew")
        path_frame.columnconfigure(1, weight=1)

        ttk.Label(path_frame, text="输入").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(path_frame, textvariable=self.input_var, state="readonly").grid(
            row=0, column=1, sticky="ew", pady=3)
        input_buttons = ttk.Frame(path_frame)
        input_buttons.grid(row=0, column=2, sticky="w", padx=(8, 0))
        button_file = ttk.Button(input_buttons, text="选择 NCM 文件", width=15,
                                 command=self.pick_file)
        button_file.pack(side="left")
        button_dir = ttk.Button(input_buttons, text="选择文件夹", width=12,
                                command=self.pick_folder)
        button_dir.pack(side="left", padx=(6, 0))

        ttk.Label(path_frame, text="输出").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(path_frame, textvariable=self.output_var, state="readonly").grid(
            row=1, column=1, sticky="ew", pady=3)
        output_buttons = ttk.Frame(path_frame)
        output_buttons.grid(row=1, column=2, sticky="w", padx=(8, 0))
        self.button_out_dir = ttk.Button(output_buttons, text="选择输出文件夹", width=15,
                                         command=self.pick_output_dir, state="disabled")
        self.button_out_dir.pack(side="left")
        self.check_to_source = ttk.Checkbutton(output_buttons, text="输出到源目录",
                                               variable=self.to_source_var,
                                               command=self._sync_output_entry)
        self.check_to_source.pack(side="left", padx=(6, 0))

        files_frame = ttk.LabelFrame(main, text="待处理文件", padding=8)
        files_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(files_frame, columns=("status", "file", "output"),
                                 show="headings", height=8)
        self.tree.heading("status", text="状态")
        self.tree.heading("file", text="文件")
        self.tree.heading("output", text="输出")
        self.tree.column("status", width=80, anchor="center", stretch=False)
        self.tree.column("file", width=420)
        self.tree.column("output", width=330)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(files_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.tag_configure("ok", foreground=TAG_OK)
        self.tree.tag_configure("bad", foreground=TAG_BAD)
        self.tree.tag_configure("busy", foreground=TAG_INFO)

        control_frame = ttk.Frame(main)
        control_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        control_frame.columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(control_frame, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(control_frame, textvariable=self.status_var).grid(row=1, column=0, sticky="w",
                                                                   pady=(4, 0))

        control_buttons = ttk.Frame(control_frame)
        control_buttons.grid(row=0, column=1, rowspan=2, sticky="e", padx=(10, 0))
        self.button_start = ttk.Button(control_buttons, text="开始解密", width=12,
                                       command=self.start)
        self.button_start.pack(side="left")
        self.button_stop = ttk.Button(control_buttons, text="停止", width=8, state="disabled",
                                      command=self.stop)
        self.button_stop.pack(side="left", padx=(6, 0))
        self.button_open = ttk.Button(control_buttons, text="打开输出目录", width=14,
                                      command=self.open_output_dir)
        self.button_open.pack(side="left", padx=(6, 0))

        log_frame = ttk.LabelFrame(main, text="运行日志", padding=8)
        log_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = scrolledtext.ScrolledText(log_frame, height=12, wrap="word")
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.tag_configure("ok", foreground=TAG_OK)
        self.log.tag_configure("bad", foreground=TAG_BAD)
        self.log.tag_configure("info", foreground=TAG_INFO)
        self.log.tag_configure("dim", foreground=TAG_DIM)
        self.log.configure(state="disabled")

        self.locked_widgets = [button_file, button_dir, self.button_out_dir,
                               self.check_to_source, self.button_start]
        self._build_menu()

    def _log(self, text, tag):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        try:
            total_lines = int(self.log.index("end-1c").split(".")[0])
        except Exception:
            total_lines = 0
        if total_lines > self.MAX_LOG_LINES:
            self.log.delete("1.0", "%d.0" % (total_lines - self.MAX_LOG_LINES + 1))
        self.log.configure(state="disabled")
        self.log.see("end")

    def _set_running(self, running):
        for widget in self.locked_widgets:
            try:
                widget.configure(state="disabled")
            except Exception:
                pass
        if running:
            self.button_stop.configure(state="normal")
        else:
            self.button_stop.configure(state="disabled")
            self.button_start.configure(state="normal")
            self._sync_output_entry()

    def _sync_output_entry(self):
        running = self.thread is not None and self.thread.is_alive()
        if self.to_source_var.get():
            self.button_out_dir.configure(state="disabled")
            source = self.input_var.get()
            if source and os.path.isdir(source):
                self.output_var.set(source)
            elif source:
                self.output_var.set(os.path.dirname(os.path.abspath(source)))
            else:
                self.output_var.set("")
        else:
            if not running:
                self.button_out_dir.configure(state="normal")

    def _clear_rows(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.row_ids = {}

    def _fill_rows(self, files):
        self._clear_rows()
        for index, path in enumerate(files):
            item = self.tree.insert("", "end", iid=str(index),
                                    values=("等待", path, ""))
            self.row_ids[path] = item

    def _set_row(self, path, status, output="", tag=""):
        item = self.row_ids.get(path)
        if item is None:
            return
        values = list(self.tree.item(item, "values"))
        values[0] = status
        if output:
            values[2] = output
        self.tree.item(item, values=values, tags=((tag,) if tag else ()))

    def pick_file(self):
        path = filedialog.askopenfilename(
            title="选择 NCM 文件",
            filetypes=[("NCM 音乐文件", "*.ncm"), ("所有文件", "*.*")])
        if not path:
            return
        self.input_var.set(path)
        self.scan(path)

    def pick_folder(self):
        path = filedialog.askdirectory(title="选择包含 NCM 文件的文件夹")
        if not path:
            return
        self.input_var.set(path)
        self.scan(path)

    def pick_output_dir(self):
        path = filedialog.askdirectory(title="选择输出文件夹")
        if not path:
            return
        self.output_var.set(path)
        self.last_out_dir = path

    def scan(self, path):
        try:
            files = collect_inputs(path)
        except NcmError as exc:
            self.files = []
            self._clear_rows()
            self._log("[错误] %s" % exc, "bad")
            messagebox.showerror(APP_NAME, str(exc))
            return
        self.files = files
        self._fill_rows(files)
        self._sync_output_entry()
        if not files:
            self._log("未找到可处理的 .ncm 文件: %s" % path, "bad")
            messagebox.showinfo(APP_NAME, "该路径下没有找到 .ncm 文件。")
            return
        self.total = len(files)
        self.progress.configure(maximum=100, value=0)
        self.status_var.set("已选择 %d 个文件，点击“开始解密”执行" % len(files))
        self._log("共找到 %d 个待处理文件" % len(files), "info")

    def open_output_dir(self):
        target = self.output_var.get() or self.last_out_dir
        if not target or not os.path.isdir(target):
            messagebox.showinfo(APP_NAME, "输出目录尚未生成。")
            return
        try:
            open_directory(target)
        except Exception as exc:
            messagebox.showerror(APP_NAME, "无法打开目录 %s: %s" % (target, exc))

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return
        if not self.files:
            messagebox.showinfo(APP_NAME, "请先选择 NCM 文件或文件夹。")
            return
        out_dir = "" if self.to_source_var.get() else self.output_var.get()
        if not self.to_source_var.get() and not out_dir:
            messagebox.showinfo(APP_NAME, "请用“选择输出文件夹”指定输出目录。")
            return
        if not self.to_source_var.get() and not os.path.isdir(out_dir):
            messagebox.showerror(APP_NAME, "输出目录不存在: %s" % out_dir)
            return

        self.last_out_dir = out_dir or (os.path.dirname(os.path.abspath(self.files[0]))
                                        if self.files else "")
        self.stop_event.clear()
        self.total = len(self.files)
        self._fill_rows(self.files)
        self.progress.configure(maximum=100, value=0)
        self.status_var.set("正在处理 0/%d" % self.total)
        self._log("开始解密，共 %d 个文件" % self.total, "info")
        self._set_running(True)

        files = list(self.files)
        self.thread = threading.Thread(target=self._worker, args=(files, out_dir), daemon=True)
        self.thread.start()

    def stop(self):
        if self.thread is not None and self.thread.is_alive():
            self.stop_event.set()
            self._log("已发送停止指令，等待当前文件处理结束……", "info")

    def _worker(self, files, out_dir):
        def on_total(total):
            self.events.put(("total", total))

        def on_start(path):
            self.events.put(("begin", path))

        def on_success(info):
            self.events.put(("ok", info))

        def on_failure(path, exc):
            self.events.put(("bad", (path, str(exc))))

        def on_progress(done, total, success, failed):
            self.events.put(("progress", (done, total, success, failed)))

        try:
            summary = process_files(files, out_dir, on_total=on_total, on_start=on_start,
                                    on_success=on_success, on_failure=on_failure,
                                    on_progress=on_progress,
                                    should_stop=self.stop_event.is_set,
                                    embed_cover=bool(self.settings.get("embed_cover", True)))
            self.events.put(("done", summary))
        except Exception as exc:
            self.events.put(("fatal", str(exc)))

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        except Exception as exc:
            self._log("[内部错误] %s" % exc, "bad")
        self.root.after(self.POLL_INTERVAL_MS, self._poll)

    def _handle(self, kind, payload):
        if kind == "total":
            self.total = payload
            return
        if kind == "begin":
            self._set_row(payload, "处理中", tag="busy")
            return
        if kind == "ok":
            info = payload
            self._set_row(info["input"], "成功", info["output"], tag="ok")
            self._log("[成功] %s" % info["input"], "ok")
            self._log("        输出: %s" % info["output"], "dim")
            if info["cover_embedded"]:
                self._log("        封面: %s" % info["cover"], "dim")
            elif info["cover"]:
                self._log("        封面: %s" % info["cover"], "bad")
            meta = info["meta"]
            if meta["musicName"]:
                artist = meta["artist"] or "未知歌手"
                self._log("        曲目: %s - %s" % (meta["musicName"], artist), "dim")
            return
        if kind == "bad":
            path, reason = payload
            self._set_row(path, "失败", tag="bad")
            self._log("[失败] %s" % path, "bad")
            self._log("        原因: %s" % reason, "bad")
            return
        if kind == "progress":
            done, total, success, failed = payload
            percent = (done * 100.0 / total) if total else 0
            self.progress.configure(value=percent)
            self.status_var.set("已处理 %d/%d，成功 %d，失败 %d" % (done, total, success, failed))
            return
        if kind == "done":
            summary = payload
            self.progress.configure(value=100 if summary["total"] else 0)
            self._set_running(False)
            self.thread = None
            self._log("处理完成: 共 %d 个文件, 成功 %d 个, 失败 %d 个" % (
                summary["total"], summary["success"], summary["failed"]),
                "ok" if summary["failed"] == 0 else "bad")
            if summary["canceled"]:
                self._log("任务已被用户停止。", "info")
            self.status_var.set("完成：成功 %d，失败 %d" % (summary["success"], summary["failed"]))
            if summary["failed"] > 0:
                messagebox.showwarning(APP_NAME, "处理完成：成功 %d 个，失败 %d 个。\n"
                                       "失败原因见日志窗口。" % (summary["success"], summary["failed"]))
            else:
                messagebox.showinfo(APP_NAME, "处理完成：成功 %d 个。" % summary["success"])
            return
        if kind == "fatal":
            self._set_running(False)
            self.thread = None
            self._log("[错误] %s" % payload, "bad")
            messagebox.showerror(APP_NAME, str(payload))
            return

    def _on_close(self):
        if self.thread is not None and self.thread.is_alive():
            if not messagebox.askyesno(APP_NAME, "任务正在运行，确定要退出吗？"):
                return
            self.stop_event.set()
        self.root.destroy()

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="设置...", command=self.open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="打开输出目录", command=self.open_output_dir)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于 %s" % APP_NAME, command=self.open_about)
        help_menu.add_command(label="项目仓库", command=lambda: open_url(APP_REPO))
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.menu = menubar
        self.root.configure(menu=menubar)

    def open_about(self):
        dialogs.show_about(self.root, log=self._log)

    def open_settings(self):
        dialogs.show_settings(self.root, self.settings, on_saved=self._on_settings_saved,
                              log=self._log)

    def _on_settings_saved(self, data):
        self.settings = data
