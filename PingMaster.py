#!/usr/bin/env python3
"""
PingMaster - 带 GUI 的 Ping & 端口检测工具
用法: python PingMaster.py
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import threading
import re
import time
import socket
import sys
import locale

# ── 浅灰主题配色 ──
C = {
    "bg":       "#dcdfe4",
    "card":     "#e8eaed",
    "input":    "#d0d3d8",
    "fg":       "#2d2d2d",
    "dim":      "#6b7280",
    "accent":   "#5b7fb5",
    "green":    "#6ea87a",
    "red":      "#c76b6b",
    "yellow":   "#b8a04e",
    "blue":     "#5a9ab5",
    "border":   "#b8bcc2",
}

FF = "Consolas" if sys.platform == "win32" else "Monospace"
FN = (FF, 11)
FB = (FF, 11, "bold")
FT = (FF, 14, "bold")
FM = (FF, 10)


class PingApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PingMaster  By_Jace")
        self.root.geometry("860x680")
        self.root.resizable(False, False)
        self.root.configure(bg=C["bg"])

        self.running = False
        self.process = None
        self.sent = 0
        self.recv = 0
        self.rtts = []
        self.start_time = 0

        self._build_ui()
        self.root.bind("<Return>", lambda e: self._start())
        self.root.bind("<Escape>", lambda e: self._stop())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ──
    def _build_ui(self):
        tk.Frame(self.root, bg=C["accent"], height=3).pack(fill="x")

        # 标题
        bar = tk.Frame(self.root, bg=C["bg"])
        bar.pack(fill="x", padx=20, pady=(12, 4))
        tk.Label(bar, text="PingMaster", font=FT, bg=C["bg"], fg=C["accent"]).pack(side="left")
        tk.Label(bar, text="  Ping & Port Scanner", font=(FF, 10), bg=C["bg"], fg=C["dim"]).pack(side="left", pady=(4, 0))

        # 输入卡片
        card = self._card(self.root)
        card.pack(fill="x", padx=20, pady=(8, 4))

        r1 = tk.Frame(card, bg=C["card"])
        r1.pack(fill="x", padx=15, pady=(10, 4))

        tk.Label(r1, text="目标地址", font=FB, bg=C["card"], fg=C["accent"]).grid(row=0, column=0, sticky="w")
        self.ent_host = self._entry(r1, 30, "IP 或域名，如 8.8.8.8")
        self.ent_host.grid(row=1, column=0, sticky="ew", padx=(0, 12))

        tk.Label(r1, text="端口", font=FB, bg=C["card"], fg=C["accent"]).grid(row=0, column=1, sticky="w")
        self.ent_port = self._entry(r1, 10, "可选")
        self.ent_port.grid(row=1, column=1, sticky="ew", padx=(0, 12))

        tk.Label(r1, text="次数", font=FB, bg=C["card"], fg=C["accent"]).grid(row=0, column=2, sticky="w")
        self.ent_count = self._entry(r1, 8, "6")
        self.ent_count.grid(row=1, column=2, sticky="ew", padx=(0, 12))

        tk.Label(r1, text="包大小", font=FB, bg=C["card"], fg=C["accent"]).grid(row=0, column=3, sticky="w")
        self.ent_size = self._entry(r1, 8, "32")
        self.ent_size.grid(row=1, column=3, sticky="ew", padx=(0, 12))

        tk.Label(r1, text="TTL", font=FB, bg=C["card"], fg=C["accent"]).grid(row=0, column=4, sticky="w")
        self.ent_ttl = self._entry(r1, 8, "61")
        self.ent_ttl.grid(row=1, column=4, sticky="ew")

        r1.columnconfigure(0, weight=3)
        r1.columnconfigure(1, weight=1)
        r1.columnconfigure(2, weight=1)
        r1.columnconfigure(3, weight=1)
        r1.columnconfigure(4, weight=1)

        r2 = tk.Frame(card, bg=C["card"])
        r2.pack(fill="x", padx=15, pady=(4, 10))

        self.var_cont = tk.BooleanVar()
        tk.Checkbutton(r2, text="持续 Ping", variable=self.var_cont, font=FN,
                        bg=C["card"], fg=C["accent"], selectcolor=C["input"],
                        activebackground=C["card"], highlightthickness=0).pack(side="left")

        self.var_v4 = tk.BooleanVar()
        tk.Checkbutton(r2, text="强制 IPv4", variable=self.var_v4, font=FN,
                        bg=C["card"], fg=C["fg"], selectcolor=C["input"],
                        activebackground=C["card"], highlightthickness=0).pack(side="left", padx=(15, 0))

        # 按钮
        bb = tk.Frame(card, bg=C["card"])
        bb.pack(fill="x", padx=15, pady=(0, 10))

        self.btn_go = self._btn(bb, "[>] 开始", "#a3d4a8", self._start)
        self.btn_go.pack(side="left", padx=(0, 6))
        self.btn_stop = self._btn(bb, "[x] 停止", "#e0a0a0", self._stop, "disabled")
        self.btn_stop.pack(side="left", padx=(0, 6))
        self._btn(bb, "[ ] 清空", "#b8bcc2", self._clear).pack(side="left", padx=(0, 6))
        self._btn(bb, "[↓] 导出", "#b8c8e0", self._export).pack(side="left")

        # 统计栏
        sf = self._card(self.root)
        sf.pack(fill="x", padx=20, pady=4)
        si = tk.Frame(sf, bg=C["card"])
        si.pack(fill="x", padx=15, pady=8)

        self.st = {}
        for i, (k, t) in enumerate([("sent", "发送"), ("recv", "接收"), ("loss", "丢包"),
                                      ("min", "最小"), ("avg", "平均"), ("max", "最大"), ("time", "耗时")]):
            f = tk.Frame(si, bg=C["card"])
            f.grid(row=0, column=i, padx=8)
            tk.Label(f, text=t, font=(FF, 9), bg=C["card"], fg=C["dim"]).pack()
            lbl = tk.Label(f, text="0", font=FB, bg=C["card"], fg=C["fg"])
            lbl.pack()
            self.st[k] = lbl

        # 结果区
        rc = self._card(self.root)
        rc.pack(fill="both", expand=True, padx=20, pady=(4, 12))

        rh = tk.Frame(rc, bg=C["card"])
        rh.pack(fill="x", padx=15, pady=(8, 4))
        tk.Label(rh, text="[ Results ]", font=FB, bg=C["card"], fg=C["accent"]).pack(side="left")

        self.txt = tk.Text(rc, bg="#dfe2e6", fg=C["fg"], font=FM,
                            insertbackground=C["fg"], selectbackground=C["accent"],
                            relief="flat", padx=12, pady=8, wrap="word", state="disabled",
                            borderwidth=0, highlightthickness=1, highlightbackground=C["border"])
        self.txt.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        for tag, color in [("ok", C["green"]), ("fail", C["red"]),
                            ("warn", C["yellow"]), ("info", C["blue"]),
                            ("dim", C["dim"]), ("title", C["accent"])]:
            kw = {"foreground": color}
            if tag == "title":
                kw["font"] = FB
            self.txt.tag_configure(tag, **kw)

        # 状态栏
        sb = tk.Frame(self.root, bg=C["card"], height=26)
        sb.pack(fill="x", side="bottom")
        self.lbl_st = tk.Label(sb, text="就绪", font=(FF, 9), bg=C["card"], fg=C["dim"], anchor="w")
        self.lbl_st.pack(side="left", padx=15)

    def _card(self, p):
        return tk.Frame(p, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)

    def _entry(self, p, w, ph):
        e = tk.Entry(p, font=FN, width=w, bg=C["input"], fg=C["fg"],
                      insertbackground=C["fg"], relief="flat",
                      highlightthickness=1, highlightbackground=C["border"],
                      highlightcolor=C["accent"])
        e.insert(0, ph)
        e.config(fg=C["dim"])
        e._ph = ph
        e.bind("<FocusIn>", lambda ev, e=e: self._ph_in(e))
        e.bind("<FocusOut>", lambda ev, e=e: self._ph_out(e))
        return e

    def _ph_in(self, e):
        if e.get() == e._ph:
            e.delete(0, "end")
            e.config(fg=C["fg"])

    def _ph_out(self, e):
        if not e.get():
            e.insert(0, e._ph)
            e.config(fg=C["dim"])

    def _val(self, e):
        if e.cget("fg") == C["dim"]:
            return ""
        return e.get().strip()

    def _btn(self, p, text, color, cmd, state="normal"):
        b = tk.Button(p, text=text, font=FB, fg="#2d2d2d", bg=color,
                       activebackground=color, activeforeground="#2d2d2d",
                       relief="flat", padx=16, pady=4, cursor="hand2",
                       command=cmd, state=state, borderwidth=0)
        def enter(e):
            if b["state"] != "disabled":
                b.configure(bg=self._brighten_color(color))
        def leave(e):
            if b["state"] != "disabled":
                b.configure(bg=color)
        b.bind("<Enter>", enter)
        b.bind("<Leave>", leave)
        return b

    def _brighten_color(self, h):
        try:
            r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
            return f"#{min(255, r + 30):02x}{min(255, g + 30):02x}{min(255, b + 30):02x}"
        except Exception:
            return h

    # ── 逻辑 ──
    def _start(self):
        if self.running:
            return
        host = self._val(self.ent_host)
        if not host:
            messagebox.showwarning("提示", "请输入目标地址")
            self.ent_host.focus_set()
            return

        port_s = self._val(self.ent_port)
        count_s = self._val(self.ent_count) or "6"
        size_s = self._val(self.ent_size) or "32"
        ttl_s = self._val(self.ent_ttl) or "61"

        try:
            count = int(count_s)
            if count < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "次数必须是正整数"); return
        try:
            size = int(size_s)
            if not 1 <= size <= 65500:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "包大小范围 1-65500"); return
        try:
            ttl = int(ttl_s)
            if not 1 <= ttl <= 255:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "TTL 范围 1-255"); return

        port = None
        if port_s:
            try:
                port = int(port_s)
                if not 1 <= port <= 65535:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("提示", "端口范围 1-65535"); return

        self.sent = self.recv = 0
        self.rtts = []
        self.start_time = time.time()
        self.running = True
        self.btn_go.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._status(f"Pinging {host} ...", C["accent"])

        is_continuous = self.var_cont.get()

        if port:
            threading.Thread(target=self._port_check, args=(host, port), daemon=True).start()
        threading.Thread(target=self._ping, args=(host, count, size, ttl, is_continuous), daemon=True).start()
        self._tick()

    def _port_check(self, host, port):
        self._log(f"\n{'=' * 50}", "dim")
        self._log(f"  [PORT] {host}:{port}", "title")
        self._log(f"{'-' * 50}", "dim")

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        t0 = time.time()
        try:
            r = s.connect_ex((host, port))
            ms = (time.time() - t0) * 1000
            if r == 0:
                self._log(f"  [OPEN]   端口 {port} 开放  ({ms:.1f}ms)", "ok")
            else:
                self._log(f"  [CLOSED] 端口 {port} 关闭  ({ms:.1f}ms)", "fail")
        except socket.timeout:
            self._log("  [TIMEOUT] 连接超时 (3s)", "warn")
        except socket.gaierror:
            self._log("  [FAIL] 无法解析主机名", "fail")
        except Exception as e:
            self._log(f"  [FAIL] {e}", "fail")
        finally:
            s.close()
        self._log(f"{'=' * 50}\n", "dim")

    def _ping(self, host, count, size, ttl, is_continuous=False):
        cmd = ["ping"]
        if sys.platform == "win32":
            if self.var_v4.get():
                cmd.append("-4")
            if is_continuous:
                cmd += ["-t", "-l", str(size), "-i", str(ttl), host]
            else:
                cmd += ["-n", str(count), "-l", str(size), "-i", str(ttl), host]
        else:
            if self.var_v4.get():
                cmd.append("-4")
            if is_continuous:
                cmd += ["-s", str(size), "-t", str(ttl), host]
            else:
                cmd += ["-c", str(count), "-s", str(size), "-t", str(ttl), host]

        self._log(f"\n{'=' * 50}", "dim")
        self._log(f"  PING {host} ({size} bytes)", "title")
        self._log(f"{'-' * 50}", "dim")

        try:
            enc = (locale.getpreferredencoding() or "gbk") if sys.platform == "win32" else "utf-8"
            popen_kw = dict(
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding=enc, errors="replace"
            )
            if sys.platform == "win32":
                popen_kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.process = subprocess.Popen(cmd, **popen_kw)

            for line in self.process.stdout:
                if not self.running:
                    break
                line = line.strip()
                if not line:
                    continue

                # 匹配 RTT（成功响应）
                m = re.search(r'(?:time|time=|时间[<=])([\d.]+)\s*ms', line)
                if m:
                    rtt = float(m.group(1))
                    self.sent += 1
                    self.recv += 1
                    self.rtts.append(rtt)
                    tag = "ok" if rtt < 50 else ("warn" if rtt < 200 else "fail")
                    self._log(f"  {line}", tag)
                    self._update()
                    continue

                # 超时 / 不可达（失败响应）
                if any(k in line.lower() for k in ['timeout', 'timed out', '超时', 'unreachable']):
                    self.sent += 1
                    self._log(f"  {line}", "fail")
                    self._update()
                    continue

                # Windows 中文统计行（来自 ping 自身的汇总）
                if sys.platform == "win32" and '平均' in line:
                    self._log(f"  {line}", "info")
                    continue

                # 其他包含有用信息的行
                if any(k in line.lower() for k in ['ttl', 'bytes', '字节', 'from']):
                    self._log(f"  {line}", "info")
                    continue

                self._log(f"  {line}", "dim")

            self.process.wait()
            self._summary()

        except FileNotFoundError:
            self._log("  [FAIL] 系统找不到 ping 命令", "fail")
        except Exception as e:
            self._log(f"  [FAIL] {e}", "fail")
        finally:
            self.running = False
            self.root.after(0, self._done)

    def _summary(self):
        elapsed = time.time() - self.start_time
        self._log(f"\n{'-' * 50}", "dim")
        self._log("  STATISTICS", "title")

        loss = ((self.sent - self.recv) / self.sent * 100) if self.sent else 100
        tag = "ok" if loss == 0 else ("warn" if loss < 50 else "fail")
        self._log(f"  Sent={self.sent}  Recv={self.recv}  Loss={loss:.0f}%", tag)

        if self.rtts:
            avg = sum(self.rtts) / len(self.rtts)
            mn, mx = min(self.rtts), max(self.rtts)
            if len(self.rtts) > 1:
                var = sum((x - avg) ** 2 for x in self.rtts) / len(self.rtts)
                mdev = var ** 0.5
            else:
                mdev = 0
            self._log(f"  RTT: min={mn:.1f}  avg={avg:.1f}  max={mx:.1f}  mdev={mdev:.1f} ms", "info")
        else:
            self._log("  [WARN] 无响应", "fail")

        self._log(f"  Time: {elapsed:.1f}s", "dim")
        self._log(f"{'=' * 50}\n", "dim")

    def _tick(self):
        if self.running:
            self.st["time"].config(text=f"{time.time() - self.start_time:.0f}s", fg=C["blue"])
            self.root.after(500, self._tick)

    def _update(self):
        def _do():
            self.st["sent"].config(text=str(self.sent))
            self.st["recv"].config(text=str(self.recv), fg=C["green"])
            loss = ((self.sent - self.recv) / self.sent * 100) if self.sent else 0
            lc = C["green"] if loss == 0 else (C["yellow"] if loss < 50 else C["red"])
            self.st["loss"].config(text=f"{loss:.0f}%", fg=lc)
            if self.rtts:
                avg = sum(self.rtts) / len(self.rtts)
                self.st["min"].config(text=f"{min(self.rtts):.1f}ms", fg=C["green"])
                self.st["avg"].config(text=f"{avg:.1f}ms", fg=C["yellow"] if avg > 50 else C["green"])
                self.st["max"].config(text=f"{max(self.rtts):.1f}ms", fg=C["red"] if max(self.rtts) > 200 else C["yellow"])
        self.root.after(0, _do)

    def _stop(self):
        self.running = False
        self._status("正在停止...", C["yellow"])
        # 让子线程自然退出，延迟后兜底 kill
        self.root.after(500, self._force_kill)

    def _force_kill(self):
        if self.process:
            try:
                self.process.kill()
            except Exception:
                pass
        self._status("已停止", C["yellow"])

    def _done(self):
        self.btn_go.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.st["time"].config(text=f"{time.time() - self.start_time:.1f}s", fg=C["blue"])
        self._status("完成", C["green"])

    def _clear(self):
        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.config(state="disabled")
        self.sent = self.recv = 0
        self.rtts = []
        for k, v in [("sent", "0"), ("recv", "0"), ("loss", "0%"), ("min", "-"), ("avg", "-"), ("max", "-"), ("time", "0s")]:
            self.st[k].config(text=v, fg=C["fg"])
        self._status("已清空", C["dim"])

    def _export(self):
        content = self.txt.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("提示", "没有内容可导出")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._status(f"已导出: {path}", C["green"])

    def _log(self, text, tag=""):
        def _do():
            self.txt.config(state="normal")
            self.txt.insert("end", text + "\n", tag)
            self.txt.see("end")
            self.txt.config(state="disabled")
        self.root.after(0, _do)

    def _status(self, text, color=None):
        def _do():
            self.lbl_st.config(text=text)
            if color:
                self.lbl_st.config(fg=color)
        self.root.after(0, _do)

    def _on_close(self):
        self.running = False
        if self.process:
            try:
                self.process.kill()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    PingApp().run()
