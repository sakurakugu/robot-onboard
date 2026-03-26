import unittest

import numpy as np

from src.modules.vision.target_tracker import 从参数解析目标框, 静态目标跟踪器


class Test目标框解析(unittest.TestCase):
    def test_支持中心点格式(self) -> None:
        bbox = 从参数解析目标框({"cx": 0.4, "cy": 0.6, "w": 0.2, "h": 0.1})
        self.assertAlmostEqual(bbox.cx, 0.4)
        self.assertAlmostEqual(bbox.cy, 0.6)
        self.assertAlmostEqual(bbox.w, 0.2)
        self.assertAlmostEqual(bbox.h, 0.1)

    def test_支持左上宽高格式(self) -> None:
        bbox = 从参数解析目标框({"x": 0.2, "y": 0.3, "w": 0.1, "h": 0.2})
        self.assertAlmostEqual(bbox.cx, 0.25)
        self.assertAlmostEqual(bbox.cy, 0.4)
        self.assertAlmostEqual(bbox.w, 0.1)
        self.assertAlmostEqual(bbox.h, 0.2)

    def test_支持角点格式(self) -> None:
        bbox = 从参数解析目标框({"x1": 0.1, "y1": 0.2, "x2": 0.3, "y2": 0.5})
        self.assertAlmostEqual(bbox.cx, 0.2)
        self.assertAlmostEqual(bbox.cy, 0.35)
        self.assertAlmostEqual(bbox.w, 0.2)
        self.assertAlmostEqual(bbox.h, 0.3)


class Test静态目标跟踪器(unittest.TestCase):
    def test_可跟踪静态目标的小位移(self) -> None:
        frame1 = np.zeros((180, 240, 3), dtype=np.uint8)
        frame1[50:90, 80:130] = 255
        frame1[58:82, 92:118] = 0
        frame1[64:76, 98:112] = 180

        frame2 = np.zeros((180, 240, 3), dtype=np.uint8)
        frame2[56:96, 88:138] = 255
        frame2[64:88, 100:126] = 0
        frame2[70:82, 106:120] = 180

        tracker = 静态目标跟踪器(
            initial_bbox=从参数解析目标框({"x": 80 / 240, "y": 50 / 180, "w": 50 / 240, "h": 40 / 180}),
            min_score=0.0,
        )
        tracker.初始化(frame1)
        result = tracker.更新(frame2)

        self.assertIsNotNone(result)
        bbox, score = result
        self.assertGreaterEqual(score, 0.0)
        self.assertGreater(bbox.cx, 0.44)
        self.assertGreater(bbox.cy, 0.39)


if __name__ == "__main__":
    unittest.main()
