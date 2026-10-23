# -*- coding: utf-8 -*-
"""复现 3: 点按钮之后, refresh() 那套 Layout/Refresh/Freeze-Thaw 会不会把焦点弹回文本框。

MulimgViewer 的 refresh() 会走
    show_img_init() -> set_img_layout() -> Layout()
    display_bitmap() -> _setup_img_panel() -> Freeze()/Thaw()/Layout()
这里把这一串放进按钮回调, 看焦点最后落在哪。
"""
import wx

app = wx.App()
frame = wx.Frame(None, -1, "probe3", size=(360, 160))
panel = wx.Panel(frame)
txt = wx.TextCtrl(panel, wx.ID_ANY, "2", pos=(20, 20), size=(60, -1))
btn = wx.Button(panel, wx.ID_ANY, "refresh", pos=(140, 20))
sizer = wx.BoxSizer(wx.HORIZONTAL)
sizer.Add(txt, 0, wx.ALL, 5)
sizer.Add(btn, 0, wx.ALL, 5)
panel.SetSizer(sizer)

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


def fake_refresh():
    # 复刻 refresh() 的重活
    panel.Layout()
    frame.Layout()
    frame.Refresh()
    try:
        panel.Freeze()
        panel.SetSize(panel.GetSize())
        panel.Layout()
        panel.Thaw()
    except Exception:
        pass


def on_button(e):
    describe("in button handler")
    fake_refresh()
    describe("after Layout/Refresh")
    wx.CallLater(60, lambda: describe("60ms after click"))


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
wx.CallLater(1100, frame.Close)
frame.Show()
app.MainLoop()
print("final commits:", state["commits"], "committed:", state["value"])