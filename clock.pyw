from enum import Enum, auto
from datetime import datetime
import time
import tkinter as tk
from threading import Thread
from ctypes import windll
from typing import Any, Tuple

import numpy as np

# [TODO] Support multi-display
# from win32api import EnumDisplayMonitors
# def get_expanded_screen_info() -> Tuple[int]:
#     xmin, ymin, xmax, ymax = 0, 0, 0, 0
#     for winfo in EnumDisplayMonitors():
#         x1, y1, x2, y2 = winfo[-1]
#         xmin = min(x1, xmin)
#         ymin = min(y1, ymin)
#         xmax = max(x2, xmax)
#         ymax = max(y2, ymax)
#     return xmin, ymin, xmax-xmin, ymax-ymin


def set_high_resolution() -> None:
    windll.shcore.SetProcessDpiAwareness(True)


def deg_linspace(num: int) -> np.ndarray:
    return np.linspace(0, 360, num+1)[:-1]


class Tag(Enum):
    DRAGGABLE = auto()
    REMOVABLE = auto()
    ALWAYSTOP = auto()


class CircularPoint:

    CORRECTION_DEGREE: int = 90

    def __init__(self, center: Tuple[float], radius: float) -> None:
        self.center = center
        self.radius = radius

    def xy(self, deg: float) -> Tuple[float]:
        rad = np.radians(self.CORRECTION_DEGREE-deg)
        x = self.center[0] + self.radius * np.cos(rad)
        y = self.center[1] - self.radius * np.sin(rad)
        return np.array((x, y))


class Line:

    def __init__(
        self, canvas: 'ClockCanvas', width: float, color: str, tags: Tuple['Tag']
    ) -> None:
        self.canvas = canvas
        self.width = width
        self.color = color
        self.tags = tags

    def draw(self, p0: np.ndarray, p1: np.ndarray) -> None:
        offset = self.canvas.offset
        self.canvas.create_line(
            *offset+p0, *offset+p1, width=self.width, fill=self.color,
            tags=self.tags
        )


class Dot:

    def __init__(
        self, canvas: 'ClockCanvas', radius: float, color: str, tags: Tuple['Tag']
    ) -> None:
        self.canvas = canvas
        self.radius = radius
        self.color = color
        self.tags = tags

    def draw(self, p: np.ndarray) -> None:
        offset = self.canvas.offset
        self.canvas.create_oval(
            *offset+p-self.radius, *offset+p+self.radius, fill=self.color,
            outline=self.color, tags=self.tags
        )


class ClockScale:

    def __init__(
        self, cp_in: 'CircularPoint', cp_out: 'CircularPoint', line: 'Line',
        degs: Tuple[float]
    ) -> None:
        self.line = line
        self.pairs = tuple((cp_in.xy(deg), cp_out.xy(deg)) for deg in degs)

    def put(self) -> None:
        for p0, p1 in self.pairs:
            self.line.draw(p0, p1)


class ClockHand:

    def __init__(
        self, cp_in: 'CircularPoint', cp_out: 'CircularPoint', line: 'Line',
        degs: Tuple[float]
    ) -> None:
        self.line = line
        self.pairs = tuple((cp_in.xy(deg), cp_out.xy(deg)) for deg in degs)
        self.lap_sec = len(degs)
        self.sec = 0

    def setup(self, now_sec: int) -> None:
        self.sec = now_sec % self.lap_sec

    def step(self) -> None:
        sec_ = self.sec + 1
        self.sec = sec_ if sec_ < self.lap_sec else 0

    def put(self) ->  None:
        p0, p1 = self.pairs[self.sec]
        self.line.draw(p0, p1)


class ClockPin:

    def __init__(self, p: Tuple[float], dot: 'Dot') -> None:
        self.p = np.array(p)
        self.dot = dot

    def put(self) -> None:
        self.dot.draw(self.p)


class ClockCanvas(tk.Canvas):

    COLOR_BG: str = "green"

    def __init__(self) -> None:
        super().__init__(bg=self.COLOR_BG, highlightthickness=0)
        # x, y, w, h = get_expanded_screen_info()
        # self.master.geometry(f'{w}x{h}+{x}+{y}')
        self.master.attributes('-fullscreen', True)
        self.master.resizable(False, False)
        self.master.attributes('-transparentcolor', self.COLOR_BG)
        self.master.attributes('-topmost', True)
        self.master.overrideredirect(True)

        self.tag_bind(Tag.DRAGGABLE, "<ButtonPress-1>", self._on_click)
        self.tag_bind(Tag.DRAGGABLE, "<Button1-Motion>", self._on_drag)
        self.tag_bind(Tag.DRAGGABLE, "<Double-Button-1>", self._on_dclick)
        self.pack(fill=tk.BOTH, expand=True)

        self.offset = [0, 0]

    def _on_click(self, event: Any) -> None:
        self.x, self.y = event.x, event.y

    def _on_drag(self, event: Any) -> None:
        dx, dy = event.x-self.x, event.y-self.y
        self.move(Tag.DRAGGABLE, dx, dy)
        self.x += dx
        self.y += dy
        self.offset[0] += dx
        self.offset[1] += dy

    def _on_dclick(self, event: Any) -> None:
        x, y = self.offset
        self.move(Tag.DRAGGABLE, -x, -y)
        self.offset = [0, 0]

    def clean(self) -> None:
        self.delete(Tag.REMOVABLE)

    def order(self) -> None:
        self.lift(Tag.ALWAYSTOP)


class Clock:

    COLOR_HAND_H: str = "gray20"
    COLOR_HAND_M: str = "gray20"
    COLOR_HAND_S: str = "red2"
    COLOR_SCALE_L: str = "gray60"
    COLOR_SCALE_S: str = "gray60"
    COLOR_DOT: str = "red2"

    R_SCALE_L_INNER: int = 125
    R_SCALE_S_INNER: int = 137
    R_SCALE_OUTER: int = 145
    R_HAND_INNER: int = 0
    R_HAND_S_OUTER: int = 140
    R_HAND_M_OUTER: int = 130
    R_HAND_H_OUTER: int = 90
    R_PIN: int = 8

    W_SCALE_L: int = 4
    W_SCALE_S: int = 2
    W_HAND_H: int = 8
    W_HAND_M: int = 5
    W_HAND_S: int = 2

    INIT_CENTER: Tuple[int] = (1920-200, 200)

    SYNC_ITV: int = 300

    def __init__(self) -> None:
        self.canvas = ClockCanvas()

        scale_l = ClockScale(
            CircularPoint(self.INIT_CENTER, self.R_SCALE_L_INNER),
            CircularPoint(self.INIT_CENTER, self.R_SCALE_OUTER),
            Line(self.canvas, self.W_SCALE_L, self.COLOR_SCALE_L,
                 (Tag.DRAGGABLE)),
            deg_linspace(12)
        )
        scale_s = ClockScale(
            CircularPoint(self.INIT_CENTER, self.R_SCALE_S_INNER),
            CircularPoint(self.INIT_CENTER, self.R_SCALE_OUTER),
            Line(self.canvas, self.W_SCALE_S, self.COLOR_SCALE_S,
                 (Tag.DRAGGABLE)),
            deg_linspace(60)
        )
        hand_h = ClockHand(
            CircularPoint(self.INIT_CENTER, self.R_HAND_INNER),
            CircularPoint(self.INIT_CENTER, self.R_HAND_H_OUTER),
            Line(self.canvas, self.W_HAND_H, self.COLOR_HAND_H,
                 (Tag.DRAGGABLE, Tag.REMOVABLE)),
            deg_linspace(60*60*12)
        )
        hand_m = ClockHand(
            CircularPoint(self.INIT_CENTER, self.R_HAND_INNER),
            CircularPoint(self.INIT_CENTER, self.R_HAND_M_OUTER),
            Line(self.canvas, self.W_HAND_M, self.COLOR_HAND_M,
                 (Tag.DRAGGABLE, Tag.REMOVABLE)),
            deg_linspace(60*60)
        )
        hand_s = ClockHand(
            CircularPoint(self.INIT_CENTER, self.R_HAND_INNER),
            CircularPoint(self.INIT_CENTER, self.R_HAND_S_OUTER),
            Line(self.canvas, self.W_HAND_S, self.COLOR_HAND_S,
                 (Tag.DRAGGABLE, Tag.REMOVABLE)),
            deg_linspace(60)
        )
        pin = ClockPin(
            self.INIT_CENTER,
            Dot(self.canvas, self.R_PIN, self.COLOR_DOT,
                (Tag.DRAGGABLE, Tag.ALWAYSTOP))
        )

        self.total_sec = 0
        self.scales = (scale_l, scale_s)
        self.hands = (hand_h, hand_m, hand_s)

        for scale in self.scales:
            scale.put()

        for hand in self.hands:
            hand.put()

        pin.put()

    def _adjust(self) -> None:
        now = datetime.now()
        now_sec = now.hour * 60*60 + now.minute * 60 + now.second
        for hand in self.hands:
            hand.setup(now_sec)

    def _tick(self) -> None:
        self.canvas.clean()
        for hand in self.hands:
            hand.step()
            hand.put()
        self.canvas.order()
        self.total_sec += 1

    def start(self) -> None:
        def loop():
            while True:
                try:
                    t1 = time.time()
                    if self.total_sec % self.SYNC_ITV == 0:
                        self._adjust()
                    self._tick()
                    t2 = time.time()
                    time.sleep(max(0, 1-t2+t1))
                except KeyboardInterrupt:
                    self.canvas.master.destroy()

        self.thread = Thread(target=loop, daemon=True)
        self.thread.start()
        self.canvas.master.mainloop()


if __name__ == '__main__':
    set_high_resolution()
    clock = Clock()
    clock.start()
