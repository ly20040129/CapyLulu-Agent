"""解压桌宠：透明置顶、可拖、点击互动、轻微晃动。伪3D升级版。

伪 3D 方案说明：
- 素材为多状态图（正面/侧面/不同表情动作），非同姿态多角度序列，
  因此用「多状态动画 + 视角轮播切换 + 立体感增强」模拟 3D 效果：
  1) 呼吸动画：PIL 预生成多档缩放帧，正弦呼吸（缩放层次）；
  2) 摇摆 + 投影：正弦上下浮动，投影随抬升高度变小变淡（纵深错觉）；
  3) 状态/视角轮播：空闲时随机切换正面/侧面帧，模拟多角度旋转切换；
  4) 点击互动：弹跳 + 表情帧切换 + 台词气泡；
  5) 立体感：PIL 合成顶部高光 + 底部暗角，增强体积感。
不嵌进网页。保留原功能：拖动、置顶、点击台词、双击右键/Esc 关闭。
"""
import math
import random
from pathlib import Path
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw

# 图片资产已迁移到 web/public/lulu（原 assets 目录已清理），按候选顺序取第一个存在的目录
_ASSET_CANDIDATES = (
    Path(__file__).resolve().parent.parent / "web" / "public" / "lulu",
    Path(__file__).resolve().parent.parent / "assets",
)
ASSETS = next((p for p in _ASSET_CANDIDATES if p.exists()), _ASSET_CANDIDATES[0])
KEY = "#FF00FF"  # 透明色键（品红；绿色键在部分显示器/合成下易冒绿光）
# 抠图背景色集合：品红(新键) + 旧素材的绿色(兼容旧图)；容差/羽化消除边缘色边
_BG_KEYS = [(255, 0, 255), (0, 255, 0)]
_BG_TOL = 38      # 完全透明判定阈值（RGB 欧氏距离）
_BG_FRINGE = 34   # 边缘羽化带宽度：距离在 (TOL, TOL+FRINGE] 之间按比例降 alpha
PHRASES = ("嗯～", "再摸一下", "先吃口零食", "天塌下来也不急", "噜～", "歇一会儿")

# 状态/视角轮播顺序：正面 → 正面趴 → 侧头大笑 → 侧面惊讶 → 侧面举瓜 → 正面持鸭 → 正面惊讶
FRAME_ORDER = ("6.png", "1.png", "7.png", "3.png", "5.png", "2.png", "4.png", "8.png")
BREATH_STEPS = 9          # 呼吸帧数（缩放层次）
BREATH_SCALE = 0.06       # 呼吸缩放幅度（±3%）
CYCLE_MIN, CYCLE_MAX = 360, 640   # 空闲换帧间隔（tick，80ms/个 ≈ 4.8~8.5 秒）


def _load_assets():
    """纯 PIL 阶段：加载全部素材帧，返回 {文件名: [呼吸帧 RGBA Image, ...]}（不依赖 Tk root）。"""
    photos = {}
    for name in FRAME_ORDER:
        p = ASSETS / name
        if p.exists():
            photos[name] = _build_frames(p)
    if not photos:  # 兜底：至少一张（从素材顺序中取第一个真实存在的文件，避免 FileNotFoundError）
        for name in FRAME_ORDER:
            if (ASSETS / name).exists():
                photos[name] = _build_frames(ASSETS / name)
                break
    return photos


def _to_photos(assets):
    """Tk 阶段：root 创建后把纯 PIL 帧转为 ImageTk.PhotoImage（PhotoImage 依赖默认 root，必须在此阶段做）。"""
    return {name: [ImageTk.PhotoImage(im) for im in frames] for name, frames in assets.items()}


def _chroma_key(im, keys, tolerance=_BG_TOL, fringe=_BG_FRINGE):
    """按背景色集合抠图 + 归一透明色键（解决冒紫光）。

    关键点：
    1. Tk 的 -transparentcolor 是精确 RGB 匹配，透明像素 RGB 必须统一成 KEY 色，
       否则露出黑/绿底；
    2. Tk PhotoImage 会把 0<alpha<255 的半透明像素与品红窗口背景做 alpha 混合，
       边缘直接冒紫/粉光。因此这里做 alpha 二值化：>=128 视为不透明(255)，
       <128 视为透明(0, RGB=KEY)，彻底消除半透明像素。
    """
    px = im.load()
    w, h = im.size
    key_rgb = (255, 0, 255)  # 必须与模块级 KEY 常量一致
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                px[x, y] = (*key_rgb, 0)
                continue
            best = min(
                ((r - kr) ** 2 + (g - kg) ** 2 + (b - kb) ** 2) ** 0.5
                for kr, kg, kb in keys
            )
            if best <= tolerance:
                px[x, y] = (*key_rgb, 0)
            elif best <= tolerance + fringe:
                factor = 1.0 - (best - tolerance) / fringe
                if factor > 0.5:
                    px[x, y] = (*key_rgb, 0)
                else:
                    px[x, y] = (r, g, b, 0)  # 弱边缘残留：归入透明
            elif a < 128:
                px[x, y] = (*key_rgb, 0)
            else:
                px[x, y] = (r, g, b, 255)  # 二值化：消灭半透明


def _resize_pma(im, nw, nh):
    """预乘 alpha 缩放：LANCZOS 对 RGBA 四通道分别插值会把 KEY 色混入边缘（紫边），
    先按 alpha 预乘 RGB 再缩放，插值出的边缘颜色才是主体色的正确淡化。
    返回：缩放后的 RGBA 图，透明像素 RGB 归一为 KEY 色，alpha 二值化（消灭半透明）。
    """
    key_rgb = (255, 0, 255)
    px = im.load()
    w, h = im.size
    # 预乘：RGB *= alpha/255（透明像素保持 KEY 色不变）
    premul = Image.new("RGBA", im.size)
    pp = premul.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                pp[x, y] = (*key_rgb, 0)
            else:
                f = a / 255.0
                pp[x, y] = (int(r * f), int(g * f), int(b * f), a)
    res = premul.resize((nw, nh), Image.Resampling.LANCZOS)
    rp = res.load()
    for y in range(nh):
        for x in range(nw):
            r, g, b, a = rp[x, y]
            if a < 128:
                rp[x, y] = (*key_rgb, 0)  # 透明归 KEY
            else:
                # 反预乘还原颜色
                f = a / 255.0
                rp[x, y] = (min(255, int(r / f)), min(255, int(g / f)), min(255, int(b / f)), 255)
    return res


def _build_frames(path: Path, size=180):
    """对单张素材生成 BREATH_STEPS 个呼吸缩放帧（含抠背景 + 高光/暗角立体感合成，返回 RGBA Image 列表）。"""
    im = Image.open(path).convert("RGBA")
    im.thumbnail((size, size), Image.Resampling.LANCZOS)
    w, h = im.size  # 修复：此前丢失该行导致下方 nw/nh 引用未定义变量 w/h 触发 NameError
    _chroma_key(im, _BG_KEYS)
    out = []
    for i in range(BREATH_STEPS):
        scale = 1.0 + BREATH_SCALE * (i / (BREATH_STEPS - 1) - 0.5)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        # 预乘 alpha 缩放：避免 LANCZOS 把 KEY 品红混入边缘产生紫边
        im2 = _resize_pma(im, nw, nh)
        # resize 后仍可能有残留，二次抠图兜底
        _chroma_key(im2, _BG_KEYS)
        out.append(_compose(im2))
    return out


def _compose(im):
    """立体感合成：顶部高光提亮 + 底部暗角压暗（体积感）。

    不引入 overlay/alpha_composite：半透明椭圆叠加会产生 0<alpha<255 像素，
    在 Tk 里与品红背景混合会冒紫光。这里直接对不透明主体像素的 RGB 加减，
    透明像素保持不变（已是 KEY 色）。
    """
    px = im.load()
    w, h = im.size
    # 高光椭圆参数（沿用原 bbox 中心/半径）
    hx, hy = w // 2, int(h * 0.10)
    hrx, hry = int(w * 0.55), int(h * 0.16)
    # 暗角椭圆参数
    dx, dy = w // 2, h - int(h * 0.035)
    drx, dry = int(w * 0.7), int(h * 0.185)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue  # 透明像素：保持 KEY 色
            # 高光：椭圆内提亮
            if hrx > 0 and hry > 0:
                if ((x - hx) / hrx) ** 2 + ((y - hy) / hry) ** 2 <= 1.0:
                    r = min(255, r + 26)
                    g = min(255, g + 26)
                    b = min(255, b + 26)
            # 暗角：椭圆内压暗
            if drx > 0 and dry > 0:
                if ((x - dx) / drx) ** 2 + ((y - dy) / dry) ** 2 <= 1.0:
                    r = max(0, r - 24)
                    g = max(0, g - 24)
                    b = max(0, b - 24)
            px[x, y] = (r, g, b, 255)
    return im


def main():
    root = tk.Tk()            # 必须先建 root：PhotoImage 依赖默认 root，过早创建会抛 RuntimeError
    assets = _load_assets()   # 纯 PIL 阶段：抠背景/缩放/立体感合成，无 Tk 依赖
    photos = _to_photos(assets)  # Tk 阶段：root 就绪后再转 ImageTk.PhotoImage
    names = list(photos.keys())
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg=KEY)
    try:
        root.wm_attributes("-transparentcolor", KEY)
    except tk.TclError:
        pass

    idx = {
        "frame": 0, "tick": 0, "breath": 0,
        "mode": "idle", "jump_t": 0,
        "x": 120, "y": 160, "dx": 0, "next": 0,
    }
    CX, CY = 100, 130          # 主体锚点
    GROUND_Y = 205             # 投影基准地面

    canvas = tk.Canvas(root, width=200, height=240, bg=KEY, highlightthickness=0, bd=0)
    canvas.pack()
    sprite = canvas.create_image(CX, CY, image=photos[names[0]][0])
    shadow = canvas.create_oval(58, GROUND_Y - 5, 142, GROUND_Y + 5,
                                fill="#000000", stipple="gray50", outline="")
    bubble = canvas.create_text(CX, 24, text="", fill="#F4EDE4", font=("", 11))

    def frame_photos():
        return photos[names[idx["frame"] % len(names)]]

    def redraw():
        canvas.itemconfig(sprite, image=frame_photos()[idx["breath"]])

    def draw_shadow(ty):
        """投影随抬升高度变小变淡（纵深错觉）。"""
        lift = CY - ty
        w = max(28, 42 - lift // 2)
        hh = max(4, 9 - lift // 8)
        canvas.coords(shadow, CX - w, GROUND_Y - hh, CX + w, GROUND_Y + hh)
        canvas.itemconfig(shadow, stipple="gray50" if lift < 16 else "gray25")

    def idle():
        idx["tick"] += 1
        t = idx["tick"]

        # 弹跳（点击后）：0→升→落
        if idx["mode"] == "jump":
            idx["jump_t"] += 1
            lift = 26 * math.sin(math.pi * idx["jump_t"] / 7)
            if idx["jump_t"] >= 7:
                idx["mode"] = "idle"
                idx["jump_t"] = 0
        else:
            # 呼吸：正弦缩放档位
            idx["breath"] = int((math.sin(t * 0.12) * 0.5 + 0.5) * (BREATH_STEPS - 1))
            # 摇摆：正弦平滑上下
            lift = int(5 * math.sin(t * 0.07))
            # 状态/视角轮播：到点随机换帧（正面↔侧面，模拟多角度切换）
            if t >= idx["next"]:
                idx["frame"] = (idx["frame"] + random.choice((1, 2))) % len(names)
                idx["next"] = t + random.randint(CYCLE_MIN, CYCLE_MAX)

        canvas.itemconfig(sprite, image=frame_photos()[idx["breath"]])
        canvas.coords(sprite, CX, CY + lift)
        draw_shadow(CY + lift)
        root.after(80, idle)

    def start(e):
        idx["dx"], idx["dy"] = e.x, e.y

    def drag(e):
        root.geometry(f"+{e.x_root - idx['dx']}+{e.y_root - idx['dy']}")

    def poke(_=None):
        idx["mode"] = "jump"
        idx["jump_t"] = 0
        # 切换表情/状态帧（点击互动）
        idx["frame"] = (idx["frame"] + 1) % len(names)
        canvas.itemconfig(bubble, text=random.choice(PHRASES))
        root.after(1800, lambda: canvas.itemconfig(bubble, text=""))

    def rotate(_=None):
        """左键双击：旋转视角（切换到下一角度/状态帧）。"""
        idx["frame"] = (idx["frame"] + 1) % len(names)
        canvas.itemconfig(bubble, text="转个角度～")
        root.after(1200, lambda: canvas.itemconfig(bubble, text=""))

    def close(_=None):
        root.destroy()

    canvas.bind("<Button-1>", start)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", poke)
    canvas.bind("<Double-Button-1>", rotate)
    canvas.bind("<Double-Button-3>", close)
    root.bind("<Escape>", close)
    root.geometry("+100+120")
    idle()
    root.mainloop()


if __name__ == "__main__":
    main()
