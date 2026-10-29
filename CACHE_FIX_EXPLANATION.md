# 视频模式缓存数量不对问题修复说明

## 问题描述
- **现象**：设置缓存数为2，浏览第9帧时，期望缓存 `[7, 8, 9, 10, 11]`（5张），实际只有 `[8, 9, 10, 11]`（4张）
- **缺失**：第7帧总是少掉
- **原因**：缓存窗口计算中的范围不一致

## 根本原因分析

### 原有代码的问题

```python
# 原有的错误逻辑
extract_end = min(local_b + R, max_batch - 1)  # 只往后取R个
stitch_end = extract_end                        # stitch_end与extract_end相同
prev_guard = R
window_start = max(0, local_b - prev_guard)
window_end = extract_end                        # window_end与extract_end相同
```

问题在于：

1. **第2部分（历史帧）的条件检查**
   ```python
   for t in range(window_start, local_b):
       if t <= stitch_end:  # ← 这个条件有问题
           if self._cached_batch_path(global_t) is None:
               self._stitch_batch(...)
   ```
   - 当前向后计算 `extract_end` 时没有考虑向前的完整范围
   - 在特定的 batch 位置和 max_batch 值的组合下，可能导致 `stitch_end < window_start` 的某些值
   - 历史帧循环因为条件 `t <= stitch_end` 可能被完全跳过

2. **第3部分（未来帧）的范围问题**
   ```python
   for t in range(local_b + 1, extract_end + 1):
   ```
   - 使用 `extract_end` 而不是完整的 `window_end`
   - 当 `window_end < extract_end`（不会发生，但逻辑不清晰）

3. **缓存窗口定义不一致**
   - 短路检查 `_display_cache_ready` 检查的是 `[local_b - R, local_b + R]`
   - 但实际拼接的范围定义不明确，导致某些批次被遗漏

## 修复方案

### 关键改变

**1. 统一窗口定义**
```python
window_start = max(0, local_b - R)              # 历史范围起点
window_end = min(local_b + R, max_batch - 1)   # 窗口范围终点
extract_end = window_end                         # 统一使用window_end
stitch_end = window_end                          # 统一使用window_end
```

**2. 简化历史帧拼接逻辑**
```python
# 移除了不必要的 if t <= stitch_end 条件
for t in range(window_start, local_b):
    self._ensure_batch_extracted(video_idx, t, wait=True)
    global_t = (base_global + t) if parallel_to_seq else t
    if self._cached_batch_path(global_t) is None:
        self._stitch_batch(video_idx, t, global_t)
```
- 因为 `window_start` 已经是窗口的有效范围，所以所有历史帧都必须拼接

**3. 修正未来帧拼接范围**
```python
for t in range(local_b + 1, window_end + 1):
    # 确保拼接到整个窗口的末端
```

**4. 简化当前帧拼接**
```python
if self._cached_batch_path(global_local) is None:
    self._stitch_batch(video_idx, local_b, global_local)
# 移除了 if local_b <= stitch_end 的条件
```

## 边界情况处理

### 1. 接近视频开头（local_b < R）
```
local_b = 1, R = 2
window_start = max(0, 1-2) = 0  ✓ 正确截断
window_end = min(1+2, max_batch-1) = 3
窗口 = [0, 1, 2, 3]  ✓ 正确
```

### 2. 接近视频结尾（local_b + R > max_batch - 1）
```
local_b = 9, R = 2, max_batch = 11
window_end = min(9+2, 11-1) = min(11, 10) = 10
窗口 = [7, 8, 9, 10]  ✓ 正确截断
```

### 3. 并行转串行模式
- 磁盘清理范围使用全局批次号计算：`(base_global + window_start)` 到 `(base_global + window_end)`
- 这部分逻辑已正确，保持不变

## 验证方法

1. **设置缓存数为2**，浏览不同位置的视频：
   - 浏览第5帧（靠近开头）：应该缓存 [0, 1, 2, 3, 4, 5, 6]（考虑边界截断）
   - 浏览第9帧（中间位置）：应该缓存 [7, 8, 9, 10, 11]
   - 浏览最后一帧：应该缓存 [最后-4, 最后-3, 最后-2, 最后-1, 最后]（考虑边界截断）

2. **检查磁盘缓存文件**：
   - 看 `Video_frames/stitch_cache/` 目录
   - batch_*.png 文件数量应该符合期望（少于等于 2R+1 = 5 张）

3. **检查内存缓存**：
   - debug_video 日志会显示 `[CacheSchedule] window=[...]`
   - window 范围应该是 `[b-R, b+R]` 或考虑边界的截断版本

## 其他不受影响的功能

✓ 图像模式（image mode）
✓ 多视频模式（multi-video mode）
✓ 并行转串行模式（parallel_to_sequential）
✓ 抽帧（skip_frames）功能
✓ 性能监控
✓ 线程动态调整

所有这些功能仍然继续工作，因为修复只涉及单视频模式下缓存窗口的一致性。
