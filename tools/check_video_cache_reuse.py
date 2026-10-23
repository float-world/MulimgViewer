# -*- coding: utf-8 -*-
"""隔离验证: 视频模式"回退"是否复用拼接缓存。

不启动 wx GUI, 只加载 main.py 里的 VideoManager, 用桩对象驱动缓存决策。
旧逻辑对照: 把 _cache_context_changed 换成原来的"非顺序前进就清空整窗"规则。
"""
import os
import sys
import tempfile
import types

PROJECT = r"e:\Program-project\tools\MulimgViewer"
SRC = os.path.join(PROJECT, "src")          # main.py 内部用相对导入, 必须按包导入
sys.path.insert(0, SRC)

workdir = tempfile.mkdtemp(prefix="mulimg_cache_test_")
os.chdir(workdir)

# 本机没装 ffmpeg-python, 这里只桩掉它(测试不抽帧, 只测缓存决策)
try:
    import ffmpeg  # noqa: F401
except ImportError:
    sys.modules["ffmpeg"] = types.ModuleType("ffmpeg")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from mulimgviewer.src import main as M  # noqa: E402
from PIL import Image  # noqa: E402


class Cfg:
    def __init__(self):
        self.video_mode = True
        self.thread = 4
        self.cache_num = 5              # 窗口半径 R
        self.count_per_action = 4
        self.skip_frames = 0
        self.parallel_to_sequential = False
        self.video_path = [os.path.join(workdir, "vidA")]
        self.real_video_path = [os.path.join(workdir, "a.mp4")]
        self.video_fps_list = [25.0]
        self.video_num_list = [100]    # 100 帧 -> 25 个 batch
        self.cache_img = []
        self.batch_idx = 0
        self.interval = 1.0
        self.debug_video = False
        self.video_last_message = ""


def make_png(gb):
    """伪造一个磁盘拼接图, 模拟 _save_image_to_disk 的结果"""
    p = os.path.join(workdir, "Video_frames", "stitch_cache", f"batch_{gb}.png")
    Image.new("RGB", (8, 8)).save(p)
    return p


def build_vm():
    cfg = Cfg()
    vm = M.VideoManager(owner=lambda: None, shared_config=cfg, ImgManager=None)
    state = {"stitch": [], "extract": 0, "disk_cleanup": 0, "mem_cleanup": 0,
             "schedule": 0, "list_missing": 0}

    def fake_stitch(v_idx, l_b, g_b):
        state["stitch"].append(g_b)
        cfg.cache_img[g_b] = make_png(g_b)

    def fake_stitch_multi(g_b):
        state["stitch"].append(g_b)
        cfg.cache_img[g_b] = make_png(g_b)

    def fake_extract(v_idx, l_b, wait=True):
        state["extract"] += 1
        return (0, 0)

    # 真实实现里 _ensure_batch_extracted 每次都要先 _list_missing_range 扫帧文件
    real_list_missing = vm._list_missing_range

    def counting_list_missing(*a, **kw):
        state["list_missing"] += 1
        return real_list_missing(*a, **kw)

    real_disk_cleanup = vm._cleanup_disk_cache_out_of_window
    real_mem_cleanup = vm._cleanup_out_of_range_cache

    def counting_disk_cleanup(*a, **kw):
        state["disk_cleanup"] += 1
        return real_disk_cleanup(*a, **kw)

    def counting_mem_cleanup(*a, **kw):
        state["mem_cleanup"] += 1
        return real_mem_cleanup(*a, **kw)

    def counting_schedule(video_idx, local_b, global_b):
        state["schedule"] += 1
        # 真实实现是丢给 stitch_executor 异步拼; 测试里抽帧是瞬时的,
        # 直接同步拼, 让前瞻窗口能真正热起来(否则测不到缓存直显)
        if global_b not in state["stitch"]:
            fake_stitch(video_idx, local_b, global_b)
        return None

    vm._list_missing_range = counting_list_missing
    vm._stitch_batch = fake_stitch
    vm._stitch_batch_multi = fake_stitch_multi
    vm._ensure_batch_extracted = fake_extract
    vm._cleanup_disk_cache_out_of_window = counting_disk_cleanup
    vm._cleanup_out_of_range_cache = counting_mem_cleanup
    vm._schedule_stitch = counting_schedule
    return cfg, vm, state


def step_to(cfg, vm, state, b):
    cfg.batch_idx = b
    for k in state:
        state[k] = [] if k == "stitch" else 0
    vm.update_cache()
    return dict(state)


# ============================================================
print("=" * 66)
print("场景 1: 新逻辑 —— 前进到 batch 12, 然后回退 3 步")
print("=" * 66)
cfg, vm, state = build_vm()
for b in range(0, 13):
    step_to(cfg, vm, state, b)
print(f"到达 batch 12, cache_img 非空条目 = {sum(1 for x in cfg.cache_img if x)}")

total = []
for b in (11, 10, 9):
    step_to(cfg, vm, state, b)
    total.append(len(state["stitch"]))
    print(f"  回退到 batch {b}: 重新拼接 {state['stitch']}  抽帧检查 {state['extract']} 次")

assert 11 not in state["stitch"], "目标批次被重新拼接了"
assert sum(total) <= 3, f"每步回退拼接过多: {total}"
print(f"PASS  回退 3 步合计重新拼接 {sum(total)} 次 (每次最多补 1 个刚进窗口的批次)\n")

# ============================================================
print("=" * 66)
print("场景 2: 旧逻辑对照 —— 同样的前进 + 回退 3 步")
print("=" * 66)
cfg2, vm2, state2 = build_vm()


def legacy_context_changed():
    """旧规则: 只有顺序前进才不复建, 其余(回退/跳页/刷新)一律清空整窗缓存"""
    last = getattr(vm2, "_last_batch", None)
    old_force = not (last is not None and cfg2.batch_idx == last + 1)
    if old_force:
        vm2._invalidate_stitch_cache()
    return old_force


vm2._cache_context_changed = legacy_context_changed

legacy_total = []
for b in range(0, 13):
    step_to(cfg2, vm2, state2, b)
for b in (11, 10, 9):
    step_to(cfg2, vm2, state2, b)
    legacy_total.append(len(state2["stitch"]))
    print(f"  回退到 batch {b}: 重新拼接 {len(state2['stitch'])} 次")

print(f"\n旧逻辑回退 3 步合计重新拼接 {sum(legacy_total)} 次, 新逻辑 {sum(total)} 次")
assert sum(legacy_total) > sum(total), "对照失败, 旧逻辑没有明显更差"
print("PASS  回退不再整窗重拼\n")

# ============================================================
print("=" * 66)
print("场景 3: 上下文变化 (改每批帧数) 必须重建, 否则显示旧尺寸图")
print("=" * 66)
cfg.count_per_action = 8
step_to(cfg, vm, state, 9)
print(f"改 count_per_action 后 batch 9 的拼接 = {state['stitch']}")
assert len(state["stitch"]) > 0, "上下文变化后没有重建"
print("PASS  上下文变化仍会重建\n")

# ============================================================
print("=" * 66)
print("场景 4: 磁盘文件被窗口清理后, 失效缓存必须被识别并重新拼接")
print("=" * 66)
cfg.count_per_action = 4
step_to(cfg, vm, state, 9)
stale_path = cfg.cache_img[9]
os.remove(stale_path)
print(f"删除 {os.path.basename(stale_path)} 后 _cached_batch_path(9) = "
      f"{M.VideoManager._cached_batch_path(vm, 9)}")
assert M.VideoManager._cached_batch_path(vm, 9) is None, "失效缓存没有被识别"
step_to(cfg, vm, state, 9)
print(f"再次请求 batch 9 -> 本次拼接 {state['stitch']}")
assert len(state["stitch"]) > 0, "缓存失效后没有重新拼接"
print("PASS  失效缓存会被识别并重建 (不会报 Load cache failed)\n")

# ============================================================
print("=" * 66)
print("场景 5: 模拟'点上一帧'——目标批次已在缓存窗口里, 各环节实际工作量")
print("=" * 66)
cfg5, vm5, state5 = build_vm()
for b in range(0, 13):
    step_to(cfg5, vm5, state5, b)

r = step_to(cfg5, vm5, state5, 11)          # 从 batch 12 点 ◀ 到 11
print(f"batch 12 -> 11  (目标批次已缓存):")
print(f"   重新拼接          = {r['stitch']}")
print(f"   抽帧入口调用      = {r['extract']}")
print(f"   抽帧缺失扫描      = {r['list_missing']}")
print(f"   磁盘缓存窗口清理  = {r['disk_cleanup']} 次")
print(f"   内存缓存窗口清理  = {r['mem_cleanup']} 次")
print(f"   异步拼接调度尝试  = {r['schedule']} 次")
cache_work = (len(r['stitch']) + r['extract'] + r['disk_cleanup'] + r['mem_cleanup'])
print(f"=> 缓存维护动作合计 = {cache_work} 次 (目标图和它的拼接结果直接复用)")
assert cache_work == 0, f"缓存已热时仍有维护动作: {r}"

# 前瞻是冷的 -> 必须走完整流程补预取
os.remove(os.path.join(workdir, "Video_frames", "stitch_cache", "batch_14.png"))
cfg5.cache_img[14] = None
r = step_to(cfg5, vm5, state5, 11)
print(f"\n前瞻 batch 14 缓存缺失 -> 短路未触发, 补拼 {r['stitch']}, 抽帧入口 {r['extract']} 次")
assert len(r['stitch']) > 0, "前瞻缺失时短路误触发, 预取会被丢掉"
assert 14 in r["stitch"], "没有补回缺失的前瞻批次"

# 历史是冷的 -> 必须走完整流程 (倒放会用到)
os.remove(os.path.join(workdir, "Video_frames", "stitch_cache", "batch_10.png"))
cfg5.cache_img[10] = None
r = step_to(cfg5, vm5, state5, 11)
print(f"历史 batch 10 缓存缺失 -> 短路未触发, 补拼 {r['stitch']}")
assert 10 in r["stitch"], "历史缺失时短路误触发, 倒放会卡在 Waiting for batch N"

# 重新热起来后再点上一帧, 仍然零维护
r = step_to(cfg5, vm5, state5, 12)
step_to(cfg5, vm5, state5, 11)
step_to(cfg5, vm5, state5, 10)
r = step_to(cfg5, vm5, state5, 9)
print(f"再次预热后 12->11->10->9 连续回退: 最后一步维护动作 = "
      f"{len(r['stitch']) + r['extract'] + r['disk_cleanup'] + r['mem_cleanup']}")
assert len(r['stitch']) == 0, "预热后回退仍在重拼"
print("ALL TESTS PASSED")