# -*- coding: utf-8 -*-
"""复现 Windows(中文区域)下 subprocess(text=True) 解码 ffprobe UTF-8 输出的崩溃。

关键点: 读取管道的线程一旦抛 UnicodeDecodeError, cp.stdout 直接变成 None,
于是下游 json.loads("{}") -> 没有 stream -> 报 "no video stream found"。
"""
import json
import locale
import subprocess
import sys
import tempfile
import os

print("preferred encoding:", locale.getpreferredencoding())

# 子进程: 往 stdout 写一段 UTF-8 字节, 其中含 cp936 无法解码的字节序列
child = r'''
import sys
data = (b'{"title": "\xe7\x94\x9f\xe5\x8c\x96\xe5\x8d\xb1\xe6\x9c\xba'
        + b'x' * 4088 + b'\xa2\x20' + b'", "n": 1}')
sys.stdout.buffer.write(data)
'''
tmp = os.path.join(tempfile.gettempdir(), "_gbk_child.py")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(child)


def run(label, **kw):
    print("\n" + label)
    cp = subprocess.run([sys.executable, tmp], capture_output=True, check=False, **kw)
    print("  stdout =", repr(cp.stdout)[:70])
    if cp.stdout is None:
        print("  -> stdout is None !! 下游 json.loads 会得到 {} -> 报 'no video stream found'")
    elif cp.stdout:
        try:
            print("  parsed title =", json.loads(cp.stdout)["title"])
        except Exception as ex:
            print("  parse failed:", ex)
    if cp.stderr:
        print("  stderr tail:", cp.stderr.decode("utf-8", "replace").strip().splitlines()[-1])


run("[A] text=True, 无 encoding  (main.py 现在的写法)", text=True)
run("[B] encoding='utf-8', errors='replace'  (建议的写法)", encoding="utf-8", errors="replace")
run("[C] 不做文本解码, 手动 json.loads(bytes)  (ffmpeg.probe 的做法)")