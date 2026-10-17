import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from src.core.constants import (
    APP_AUTHOR,
    APP_HOMEPAGE,
    APP_LICENSE,
    APP_NAME,
    APP_REPO,
    APP_SUMMARY,
    APP_VERSION,
    DEFAULT_SETTINGS,
)
from src.core.errors import NcmError
from src.core.settings import config_path, save_settings
from src.utils.system import open_url

LINK_COLOR = "#1a4f9c"


def _dialog(parent, title, width, height):
    window = tk.Toplevel(parent)
    window.title(title)
    window.transient(parent)
    window.resizable(False, False)
    parent.update_idletasks()
    left = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    top = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    if left < 0:
        left = 0
    if top < 0:
        top = 0
    window.geometry("%dx%d+%d+%d" % (width, height, left, top))
    try:
        window.grab_set()
    except Exception:
        pass
    return window


def _report(log, text):
    if log is not None:
        log(text, "dim")


def _link_row(parent, row, name, url):
    ttk.Label(parent, text=name).grid(row=row, column=0, sticky="e", padx=(0, 10), pady=3)
    link = tk.Label(parent, text=url, fg=LINK_COLOR, cursor="hand2")
    link.configure(font=("TkDefaultFont", 9, "underline"))
    link.grid(row=row, column=1, sticky="w", pady=3)
    link.bind("<Button-1>", lambda event: open_url(url))
    ttk.Button(parent, text="打开", width=6, command=lambda: open_url(url)).grid(
        row=row, column=2, sticky="w", padx=(10, 0), pady=3)


def _copy_text(window, text, log=None):
    try:
        window.clipboard_clear()
        window.clipboard_append(text)
    except Exception:
        return
    _report(log, "已复制到剪贴板: %s" % text)


def show_about(parent, log=None):
    window = _dialog(parent, "关于 %s" % APP_NAME, 640, 380)
    frame = ttk.Frame(window, padding=14)
    frame.pack(fill="both", expand=True)
    title = tk.Label(frame, text=APP_NAME, font=("TkDefaultFont", 16, "bold"), fg=LINK_COLOR)
    title.grid(row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(frame, text=APP_SUMMARY).grid(row=1, column=0, columnspan=3, sticky="w",
                                            pady=(4, 12))
    rows = [("软件名称", APP_NAME), ("版本", APP_VERSION), ("作者", APP_AUTHOR),
            ("开源协议", APP_LICENSE)]
    row = 2
    for name, value in rows:
        ttk.Label(frame, text=name).grid(row=row, column=0, sticky="e", padx=(0, 10), pady=3)
        ttk.Label(frame, text=value).grid(row=row, column=1, columnspan=2, sticky="w", pady=3)
        row += 1
    _link_row(frame, row, "GitHub 主页", APP_HOMEPAGE)
    _link_row(frame, row + 1, "项目仓库", APP_REPO)
    button_bar = ttk.Frame(frame)
    button_bar.grid(row=row + 2, column=0, columnspan=3, sticky="e", pady=(18, 0))
    ttk.Button(button_bar, text="复制仓库链接", width=14,
               command=lambda: _copy_text(window, APP_REPO, log)).pack(side="left", padx=(0, 8))
    ttk.Button(button_bar, text="关闭", width=10, command=window.destroy).pack(side="left")


def show_settings(parent, settings, on_saved=None, log=None):
    window = _dialog(parent, "设置", 640, 360)
    frame = ttk.Frame(window, padding=14)
    frame.pack(fill="both", expand=True)
    cover_var = tk.BooleanVar(value=bool(settings.get("embed_cover", True)))
    json_var = tk.BooleanVar(value=bool(settings.get("meta_json", False)))
    skip_var = tk.BooleanVar(value=bool(settings.get("skip_existing", False)))
    ttk.Checkbutton(frame, text="将封面内嵌到音频文件的标签中（取消勾选则丢弃封面）",
                    variable=cover_var).grid(row=0, column=0, sticky="w", pady=4)
    ttk.Checkbutton(frame, text="导出元数据 JSON（预留项，暂不影响处理流程）",
                    variable=json_var).grid(row=1, column=0, sticky="w", pady=4)
    ttk.Checkbutton(frame, text="跳过输出目录中已存在的同名文件（预留项，暂不影响处理流程）",
                    variable=skip_var).grid(row=2, column=0, sticky="w", pady=4)
    ttk.Label(frame, text="封面写入 MP3 的 ID3v2 APIC 帧或 FLAC 的 PICTURE 块，"
                          "不再单独导出图片文件。").grid(row=3, column=0, sticky="w",
                                                          pady=(12, 0))
    ttk.Label(frame, text="设置文件: %s" % config_path()).grid(row=4, column=0, sticky="w",
                                                              pady=2)
    ttk.Label(frame, text="封面设置对之后发起的解密任务生效。").grid(row=5, column=0,
                                                                     sticky="w", pady=2)

    def reset_defaults():
        cover_var.set(bool(DEFAULT_SETTINGS["embed_cover"]))
        json_var.set(bool(DEFAULT_SETTINGS["meta_json"]))
        skip_var.set(bool(DEFAULT_SETTINGS["skip_existing"]))

    def apply_settings():
        data = {"embed_cover": bool(cover_var.get()), "meta_json": bool(json_var.get()),
                "skip_existing": bool(skip_var.get())}
        try:
            saved = save_settings(data)
        except NcmError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        if on_saved is not None:
            on_saved(data)
        _report(log, "设置已保存: %s" % saved)
        _report(log, "内嵌封面: %s" % ("是" if data["embed_cover"] else "否"))
        window.destroy()

    button_bar = ttk.Frame(frame)
    button_bar.grid(row=6, column=0, sticky="e", pady=(18, 0))
    ttk.Button(button_bar, text="恢复默认", width=10,
               command=reset_defaults).pack(side="left", padx=(0, 8))
    ttk.Button(button_bar, text="保存", width=10,
               command=apply_settings).pack(side="left", padx=(0, 8))
    ttk.Button(button_bar, text="取消", width=10, command=window.destroy).pack(side="left")
