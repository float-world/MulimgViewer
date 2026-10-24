r"""This module can be called by
`python -m <https://docs.python.org/3/library/__main__.html>`_.
"""
import sys
from pathlib import Path

import wx
import wx.lib.inspection
from PIL import ImageFile, Image

from .src.main import MulimgViewer
from .src.path_select import PathSelectFrame

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None


class GuiManager:
    def __init__(self, UpdateUI, get_type):
        self.UpdateUI = UpdateUI
        self.get_type = get_type
        self.frameDict = {}

    def GetFrame(self, type_):
        f = self.frameDict.get(type_)
        if f is None:
            f = self.CreateFrame(type_)
            self.frameDict[type_] = f
        return f

    def CreateFrame(self, type_):
        global file_name
        input_path = Path(file_name).parent if file_name else None
        if type_ == 0:
            return MulimgViewer(None, self.UpdateUI, self.get_type, default_path=input_path)
        elif type_ == 1:
            return PathSelectFrame(None, self.UpdateUI, self.get_type)
        else:
            raise ValueError(f"Unknown frame type: {type_}")


class MainAPP(wx.App):
    def OnInit(self):
        self.manager = GuiManager(self.UpdateUI, self.get_type)
        self._last_manual_paths = []
        self.frame = [None, None]
        self.frame[0] = self.manager.GetFrame(0)  # 主窗口
        self.frame[1] = self.manager.GetFrame(1)  # 选择窗口
        self.frame[0].Show()
        self.SetTopWindow(self.frame[0])
        self.type = 0  # init show MulimgViewer
        return True

    def _normalize_paths(self, paths):
        if paths is None:
            return []
        if isinstance(paths, str):
            return [paths] if paths else []
        try:
            iterable = list(paths)
        except TypeError:
            return []
        normalized = []
        for item in iterable:
            if isinstance(item, str):
                if item:
                    normalized.append(item)
            else:
                normalized.append(str(item))
        return normalized

    def UpdateUI(self, type, input_path=None, parallel_to_sequential=None, video_manager = None,shared_config=None):
        """
        type: 1=PathSelectFrame, 0=MulimgViewer, -1=全部关闭
        input_path: list[str] 或 None
        parallel_to_sequential: 保持原参数
        """
        if video_manager is not None:
            self.video_manager = video_manager
            self.shared_config = shared_config
            self.frame[1].set_video_manager(self.video_manager, self.shared_config)
        self.type = type
        self.thread = 4

        normalized_input = self._normalize_paths(input_path)
        ptos_flag = parallel_to_sequential
        if ptos_flag is None:
            frame0 = self.frame[0] if self.frame and self.frame[0] else None
            if frame0 is not None:
                shared_cfg = getattr(frame0, "shared_config", None)
                if shared_cfg is not None and hasattr(shared_cfg, "parallel_to_sequential"):
                    ptos_flag = bool(getattr(shared_cfg, "parallel_to_sequential", False))
                elif hasattr(frame0, "parallel_to_sequential"):
                    try:
                        ptos_flag = bool(frame0.parallel_to_sequential.GetValue())
                    except Exception:
                        ptos_flag = False
        if ptos_flag is None:
            ptos_flag = False
        if normalized_input:
            self._last_manual_paths = normalized_input
            if not self.frame[0].shared_config.video_mode:
                self.frame[0].ImgManager.init(normalized_input, 1, ptos_flag)
                self.frame[0].show_img_init()
                self.frame[0].ImgManager.set_action_count(0)
                self.frame[0].show_img()

        if type == -1:
            try:
                self.frame[0].close(None)
            except Exception:
                pass
            try:
                self.frame[1].close(None)
            except Exception:
                pass
            return True

        if type == 0:
            if self.frame[1]:
                self.frame[1].Show(False)
            self.frame[0].Show(True)
            self.SetTopWindow(self.frame[0])
            return True

        if type == 1:
            try:
                if self.frame[1]:
                    self.frame[1].Destroy()
            except Exception:
                pass
            self.frame[1] = None

            self.frame[1] = self.manager.CreateFrame(1)

            # ★ 路径列表不再自动填充。
            #   以前这里在没有显式 input_path 时, 会退回使用"当前已打开的路径"
            #   (ImgManager.input_path) 或者"上一次手动选择的结果"(_last_manual_paths)
            #   填进选择框 —— 于是用顺序/并行自动模式打开一个目录后再切到 parallel manual,
            #   框里会莫名其妙出现当前目录; 关闭时它又被一起提交,
            #   图片/视频模式来回切换时就会把不该用的路径带进 ImgManager。
            #   现在列表始终为空: 只有调用方显式传入 input_path 时才会预填。
            if normalized_input:
                self._last_manual_paths = normalized_input
                try:
                    self.frame[1].refresh_txt(normalized_input)
                except AttributeError:
                    self.frame[1].m_richText1.Value = "\n".join(normalized_input) + "\n"
            # 关键：重建后立刻把 vm 注入新实例
            if getattr(self, "video_manager", None) is not None:
                self.frame[1].set_video_manager(self.video_manager,self.shared_config)

            self.frame[1].Show(True)
            self.frame[1].Raise()
            self.SetTopWindow(self.frame[1])
            return True

        return True

    def get_type(self):
        return self.type

def main():
    global file_name
    file_name = sys.argv[1] if len(sys.argv) > 1 else None
    app = MainAPP()
    # 调试可打开：
    # wx.lib.inspection.InspectionTool().Show()
    app.MainLoop()


if __name__ == '__main__':
    main()
