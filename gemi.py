# =============================================================
#  Kingnu Dubbing Tool — FINAL FULL VERSION (2025)
#  (Speaker Filter in Dialogue Viewer Added)
# =============================================================

import sys
import os
import re
import pandas as pd
import sounddevice as sd
import soundfile as sf
import datetime

from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *


# =============================================================
# VLC AUTO-LOADER (VLC 미설치 PC 지원)
# =============================================================
def configure_vlc_path():
    try:
        # PyInstaller EXE 실행 환경
        if hasattr(sys, "_MEIPASS"):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        # EXE 내부 DLL 경로 추가
        os.add_dll_directory(base_path)

        # plugins 폴더 등록
        plugin_path = os.path.join(base_path, "plugins")
        os.environ["VLC_PLUGIN_PATH"] = plugin_path

        print("VLC Base Path:", base_path)
        print("VLC Plugin Path:", plugin_path)

    except Exception as e:
        print("VLC Path Error:", e)


configure_vlc_path()

# VLC import (경로 설정 후)
import vlc


# =============================================================
# Recorder - 안정적 녹음기 
# =============================================================
class Recorder:
    def __init__(self):
        self.fs = 44100
        self.channels = 1
        self.recording = None
        self.start_time = None

    def start(self):
        self.start_time = datetime.datetime.now()
        self.recording = sd.rec(
            int(3600 * self.fs),
            samplerate=self.fs,
            channels=self.channels,
            dtype="float32"
        )

    def stop(self):
        sd.stop()
        sd.wait() 
        
        duration = (datetime.datetime.now() - self.start_time).total_seconds()
        samples = int(duration * self.fs)
        
        return self.recording[:samples]

    def play(self, data):
        sd.play(data, self.fs)


# =============================================================
# VLC Video Player
# =============================================================
class VideoPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.instance = vlc.Instance()
        self.media_player = self.instance.media_player_new()

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.video_frame = QFrame()
        self.video_frame.setObjectName("VideoFrame")
        self.video_frame.setStyleSheet("background:black;")
        layout.addWidget(self.video_frame)

        # Seek bar
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderPressed.connect(self.pause_drag)
        self.slider.sliderReleased.connect(self.finish_drag)
        layout.addWidget(self.slider)
        
        # Current/Total Time Display
        time_layout = QHBoxLayout()
        self.lbl_cur_time = QLabel("00:00:00.000") 
        self.lbl_cur_time.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.lbl_total_time = QLabel("00:00:00.000") 
        self.lbl_total_time.setAlignment(Qt.AlignmentFlag.AlignRight)

        time_layout.addWidget(self.lbl_cur_time)
        time_layout.addWidget(self.lbl_total_time)
        layout.addLayout(time_layout)


        # Playback buttons
        ctrl = QHBoxLayout()
        self.btn_play = QPushButton("▶ 재생/⏸ 일시정지")
        self.btn_stop = QPushButton("■ 정지")
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_stop)
        layout.addLayout(ctrl)

        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_stop.clicked.connect(self.stop)

        # Recording buttons
        rec = QHBoxLayout()
        self.btn_rec_start = QPushButton("🎙 녹음 시작")
        self.btn_rec_stop = QPushButton("⏹ 녹음 종료")
        self.btn_rec_play = QPushButton("🎧 녹음 듣기")
        rec.addWidget(self.btn_rec_start)
        rec.addWidget(self.btn_rec_stop)
        rec.addWidget(self.btn_rec_play)
        layout.addLayout(rec)

        self.dragging = False

    # ---------------------------
    def format_time(self, ms):
        if ms < 0: return "00:00:00.000"
        seconds = ms // 1000
        milliseconds = ms % 1000
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02}:{m:02}:{s:02}.{milliseconds:03}"
    
    def load_video(self, path):
        media = self.instance.media_new(path)
        self.media_player.set_media(media)

        if sys.platform == "win32":
            self.media_player.set_hwnd(self.video_frame.winId())
        else:
            self.media_player.set_xwindow(self.video_frame.winId())

    def toggle_play(self):
        if self.media_player.is_playing():
            self.media_player.pause()
        else:
            self.media_player.play()

    def stop(self):
        self.media_player.pause()

    def get_time_sec(self):
        return max(0, self.media_player.get_time() / 1000)

    def set_time_sec(self, sec):
        self.media_player.set_time(int(sec * 1000))

    # ---------------------------
    def pause_drag(self):
        self.dragging = True

    def finish_drag(self):
        self.dragging = False
        total = self.media_player.get_length() / 1000
        if total > 0:
            pos = self.slider.value() / 1000
            self.set_time_sec(total * pos)

    def update_slider(self):
        if self.dragging:
            return
            
        length = self.media_player.get_length()
        cur = self.media_player.get_time()
        
        # 시간 레이블 업데이트 (개선)
        current_time_str = self.format_time(cur)
        total_time_str = self.format_time(length)
        self.lbl_cur_time.setText(current_time_str)
        self.lbl_total_time.setText(total_time_str)
        
        if length <= 0:
            return
        
        v = int((cur / length) * 1000)
        self.slider.setValue(max(0, min(1000, v)))


# =============================================================
# Main Tool
# =============================================================
class KingnuTool(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("킹누 더빙툴 — FINAL 2025")
        self.resize(1500, 900)

        # ---------------- QSS (스타일 시트) 적용 ----------------
        self.setStyleSheet(self._get_qss_style())

        self.rec = Recorder()
        self.dialogues_full = []
        self.dialogues_primary = [] 
        self.speaker_colors = {}
        self.mode = "primary" # '실전 모드' 유지

        # ---------------- Layout ----------------
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout()
        central.setLayout(main)

        # --------------------------------------------------------
        # LEFT PANEL 
        # --------------------------------------------------------
        left = QVBoxLayout()
        
        # 전체 대사 보기 버튼 (새 기능)
        self.btn_show_all = QPushButton("📋 전체 대사 보기 (더블클릭 이동)")
        self.btn_show_all.clicked.connect(self.show_all_dialogues_dialog)
        left.addWidget(self.btn_show_all)

        # 현재 화자 그룹
        group_current = QGroupBox("현재 대사")
        group_current_layout = QVBoxLayout(group_current)
        
        self.lbl_current = QLabel("-")
        self.lbl_current.setObjectName("CurrentSpeakerLabel")
        group_current_layout.addWidget(self.lbl_current)
        
        left.addWidget(group_current)


        # 다음 화자 그룹 (강조)
        group_next = QGroupBox("다음 대사 준비")
        group_next_layout = QVBoxLayout(group_next)
        
        self.lbl_next = QLabel("-")
        self.lbl_next.setObjectName("NextSpeakerLabel")
        group_next_layout.addWidget(self.lbl_next)
        
        self.lbl_count = QLabel("(다음화자) 준비 -")
        self.lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_count.setObjectName("CountdownLabel")
        group_next_layout.addWidget(self.lbl_count)
        
        left.addWidget(group_next)


        # 다다음 화자 그룹
        group_next2 = QGroupBox("다다음 대사")
        group_next2_layout = QVBoxLayout(group_next2)
        
        self.lbl_next2 = QLabel("-")
        self.lbl_next2.setObjectName("Next2SpeakerLabel")
        group_next2_layout.addWidget(self.lbl_next2)
        
        left.addWidget(group_next2)

        left.addStretch()

        # --------------------------------------------------------
        # RIGHT PANEL
        # --------------------------------------------------------
        self.player = VideoPlayer()

        # 연결
        self.player.btn_rec_start.clicked.connect(self.start_record)
        self.player.btn_rec_stop.clicked.connect(self.stop_record)
        self.player.btn_rec_play.clicked.connect(self.play_record)

        main.addLayout(left, 3)
        main.addWidget(self.player, 2)

        # --------------------------------------------------------
        # MENU
        # --------------------------------------------------------
        menu = self.menuBar().addMenu("파일")

        act_excel = QAction("엑셀 불러오기", self)
        act_excel.triggered.connect(self.load_excel)
        menu.addAction(act_excel)

        act_video = QAction("영상 불러오기", self)
        act_video.triggered.connect(self.load_video)
        menu.addAction(act_video)

        act_srt = QAction("SRT → 엑셀 변환", self)
        act_srt.triggered.connect(self.load_srt)
        menu.addAction(act_srt)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_by_time)
        self.timer.start(200)

    # =============================================================
    # UI STYLING (QSS)
    # =============================================================
    def _get_qss_style(self):
        return """
            /* Global Dark Theme */
            QMainWindow, QDialog { 
                background-color: #2e2e2e; 
                color: #ffffff; 
            }
            
            QMenuBar {
                background-color: #3e3e3e;
                color: #ffffff;
            }
            QMenuBar::item:selected {
                background: #555555;
            }
            QMenu {
                background-color: #3e3e3e;
                border: 1px solid #555555;
            }
            QMenu::item:selected {
                background-color: #555555;
                color: #ffffff;
            }

            /* Buttons */
            QPushButton {
                background-color: #4a4a4a;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-weight: 600;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #5f5f5f;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }

            /* Group Box */
            QGroupBox {
                border: 2px solid #555555;
                border-radius: 8px;
                margin-top: 10px;
                background-color: #3a3a3a;
                font-weight: bold;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 10px;
                color: #ffffff; 
            }

            /* Labels */
            QLabel {
                padding: 5px;
                color: #ffffff; 
            }
            
            /* Specific Labels */
            #CurrentSpeakerLabel {
                font-size: 20px; 
                font-weight: bold;
                padding: 15px;
            }
            
            #NextSpeakerLabel { /* 다음 화자 텍스트 */
                font-size: 28px; 
                font-weight: 900; 
                padding: 14px; 
                color: #ff9900; 
                background: #442200; 
                border-radius: 8px;
            }
            
            #CountdownLabel { /* 카운트다운 */
                font-size: 40px; 
                font-weight: 900; 
                color: #FF4D4D; 
                background: #1e1e1e; 
                padding: 15px; 
                border-radius: 8px;
            }
            
            #Next2SpeakerLabel { /* 다다음 화자 텍스트 */
                font-size: 16px; 
                font-weight: normal; 
            }

            /* Sliders */
            QSlider::groove:horizontal {
                height: 8px;
                background: #555555;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00bfff;
                border: none;
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #00bfff;
                border-radius: 4px;
            }

            /* Table Widget */
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff; 
                gridline-color: #3e3e3e;
                alternate-background-color: #242424;
                border: 1px solid #444444;
                selection-background-color: #00bfff;
            }
            QHeaderView::section {
                background-color: #4a4a4a;
                color: #ffffff;
                padding: 6px;
                border: 1px solid #3e3e3e;
            }
        """

    # =============================================================
    # NEW FEATURE: Dialogue Viewer & Seeker (화자 필터 기능 추가)
    # =============================================================
    def show_all_dialogues_dialog(self):
        if not self.dialogues_full:
            QMessageBox.warning(self, "오류", "엑셀 파일이 로드되지 않았습니다.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("전체 대사 목록 (화자 필터 및 더블클릭 이동)")
        dialog.resize(1000, 700)
        
        main_layout = QVBoxLayout(dialog)
        
        # --- 1. 필터링 컨트롤 (콤보 박스 추가) ---
        filter_layout = QHBoxLayout()
        lbl_filter = QLabel("화자 필터:")
        self.combo_speaker_filter = QComboBox() # self로 저장하여 다른 메서드에서 접근 가능하게 함
        
        # 화자 목록 채우기
        speakers = ["--전체보기--"] + sorted(list(self.speaker_colors.keys()))
        self.combo_speaker_filter.addItems(speakers)

        filter_layout.addWidget(lbl_filter)
        filter_layout.addWidget(self.combo_speaker_filter)
        filter_layout.addStretch()
        main_layout.addLayout(filter_layout)

        # --- 2. 테이블 위젯 ---
        self.dialogue_table = QTableWidget() # self로 저장하여 필터링 메서드에서 접근 가능하게 함
        main_layout.addWidget(self.dialogue_table)
        
        # 초기 테이블 설정 및 데이터 로드
        self._populate_dialogue_table("--전체보기--")

        # --- 3. 이벤트 연결 ---
        self.combo_speaker_filter.currentTextChanged.connect(self._handle_speaker_filter_change)
        
        # 더블클릭 이벤트 연결
        self.dialogue_table.cellDoubleClicked.connect(
            lambda row, col: self.seek_to_row_start_time_filtered(row, dialog)
        )
        
        dialog.exec()
        
    def _populate_dialogue_table(self, filter_speaker):
        table = self.dialogue_table
        
        # 필터링 로직
        if filter_speaker == "--전체보기--":
            filtered_data = self.dialogues_full
        else:
            filtered_data = [
                row for row in self.dialogues_full 
                if row.get("화자") == filter_speaker
            ]
        
        table.setRowCount(0) # 기존 내용 삭제
        
        column_names = list(self.dialogues_full[0].keys()) if self.dialogues_full else []
        table.setColumnCount(len(column_names))
        table.setHorizontalHeaderLabels(column_names)
        
        table.setRowCount(len(filtered_data))
        
        # 테이블 채우기
        for row_idx, row_data in enumerate(filtered_data):
            for col_idx, col_name in enumerate(column_names):
                value = row_data.get(col_name)
                
                if col_name == "시작_초":
                    value_str = f"{value:.3f}초" if value is not None else ""
                elif value is None:
                    value_str = ""
                else:
                    value_str = str(value)
                    
                item = QTableWidgetItem(value_str)
                table.setItem(row_idx, col_idx, item)

        # 컬럼 크기 조정
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        try:
            dialogue_col_index = column_names.index("대사")
            header.setSectionResizeMode(dialogue_col_index, QHeaderView.ResizeMode.Stretch)
        except ValueError:
            pass
            
        # 테이블에 현재 필터링된 데이터를 임시 저장 (더블클릭 탐색을 위해)
        self.filtered_dialogues = filtered_data


    def _handle_speaker_filter_change(self, speaker_name):
        self._populate_dialogue_table(speaker_name)
        
    def seek_to_row_start_time_filtered(self, row_index_in_table, dialog):
        try:
            # 테이블의 인덱스가 아니라 self.filtered_dialogues 리스트의 인덱스 사용
            start_sec = self.filtered_dialogues[row_index_in_table]["시작_초"]
            self.player.set_time_sec(start_sec)
            dialog.accept()
                
        except (IndexError, KeyError, TypeError) as e:
            QMessageBox.warning(self, "오류", f"해당 행의 시작 시간을 찾을 수 없습니다: {e}")

    # =============================================================
    # LOAD VIDEO
    # =============================================================
    def load_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "영상 선택", "", "Video (*.mp4 *.mkv *.avi *.mov)"
        )
        if path:
            self.player.load_video(path)
            QMessageBox.information(self, "완료", "영상 로드 완료!")

    # =============================================================
    # LOAD EXCEL (build_primary 유지)
    # =============================================================
    def load_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "엑셀 선택", "", "Excel (*.xlsx)")
        if not path:
            return

        df = pd.read_excel(path)

        rename = {
            " 시작": "시작", "시작 ": "시작",
            " 끝": "끝", "끝 ": "끝",
            " 화자": "화자", "화자 ": "화자",
            " 대사": "대사", "대사 ": "대사",
        }
        df.rename(columns=rename, inplace=True)

        if not all(x in df.columns for x in ["시작", "화자", "대사"]):
            QMessageBox.warning(self, "오류", "엑셀 양식이 잘못되었습니다.")
            return

        df["시작_초"] = df["시작"].apply(self.to_sec)
        df = df.sort_values(by="시작_초")

        self.dialogues_full = df.to_dict("records")
        self.dialogues_primary = self.build_primary(self.dialogues_full) # 기존 알고리즘 유지
        self.assign_colors()

        QMessageBox.information(self, "완료", "엑셀 로드 완료!")

    # =============================================================
    # SRT → EXCEL
    # =============================================================
    def strip_html(self, text):
        return re.sub(r"<[^>]*>", "", text)

    def load_srt(self):
        path, _ = QFileDialog.getOpenFileName(self, "SRT 선택", "", "SRT (*.srt)")
        if not path:
            return

        subs = []
        cur = {"start": "", "end": "", "text": ""}

        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()

        for line in lines:
            line = line.strip()

            if line.isdigit():
                if cur["text"]:
                    subs.append(cur)
                cur = {"start": "", "end": "", "text": ""}
                continue

            if "-->" in line:
                s, e = line.split("-->")
                cur["start"] = s.strip().replace(",", ".")
                cur["end"] = e.strip().replace(",", ".")
                continue

            if line:
                clean = self.strip_html(line)
                cur["text"] += (" " if cur["text"] else "") + clean

        if cur["text"]:
            subs.append(cur)

        df = pd.DataFrame([{
            "시작": x["start"],
            "끝": x["end"],
            "화자": "",
            "대사": x["text"],
            "감정": "",
            "톤": ""
        } for x in subs])

        save, _ = QFileDialog.getSaveFileName(self, "엑셀 저장", "", "Excel (*.xlsx)")
        if save:
            df.to_excel(save, index=False)
            QMessageBox.information(self, "완료", "SRT → 엑셀 변환 성공!")

    # =============================================================
    # RECORDING (경로 수정 적용)
    # =============================================================
    def start_record(self):
        self.rec.start()
        QMessageBox.information(self, "녹음", "녹음을 시작합니다!")

    def stop_record(self):
        try:
            data = self.rec.stop()

            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"record_{now}.wav"

            # 저장 경로 설정 (사용자 문서 폴더)
            home_dir = os.path.expanduser("~")
            save_folder = os.path.join(home_dir, "Documents", "KingnuDubbingTool_Recordings")
            
            if not os.path.exists(save_folder):
                os.makedirs(save_folder)
                
            save_path = os.path.join(save_folder, filename)

            sf.write(save_path, data, self.rec.fs)
            QMessageBox.information(self, "저장", f"녹음 저장 완료!\n{save_path}")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"녹음 종료 및 저장 실패: {e}\n(재시도하거나 권한을 확인해주세요.)")

    def play_record(self):
        try:
            # 기본 경로 설정 (KingnuDubbingTool_Recordings 폴더)
            home_dir = os.path.expanduser("~")
            app_path = os.path.join(home_dir, "Documents", "KingnuDubbingTool_Recordings")

            if not os.path.exists(app_path):
                os.makedirs(app_path, exist_ok=True)

            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "재생할 WAV 파일 선택",
                app_path, # 기본 경로로 설정
                "WAV 파일 (*.wav)"
            )

            if not file_path:
                return

            data, fs = sf.read(file_path, dtype="float32")
            sd.play(data, fs)
            QMessageBox.information(self, "재생", f"재생 중:\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"재생 실패:\n{e}")

    # =============================================================
    # SYNC (기존 알고리즘 유지)
    # =============================================================
    def to_sec(self, t):
        try:
            if isinstance(t, (float, int)):
                return float(t)
            
            parts = str(t).split(":")
            if len(parts) == 3:
                h, m, s = parts
                return int(h)*3600 + int(m)*60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m)*60 + float(s)
            else:
                return 0.0
        except:
            return 0.0

    def build_primary(self, full): # 기존 알고리즘 유지
        result = []
        prev = None
        for r in full:
            if r["화자"] != prev:
                result.append(r)
                prev = r["화자"]
        return result

    def assign_colors(self):
        pal = [
            "#FF6B6B","#4ECDC4","#45B7D1","#FFA600",
            "#6A4C93","#1982C4","#8E5572","#9BC53D",
            "#F94144","#577590","#D8572A"
        ]
        i = 0
        self.speaker_colors = {}

        for r in self.dialogues_full:
            s = r["화자"]
            if s not in self.speaker_colors:
                self.speaker_colors[s] = pal[i % len(pal)]
                i += 1

    def update_by_time(self): # 기존 알고리즘 유지
        self.player.update_slider()

        if not self.dialogues_full:
            return

        now = self.player.get_time_sec()
        # self.mode가 'primary'로 고정되었으므로 dialogues_primary만 사용
        lst = self.dialogues_primary 

        idx = 0
        for i, r in enumerate(lst):
            if r["시작_초"] <= now:
                idx = i
            else:
                break

        self.update_labels(lst, idx, now)

    def update_labels(self, lst, idx, now): # 기존 알고리즘 유지
        cur = lst[idx] if idx < len(lst) else None
        nxt = lst[idx+1] if idx+1 < len(lst) else None
        nxt2 = lst[idx+2] if idx+2 < len(lst) else None

        if cur:
            s = cur["화자"]
            t = cur["대사"]
            self.lbl_current.setText(f"{s}\n\n{t}")
            self.colorize(self.lbl_current, s)
        else:
            self.lbl_current.setText("-")
            self.colorize(self.lbl_current, None)

        if nxt:
            s = nxt["화자"]
            t = nxt["대사"]
            remain = max(0, nxt["시작_초"] - now)
            self.lbl_next.setText(f"{s}\n\n{t}")
            self.lbl_count.setText(f"({s}) 준비 - {remain:.2f} 초")
        else:
            self.lbl_next.setText("다음 화자 없음 (혹은 동일 화자)")
            self.lbl_count.setText("(다음화자) 준비 -")

        if nxt2:
            s = nxt2["화자"]
            t = nxt2["대사"]
            self.lbl_next2.setText(f"{s}\n\n{t}")
            self.colorize(self.lbl_next2, s)
        else:
            self.lbl_next2.setText("-")
            self.colorize(self.lbl_next2, None)

    def colorize(self, label, spk):
        if spk is None:
            color = "#3a3a3a"
        else:
            color = self.speaker_colors.get(spk, "#555555")

        if label.objectName() == "CurrentSpeakerLabel":
            label.setStyleSheet(
                f"background:{color}; font-size:20px; font-weight:bold; padding:15px; border-radius:6px;"
            )
        elif label.objectName() == "Next2SpeakerLabel":
            label.setStyleSheet(
                f"background:{color}; font-size:16px; font-weight:normal; padding:10px; border-radius:6px;"
            )
        


# =============================================================
# EXEC
# =============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = KingnuTool()
    win.show()
    sys.exit(app.exec())