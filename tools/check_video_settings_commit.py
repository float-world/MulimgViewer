# -*- coding: utf-8 -*-
"""验证视频设置数值框的提交逻辑 (_commit_video_settings)。

覆盖用户反馈的现象:
  - 改了 Cached Frames 之后刷新到底有没有真正生效;
  - 输入非法内容时会不会静默保留旧值 (以前的 int() 会在事件处理里抛异常);
  - 输入框里显示的是不是当前真正生效的值。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "mulimgviewer", "src"))
import main as M  # noqa: E402


class FakeTextCtrl:
    def __init__(self, value):
        self.value = str(value)

    def GetValue(self):
        return self.value

    def SetValue(self, v):
        self.value = str(v)


class FakeImgManager:
    def __init__(self):
        self.skip = 0


def make_host(interval="1.0", threads="4", cache="2", skip="0"):
    host = type("H", (), {})()
    host.shared_config = M.SharedConfig()
    host.ImgManager = FakeImgManager()
    host.m_textCtrl28 = FakeTextCtrl(interval)
    host.m_textCtrl29 = FakeTextCtrl(threads)
    host.m_textCtrl30 = FakeTextCtrl(cache)
    host.m_textCtrl281 = FakeTextCtrl(skip)
    host.video_manager = None
    return host


def commit(host):
    M.MulimgViewer._commit_video_settings(host)
    return host.shared_config


print("=" * 66)
print("场景 A: 正常修改 Cached Frames")
print("=" * 66)
h = make_host()
h.m_textCtrl30.SetValue("6")
cfg = commit(h)
print(f"  输入 6      -> cache_num = {cfg.cache_num}, 框里显示 = {h.m_textCtrl30.GetValue()!r}")
assert cfg.cache_num == 6, "Cached Frames 没有提交"
assert h.m_textCtrl30.GetValue() == "6"

print()
print("=" * 66)
print("场景 B: 非法输入 (以前 int() 抛异常, 值悄悄保持旧的)")
print("=" * 66)
for bad in ("abc", "", "3.5", "-1", "0", "  "):
    h = make_host(cache="2")
    h.m_textCtrl30.SetValue(bad)
    cfg = commit(h)
    shown = h.m_textCtrl30.GetValue()
    print(f"  输入 {bad!r:8} -> cache_num = {cfg.cache_num}, 框里显示 = {shown!r}")
    assert cfg.cache_num >= 1, f"{bad!r} 应该回退到合法值"
    assert shown == str(cfg.cache_num), "框里显示的和生效的不一致"

print()
print("=" * 66)
print("场景 C: 线程数 / 跳过帧数 / 间隔 一起提交")
print("=" * 66)
h = make_host()
h.m_textCtrl29.SetValue("8")
h.m_textCtrl281.SetValue("3")
h.m_textCtrl28.SetValue("0.5")
cfg = commit(h)
print(f"  threads={cfg.thread}  skip={cfg.skip_frames}  interval={cfg.interval}  "
      f"ImgManager.skip={h.ImgManager.skip}")
assert cfg.thread == 8
assert cfg.skip_frames == 3 and h.ImgManager.skip == 3
assert abs(cfg.interval - 0.5) < 1e-9

print()
print("=" * 66)
print("场景 D: 刷新前提交 (模拟 refresh() 开头的 _commit_video_settings)")
print("=" * 66)
h = make_host()
h.m_textCtrl30.SetValue("9")
cfg = commit(h)
print(f"  刷新时读到 cache_num = {cfg.cache_num}")
assert cfg.cache_num == 9, "刷新时用的还是旧值"

print()
print("ALL TESTS PASSED")