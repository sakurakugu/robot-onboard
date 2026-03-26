"""静态目标跟踪模块

基于初始目标框进行轻量模板匹配，适用于静止目标的本地靠近。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import cv2
import numpy as np
from sparkrobot_common import get_logger

logger = get_logger("robot-agent")


@dataclass(frozen=True)
class 归一化目标框:
    """归一化目标框，坐标范围均为 0~1。"""

    cx: float
    cy: float
    w: float
    h: float

    @property
    def area(self) -> float:
        return self.w * self.h


def 从参数解析目标框(parameters: dict) -> 归一化目标框:
    """从动作参数中解析归一化目标框。"""

    if {"cx", "cy", "w", "h"} <= parameters.keys():
        return _裁剪归一化目标框(
            归一化目标框(
                cx=float(parameters["cx"]),
                cy=float(parameters["cy"]),
                w=float(parameters["w"]),
                h=float(parameters["h"]),
            )
        )

    if {"x1", "y1", "x2", "y2"} <= parameters.keys():
        x1 = float(parameters["x1"])
        y1 = float(parameters["y1"])
        x2 = float(parameters["x2"])
        y2 = float(parameters["y2"])
        return _从角点生成目标框(x1, y1, x2, y2)

    if {"left", "top", "right", "bottom"} <= parameters.keys():
        return _从角点生成目标框(
            float(parameters["left"]),
            float(parameters["top"]),
            float(parameters["right"]),
            float(parameters["bottom"]),
        )

    if {"x", "y", "w", "h"} <= parameters.keys():
        x = float(parameters["x"])
        y = float(parameters["y"])
        w = float(parameters["w"])
        h = float(parameters["h"])
        return _裁剪归一化目标框(
            归一化目标框(
                cx=x + w / 2.0,
                cy=y + h / 2.0,
                w=w,
                h=h,
            )
        )

    raise ValueError("缺少目标框参数，请提供 cx/cy/w/h、x1/y1/x2/y2、left/top/right/bottom 或 x/y/w/h")


def 打开视频流(rtsp_url: str, timeout: int = 5) -> cv2.VideoCapture:
    """打开 RTSP 视频流。"""

    cap = cv2.VideoCapture(rtsp_url + "?tcp", cv2.CAP_FFMPEG)
    if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)
    return cap


def 读取最新视频帧(cap: cv2.VideoCapture, warmup_reads: int = 0) -> Optional[np.ndarray]:
    """读取尽量新的帧，必要时先丢弃几帧缓冲。"""

    frame: Optional[np.ndarray] = None
    for _ in range(max(1, warmup_reads + 1)):
        ok, current = cap.read()
        if not ok or current is None:
            continue
        frame = current
    return frame


class 静态目标跟踪器:
    """基于模板匹配的静态目标跟踪器。"""

    def __init__(
        self,
        initial_bbox: 归一化目标框,
        search_margin: float = 1.8,
        scale_factors: Iterable[float] = (0.9, 0.96, 1.0, 1.08, 1.16),
        min_score: float = 0.18,
        template_update_rate: float = 0.2,
    ) -> None:
        self.initial_bbox = _裁剪归一化目标框(initial_bbox)
        self.search_margin = max(1.1, min(search_margin, 3.5))
        self.scale_factors = tuple(scale_factors)
        self.min_score = max(-1.0, min(min_score, 1.0))
        self.template_update_rate = max(0.0, min(template_update_rate, 1.0))
        self._template_gray: Optional[np.ndarray] = None
        self._current_rect: Optional[tuple[int, int, int, int]] = None

    def 初始化(self, frame: np.ndarray) -> 归一化目标框:
        """根据首帧和初始框建立模板。"""

        frame_h, frame_w = frame.shape[:2]
        rect = self._normalized_to_rect(self.initial_bbox, frame_w, frame_h)
        template = self._extract_patch(frame, rect)
        if template is None:
            raise ValueError("初始目标框无效，无法截取模板")

        gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        if gray.shape[0] < 8 or gray.shape[1] < 8:
            raise ValueError("初始目标框过小，无法进行稳定跟踪")

        self._template_gray = gray
        self._current_rect = rect
        return self._rect_to_normalized(rect, frame_w, frame_h)

    def 更新(self, frame: np.ndarray) -> Optional[tuple[归一化目标框, float]]:
        """在新帧中更新目标位置，返回目标框和匹配得分。"""

        if self._template_gray is None or self._current_rect is None:
            raise RuntimeError("跟踪器尚未初始化")

        frame_h, frame_w = frame.shape[:2]
        search_rect = self._build_search_rect(self._current_rect, frame_w, frame_h)
        search_patch = self._extract_patch(frame, search_rect)
        if search_patch is None:
            return None

        search_gray = cv2.cvtColor(search_patch, cv2.COLOR_BGR2GRAY)
        best_rect: Optional[tuple[int, int, int, int]] = None
        best_score = -1.0

        for scale in self.scale_factors:
            candidate = self._resize_template(self._template_gray, scale)
            if candidate is None:
                continue
            candidate_h, candidate_w = candidate.shape[:2]
            if candidate_h >= search_gray.shape[0] or candidate_w >= search_gray.shape[1]:
                continue
            result = cv2.matchTemplate(search_gray, candidate, cv2.TM_CCOEFF_NORMED)
            _, score, _, max_loc = cv2.minMaxLoc(result)
            if score > best_score:
                left = search_rect[0] + max_loc[0]
                top = search_rect[1] + max_loc[1]
                best_rect = (left, top, candidate_w, candidate_h)
                best_score = float(score)

        if best_rect is None or best_score < self.min_score:
            return None

        self._current_rect = self._smooth_rect(self._current_rect, best_rect)
        self._refresh_template(frame, self._current_rect)
        bbox = self._rect_to_normalized(self._current_rect, frame_w, frame_h)
        return bbox, best_score

    def _build_search_rect(self, rect: tuple[int, int, int, int], frame_w: int, frame_h: int) -> tuple[int, int, int, int]:
        left, top, width, height = rect
        search_w = int(width * self.search_margin)
        search_h = int(height * self.search_margin)
        center_x = left + width // 2
        center_y = top + height // 2
        search_left = max(0, center_x - search_w // 2)
        search_top = max(0, center_y - search_h // 2)
        search_right = min(frame_w, search_left + search_w)
        search_bottom = min(frame_h, search_top + search_h)
        return search_left, search_top, max(1, search_right - search_left), max(1, search_bottom - search_top)

    def _refresh_template(self, frame: np.ndarray, rect: tuple[int, int, int, int]) -> None:
        patch = self._extract_patch(frame, rect)
        if patch is None:
            return
        patch_gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        if patch_gray.shape[0] < 8 or patch_gray.shape[1] < 8:
            return
        if self._template_gray is None:
            self._template_gray = patch_gray
            return

        target_size = (self._template_gray.shape[1], self._template_gray.shape[0])
        resized = cv2.resize(patch_gray, target_size, interpolation=cv2.INTER_LINEAR)
        blended = cv2.addWeighted(
            self._template_gray,
            1.0 - self.template_update_rate,
            resized,
            self.template_update_rate,
            0.0,
        )
        self._template_gray = blended

    @staticmethod
    def _smooth_rect(previous: tuple[int, int, int, int], current: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        alpha = 0.35
        return (
            int(previous[0] * (1.0 - alpha) + current[0] * alpha),
            int(previous[1] * (1.0 - alpha) + current[1] * alpha),
            max(1, int(previous[2] * (1.0 - alpha) + current[2] * alpha)),
            max(1, int(previous[3] * (1.0 - alpha) + current[3] * alpha)),
        )

    @staticmethod
    def _resize_template(template_gray: np.ndarray, scale: float) -> Optional[np.ndarray]:
        width = max(1, int(template_gray.shape[1] * scale))
        height = max(1, int(template_gray.shape[0] * scale))
        if width < 8 or height < 8:
            return None
        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        return cv2.resize(template_gray, (width, height), interpolation=interpolation)

    @staticmethod
    def _extract_patch(frame: np.ndarray, rect: tuple[int, int, int, int]) -> Optional[np.ndarray]:
        left, top, width, height = rect
        right = left + width
        bottom = top + height
        if width <= 0 or height <= 0:
            return None
        if left < 0 or top < 0 or right > frame.shape[1] or bottom > frame.shape[0]:
            return None
        return frame[top:bottom, left:right].copy()

    @staticmethod
    def _normalized_to_rect(bbox: 归一化目标框, frame_w: int, frame_h: int) -> tuple[int, int, int, int]:
        width = max(1, int(round(bbox.w * frame_w)))
        height = max(1, int(round(bbox.h * frame_h)))
        center_x = int(round(bbox.cx * frame_w))
        center_y = int(round(bbox.cy * frame_h))
        left = max(0, min(frame_w - width, center_x - width // 2))
        top = max(0, min(frame_h - height, center_y - height // 2))
        return left, top, width, height

    @staticmethod
    def _rect_to_normalized(rect: tuple[int, int, int, int], frame_w: int, frame_h: int) -> 归一化目标框:
        left, top, width, height = rect
        return _裁剪归一化目标框(
            归一化目标框(
                cx=(left + width / 2.0) / frame_w,
                cy=(top + height / 2.0) / frame_h,
                w=width / frame_w,
                h=height / frame_h,
            )
        )


def _从角点生成目标框(x1: float, y1: float, x2: float, y2: float) -> 归一化目标框:
    left = min(x1, x2)
    right = max(x1, x2)
    top = min(y1, y2)
    bottom = max(y1, y2)
    return _裁剪归一化目标框(
        归一化目标框(
            cx=(left + right) / 2.0,
            cy=(top + bottom) / 2.0,
            w=right - left,
            h=bottom - top,
        )
    )


def _裁剪归一化目标框(bbox: 归一化目标框) -> 归一化目标框:
    w = max(0.001, min(1.0, bbox.w))
    h = max(0.001, min(1.0, bbox.h))
    cx = max(w / 2.0, min(1.0 - w / 2.0, bbox.cx))
    cy = max(h / 2.0, min(1.0 - h / 2.0, bbox.cy))
    return 归一化目标框(cx=cx, cy=cy, w=w, h=h)
