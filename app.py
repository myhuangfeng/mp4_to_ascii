# -*- coding: utf-8 -*-
import cv2
import os
import time
import curses
import numpy as np
import shutil
from concurrent.futures import ThreadPoolExecutor

# 高清配置
ENHANCED_ASCII = "@%#W$9876543210?!abc;:+=-,._ "  # 32级灰度增强字符
VIDEO_FILE = "input.mp4"
FPS = 12  # 优化帧率
ASCII_WIDTH = 100  # 高清宽度
MAX_THREADS = 4    # 多线程加速

class HDAsciiPlayer:
    def __init__(self):
        self.term_size = self._get_terminal_size()
        self.ascii_frames = []
        self._prepare_dirs()

    def _get_terminal_size(self):
        """获取终端尺寸并保留边距"""
        try:
            import shutil
            cols, rows = shutil.get_terminal_size()
            return max(rows-2, 24), max(cols-4, 80)  # 最小24行80列
        except:
            return 24, 80

    def _prepare_dirs(self):
        """创建必要目录"""
        os.makedirs("temp_frames", exist_ok=True)
        os.makedirs("ascii_cache", exist_ok=True)

    def _enhance_image(self, img):
        """图像增强处理"""
        # 对比度增强
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        limg = cv2.merge([clahe.apply(l), a, b])
        enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        
        # 边缘锐化
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        return cv2.filter2D(enhanced, -1, kernel)

    def _convert_to_ascii(self, img_path):
        """高清ASCII转换核心"""
        try:
            # 可靠读取图像
            img = cv2.imread(img_path)
            if img is None:
                img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            
            if img is None:
                return None

            # 图像增强
            img = self._enhance_image(img)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 智能尺寸调整
            height = int(self.term_size[0] * 0.9)  # 保留状态栏空间
            width = min(ASCII_WIDTH, self.term_size[1])
            gray = cv2.resize(gray, (width, height), interpolation=cv2.INTER_AREA)
            
            # 高精度ASCII映射
            ascii_str = ""
            for row in gray:
                line = "".join([ENHANCED_ASCII[min(int((p/255) * (len(ENHANCED_ASCII)-1)), len(ENHANCED_ASCII)-1)] 
                              for p in row])
                ascii_str += line + "\n"
            return ascii_str
        except Exception as e:
            print(f"转换错误 {img_path}: {str(e)}")
            return None

    def convert_video(self):
        """视频转换主流程"""
        if not os.path.exists(VIDEO_FILE):
            print(f"错误：找不到视频文件 {VIDEO_FILE}")
            return False

        # 使用现代FFmpeg参数
        cmd = (
            f'ffmpeg -i "{VIDEO_FILE}" '
            f'-vf "fps={FPS},scale={ASCII_WIDTH}:-1:flags=lanczos" '
            f'"temp_frames/frame_%04d.png" -y'
        )
        
        if os.system(cmd) != 0:
            print("视频转换失败！请检查FFmpeg")
            return False

        # 多线程转换
        frame_files = sorted([f for f in os.listdir("temp_frames") if f.endswith(".png")])
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            results = list(executor.map(
                lambda f: self._convert_to_ascii(os.path.join("temp_frames", f)),
                frame_files
            ))
        
        self.ascii_frames = [f for f in results if f]
        return bool(self.ascii_frames)

    def play(self):
        """高清播放引擎"""
        if not self.ascii_frames:
            print("错误：没有可播放的帧！")
            return

        try:
            stdscr = curses.initscr()
            curses.curs_set(0)
            curses.noecho()
            stdscr.nodelay(1)
            
            # 颜色支持（可选）
            try:
                curses.start_color()
                curses.use_default_colors()
            except:
                pass

            max_rows, max_cols = self.term_size
            
            for idx, frame in enumerate(self.ascii_frames):
                stdscr.clear()
                try:
                    # 分块渲染（解决大帧问题）
                    lines = frame.splitlines()
                    for i in range(min(len(lines), max_rows-1)):
                        stdscr.addstr(i, 0, lines[i][:max_cols-1])
                    
                    # 状态栏
                    status = f"HD-ASCII {idx+1}/{len(self.ascii_frames)} | {FPS}FPS | Q退出"
                    stdscr.addstr(min(max_rows-1, len(lines)), 0, status[:max_cols-1])
                    stdscr.refresh()
                    
                    # 控制逻辑
                    if stdscr.getch() == ord('q'):
                        break
                        
                    time.sleep(1/FPS)
                except curses.error:
                    continue
        finally:
            curses.endwin()

    def cleanup(self):
        """资源清理"""
        shutil.rmtree("temp_frames", ignore_errors=True)

if __name__ == "__main__":
    print("=== 高清ASCII视频播放器 ===")
    player = HDAsciiPlayer()
    
    try:
        # 转换流程
        print("正在转换视频...")
        if not player.convert_video():
            exit(1)
            
        # 播放流程
        print(f"准备播放 {len(player.ascii_frames)} 帧 (终端尺寸: {player.term_size[0]}x{player.term_size[1]})")
        player.play()
    except KeyboardInterrupt:
        print("\n播放中断")
    finally:
        player.cleanup()
        print("播放结束")