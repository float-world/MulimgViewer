import wx
from ..gui.path_select_gui import PathSelectFrameGui
from .utils import get_resource_path

_PATH_SELECT_STATE = {
    "video_mode": False,
    "last_manual_paths": [],
}

class PathSelectFrame(PathSelectFrameGui):
    def __init__(self, parent, UpdateUI, get_type, title = "Parallel manual choose input directory",video_manager=None):
        super().__init__(parent)

        self.UpdateUI = UpdateUI
        self.get_type = get_type
        self.SetTitle(title)
        self.video_manager = video_manager
        self.shared_config = None
        self._last_folder_dir = ""
        self._last_video_dir = ""

        try:
            self.SetIcon(wx.Icon(get_resource_path("mulimgviewer.png"), wx.BITMAP_TYPE_PNG))
        except Exception:
            pass

        self.Bind(wx.EVT_CLOSE, self._on_close)

        if not hasattr(self, "input_paths"):
            self.input_paths = []

        self.Layout()
        # ★ 列表初始为空: 不再恢复上一次手动选择的路径。
        #   自动填充会让"这一次到底选了哪些路径"变得不明确,
        #   关闭时旧路径会被一起提交, 图片/视频模式切换时容易用错路径。
        #   用户在框里看到的内容 = 这次真正会生效的路径集合。

    def set_video_manager(self, vm, sh):
        self.video_manager = vm
        self.shared_config = sh
        # ★ 视频模式下同样不预填当前已加载的视频路径, 列表保持为空。
        #   在这里挑选的就是"这次要加载的视频集合", 不该混入上一轮的残留。

    def frame_resize(self, event):
        self.m_richText1.SetMinSize(wx.Size(self.Size.Width, self.Size.Height))
        self.Layout()
        self.Refresh()

    def refresh_txt(self, input_path=None):
        if input_path:
            text = "\n".join(str(p) for p in input_path if p)
            if hasattr(self, "m_richText1") and self.m_richText1:
                try:
                    self.m_richText1.Value = (text + "\n") if text else ""
                except RuntimeError:
                    pass

    def _finalize_and_return(self):
        """Collect selected paths, invoke callback, then close the window."""
        paths = [p for p in self.m_richText1.Value.split("\n") if p]
        if _PATH_SELECT_STATE["video_mode"]:
            # ★ 列表为空 = 这次没有选任何视频: 保持当前已加载的视频不变。
            #   以前不管列表是否为空都会覆盖 real_video_path 并重新 select_video(-1),
            #   于是"打开再关闭"这种空操作也会把视频清空并重建整条视频管线,
            #   在图片/视频模式之间切换时就会把当前画面弄坏。
            if paths:
                if self.shared_config is not None:
                    self.shared_config.real_video_path = list(paths)
                if self.video_manager is not None and getattr(self.shared_config, "video_mode", False):
                    self.video_manager.select_video(type=-1)
        else:
            _PATH_SELECT_STATE["last_manual_paths"] = list(paths)
        if self.get_type() == -1:
            self.Destroy()
        else:
            if _PATH_SELECT_STATE["video_mode"]:
                self.Destroy()
            else:
                try:
                    self.UpdateUI(0, input_path=paths)
                finally:
                    self.Destroy()

    def on_browse(self, event):
        paths = []
        if _PATH_SELECT_STATE["video_mode"]:  # Select one or more video files
            wildcard = ("Video files (*.mp4;*.avi;*.mov;*.mkv)|*.mp4;*.avi;*.mov;*.mkv|"
                        "All files (*.*)|*.*")
            # If video files were selected previously, use that as the initial directory
            last_dir = self._last_video_dir if hasattr(self, '_last_video_dir') else ""
            dlg = wx.FileDialog(None, "Select Video", last_dir,
                                wildcard=wildcard,
                                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE)
            if dlg.ShowModal() == wx.ID_OK:
                paths = dlg.GetPaths()
        else:  # Select one folder at a time; repeated browse clicks accumulate selections.
            last_dir = self._last_folder_dir if hasattr(self, '_last_folder_dir') else ""
            dlg = wx.DirDialog(self, "Select Folder", last_dir, style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
            if dlg.ShowModal() != wx.ID_OK:
                dlg.Destroy()
                return
            selected_path = dlg.GetPath()
            if selected_path:
                paths = [selected_path]
                self._last_folder_dir = selected_path
        dlg.Destroy()

        # Update selected paths in the text box
        cur = [x for x in self.m_richText1.Value.split("\n") if x]
        if paths:
            for p in paths:
                if p not in cur:
                    cur.append(p)
            self.m_richText1.Value = "\n".join(cur) + ("\n" if cur else "")
            if not _PATH_SELECT_STATE["video_mode"]:
                _PATH_SELECT_STATE["last_manual_paths"] = list(cur)

    def _on_close(self, event):
        self._finalize_and_return()

    def close(self, event):
        self._finalize_and_return()

    def Close(self, event):  # noqa: N802  Keep this name to match generated-code bindings
        self._finalize_and_return()

    def add_dir(self, event):
        p = self.m_dirPicker1.GetPath()
        if not p:
            return
        cur = [x for x in self.m_richText1.Value.split("\n") if x]
        if p not in cur:
            cur.append(p)
        self.m_richText1.Value = "\n".join(cur) + "\n"

    def add_video(self, event):
        p = self.m_filePicker1.GetPath()
        if not p:
            return
        cur = [x for x in self.m_richText1.Value.split("\n") if x]
        if p not in cur:
            cur.append(p)
        self.m_richText1.Value = "\n".join(cur) + "\n"
        self.m_filePicker1.SetPath("")

    def clear_all_path(self, event):
        self.m_richText1.Clear()

    def clear_last_path(self, event):
        cur = [x for x in self.m_richText1.Value.split("\n") if x]
        if cur:
            cur.pop()
        self.m_richText1.Value = "\n".join(cur) + ("\n" if cur else "")

def on_video_mode_change(video_mode):
        _PATH_SELECT_STATE["video_mode"] = video_mode
