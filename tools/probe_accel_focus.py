# -*- coding: utf-8 -*-
"""复现 2: 加上 MulimgViewer 的加速键表守卫。

这个 app 在每个 TextCtrl 上绑了
    EVT_SET_FOCUS  -> SetAcceleratorTable(Null)
    EVT_KILL_FOCUS -> SetAcceleratorTable(acceltbl)
看看点按钮之后焦点会不会被弹回文本框 (光标留在框里)。
"""
import wx

app = wx.App()
frame = wx.Frame(None, -1, "probe2", size=(360, 140))
panel = wx.Panel(frame)
txt = wx.TextCtrl(panel, wx.ID_ANY, "2", pos=(20, 20), size=(60, -1))
btn = wx.Button(panel, wx.ID_ANY, "refresh", pos=(140, 20))

acceltbl = wx.AcceleratorTable([(wx.ACCEL_CTRL, ord("R"), 1001)])
frame.SetAcceleratorTable(acceltbl)

state = {"commits": 0, "value": None}


def disable_accel(event):
    frame.SetAcceleratorTable(wx.NullAcceleratorTable)
    event.Skip()


def enable_accel(event):
    state["commits"] += 1
    state["value"] = txt.GetValue()
    frame.SetAcceleratorTable(acceltbl)
    event.Skip()


txt.Bind(wx.EVT_SET_FOCUS, disable_accel)
txt.Bind(wx.EVT_KILL_FOCUS, enable_accel)


def describe(tag):
    focus = wx.Window.FindFocus()
    kind = type(focus).__name__ if focus is not None else "None"
    print(f"  [{tag}] focus={kind} commits={state['commits']} "
          f"committed={state['value']!r}")


def on_button(e):
    describe("in button handler")
    wx.CallLater(50, lambda: describe("50ms after click"))


btn.Bind(wx.EVT_BUTTON, on_button)


def simulate_click():
    txt.SetFocus()
    txt.SetValue("8")
    describe("before click")
    sim = wx.UIActionSimulator()
    sx, sy = btn.GetScreenPosition()
    sw, sh = btn.GetSize()
    sim.MouseMove(sx + sw // 2, sy + sh // 2)
    sim.MouseDown()
    sim.MouseUp()


wx.CallLater(400, simulate_click)
wx.CallLater(1000, frame.Close)
frame.Show()
app.MainLoop()
print("final commits:", state["commits"], "committed:", state["value"])