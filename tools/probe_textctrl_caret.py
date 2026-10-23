# -*- coding: utf-8 -*-
"""最小复现: 文本框(KILL_FOCUS 才提交) + 普通 Button。

复刻 MulimgViewer 的结构, 用真实的鼠标点击模拟, 看:
  1) 点按钮后 KILL_FOCUS 有没有触发 (值有没有被提交)
  2) 焦点还留在文本框里吗 (即光标还会不会闪)
"""
import wx

app = wx.App()
frame = wx.Frame(None, -1, "probe", size=(320, 120))
panel = wx.Panel(frame)
txt = wx.TextCtrl(panel, wx.ID_ANY, "2", pos=(20, 20), size=(60, -1))
btn = wx.Button(panel, wx.ID_ANY, "refresh", pos=(120, 20))

state = {"commits": 0, "value": None}


def on_kill_focus(event):
    state["commits"] += 1
    state["value"] = txt.GetValue()
    event.Skip()


txt.Bind(wx.EVT_KILL_FOCUS, on_kill_focus)


def describe_focus(tag):
    focus = wx.Window.FindFocus()
    kind = type(focus).__name__ if focus is not None else "None"
    print(f"  [{tag}] focus={kind} "
          f"caret_shown={txt.GetCaret().IsVisible() if txt.GetCaret() else 'n/a'} "
          f"commits={state['commits']} committed_value={state['value']!r}")


def on_button(e):
    describe_focus("after button click")


btn.Bind(wx.EVT_BUTTON, on_button)


def simulate_click():
    txt.SetFocus()
    txt.SetValue("8")
    describe_focus("before click")
    sim = wx.UIActionSimulator()
    sx, sy = btn.GetScreenPosition()
    sw, sh = btn.GetSize()
    sim.MouseMove(sx + sw // 2, sy + sh // 2)
    sim.MouseDown()
    sim.MouseUp()


wx.CallLater(400, simulate_click)
wx.CallLater(900, frame.Close)
frame.Show()
app.MainLoop()
print("final commits:", state["commits"], "committed value:", state["value"])