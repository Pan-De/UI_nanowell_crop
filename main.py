import os
import sys

# Suppress low-level OpenCV C++ warnings and libtiff logs before importing cv2
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

import cv2
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QTextEdit, QFileDialog, QGridLayout, QHBoxLayout, QVBoxLayout, QSplitter,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, QWheelEvent, QPainter

import core_crop


class InteractiveView(QGraphicsView):
    """
    Interactive canvas supporting mouse wheel zooming centered on cursor
    and scroll-hand drag panning for alignment verification.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = None

        # Configure the interactive drag mode to scroll-hand dragging
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    
    def set_image(self, pixmap: QPixmap):
        # Updates the background image while maintaining the current zoom state.
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        # Enable bilinear filtering to keep edges smooth when zooming in on nanowells
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def wheelEvent(self, event: QWheelEvent):
        # Intercepts the mouse wheel event to zoom centered on the cursor position.
        if self.pixmap_item is None:
            return
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        scale_factor = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
        self.scale(scale_factor, scale_factor)


class MicroscopyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Microscopy Nanowell Processor & Crop Tool")
        self.resize(1400, 900)

        # In-memory image caching structures
        self.cached_gray = None
        self.cached_gray_crop = None
        self.cached_bgr = None
        self.cached_path = ""
        self.valid_wells = []

        self.init_ui()
        self.log("System initialized. Ready for operations.")

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # ---------------- Left Control Panel ----------------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # Step 1: Rename Section
        left_layout.addWidget(QLabel("<b>Step 1: Filename Standardizer</b>"))
        self.rename_dir_input = QLineEdit()
        self.rename_dir_input.setPlaceholderText("Select the directory containing raw TIFs...")
        self.btn_browse_rename = QPushButton("Browse")
        self.btn_browse_rename.clicked.connect(lambda: self.browse_folder(self.rename_dir_input))

        h_rename1 = QHBoxLayout()
        h_rename1.addWidget(self.rename_dir_input)
        h_rename1.addWidget(self.btn_browse_rename)
        left_layout.addLayout(h_rename1)

        self.rename_day = QLineEdit()
        self.rename_day.setPlaceholderText("e.g., 1 or 2")
        self.btn_run_rename = QPushButton("Run Rename Task")
        self.btn_run_rename.setStyleSheet("background-color: #2E86C1; color: white; font-weight: bold;")
        self.btn_run_rename.clicked.connect(self.on_run_rename)

        h_rename2 = QHBoxLayout()
        h_rename2.addWidget(QLabel("Day Index:"))
        h_rename2.addWidget(self.rename_day)
        h_rename2.addWidget(self.btn_run_rename)
        left_layout.addLayout(h_rename2)

        left_layout.addWidget(QLabel("<hr>"))

        # Step 2: Parameter Configuration Section
        left_layout.addWidget(QLabel("<b>Step 2: Parameter Configuration</b>"))
        grid = QGridLayout()

        grid.addWidget(QLabel("Well Name:"), 0, 0)
        self.in_well_name = QLineEdit()
        self.in_well_name.setPlaceholderText("e.g. A02 or C05")
        grid.addWidget(self.in_well_name, 0, 1)

        grid.addWidget(QLabel("Day Index:"), 1, 0)
        self.in_day = QLineEdit()
        self.in_day.setPlaceholderText("e.g., 1 or 2")
        grid.addWidget(self.in_day, 1, 1)

        grid.addWidget(QLabel("Image Folder:"), 2, 0)
        self.in_img_dir = QLineEdit()
        self.btn_browse_img = QPushButton("Browse")
        self.btn_browse_img.clicked.connect(lambda: self.browse_folder(self.in_img_dir))
        h_img = QHBoxLayout()
        h_img.addWidget(self.in_img_dir)
        h_img.addWidget(self.btn_browse_img)
        grid.addLayout(h_img, 2, 1)

        grid.addWidget(QLabel("Nanowell R (px):"), 3, 0)
        self.in_well_r = QLineEdit('180')
        self.in_well_r.setToolTip("Individual Well Radius (pixels)")
        grid.addWidget(self.in_well_r, 3, 1)

        grid.addWidget(QLabel("Boundary R (px):"), 4, 0)
        self.in_bound_r = QLineEdit('7500')
        self.in_bound_r.setToolTip("Boundary outer radius (pixels)")
        grid.addWidget(self.in_bound_r, 4, 1)

        grid.addWidget(QLabel("Square Length (px):"), 5, 0)
        self.in_sq_len = QLineEdit('370')
        self.in_sq_len.setToolTip("Origin marker side length (pixels)")
        grid.addWidget(self.in_sq_len, 5, 1)

        grid.addWidget(QLabel("Pitch (px):"), 6, 0)
        self.in_pitch = QLineEdit("462")
        self.in_pitch.setToolTip("Adjacent center-to-center well pitch (pixels)")
        grid.addWidget(self.in_pitch, 6, 1)
        left_layout.addLayout(grid)

        # Step 3: Calculation & Coordinates Section
        self.btn_calc = QPushButton("📊 Calculate Initial Parameters")
        self.btn_calc.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold;")
        self.btn_calc.clicked.connect(self.on_run_calculation)
        left_layout.addWidget(self.btn_calc)

        grid_calc = QGridLayout()
        grid_calc.addWidget(QLabel("Calculated Angle (°):"), 0, 0)
        self.out_angle = QLineEdit()
        grid_calc.addWidget(self.out_angle, 0, 1)

        grid_calc.addWidget(QLabel("Center X (px):"), 1, 0)
        self.out_cx = QLineEdit()
        grid_calc.addWidget(self.out_cx, 1, 1)

        grid_calc.addWidget(QLabel("Center Y (px):"), 2, 0)
        self.out_cy = QLineEdit()
        grid_calc.addWidget(self.out_cy, 2, 1)
        left_layout.addLayout(grid_calc)

        # Step 4: Visualization and Cropping Section
        # Section 4.1: visualization
        self.btn_visualize = QPushButton("👁️ Visualize / Update Preview")
        self.btn_visualize.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold;")
        self.btn_visualize.clicked.connect(self.on_run_visualization)
        left_layout.addWidget(self.btn_visualize)

        # Section 4.2: crop size definition
        crop_size_container = QWidget()
        h_crop_size = QHBoxLayout(crop_size_container)
        h_crop_size.setContentsMargins(0, 5, 0, 5)
        h_crop_size.addWidget(QLabel("Crop Resolution (px):"))

        self.cb_default_size = QCheckBox("380")  # Default Option (380 px)
        self.cb_default_size.setChecked(True)
        self.cb_other_size = QCheckBox("Other:") # Custom Option (Other)
        self.in_custom_size = QLineEdit()
        self.in_custom_size.setPlaceholderText("Enter size...")
        self.in_custom_size.setEnabled(False)

        # Connect mutual exclusivity toggles
        self.cb_default_size.toggled.connect(self.on_default_size_toggled)
        self.cb_other_size.toggled.connect(self.on_other_size_toggled)

        h_crop_size.addWidget(self.cb_default_size)
        h_crop_size.addWidget(self.cb_other_size)
        h_crop_size.addWidget(self.in_custom_size)
        left_layout.addWidget(crop_size_container)

        # Section 4.3: crop button
        self.btn_crop = QPushButton("✂️ Crop & Export All Nanowells")
        self.btn_crop.setStyleSheet("background-color: #8E44AD; color: white; font-weight: bold; font-size: 14px;")
        self.btn_crop.clicked.connect(self.on_run_cropping)
        left_layout.addWidget(self.btn_crop)

        # Step 5: Rollback Engine Section
        left_layout.addWidget(QLabel("<br><hr style='border: 1px dashed #E74C3C;'>"))
        rollback_title = QLabel("<b>⚠️ Emergency Rollback & Purge Engine</b>")
        rollback_title.setStyleSheet("color: #E67E22;")
        left_layout.addWidget(rollback_title)

        rollback_desc = QLabel("Deletes all exported single-well crops matching current inputs.")
        rollback_desc.setStyleSheet("font-size: 10px; color: #2C3E50;")
        left_layout.addWidget(rollback_desc)

        self.btn_rollback = QPushButton("🗑️ Purge Matching Cropped Wells")
        self.btn_rollback.setStyleSheet("background-color: #7B241C; color: #F5EEF8; font-weight: bold; font-size: 11px; border: 1px solid #C0392B;")
        self.btn_rollback.clicked.connect(self.on_run_rollback)
        left_layout.addWidget(self.btn_rollback)

        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # ---------------- Right Canvas & Console Panel ----------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        right_layout.addWidget(QLabel("<b>Real-time Interactive Mask Preview</b>"))
        self.canvas = InteractiveView(self)
        self.canvas.setMinimumSize(600, 500)
        self.canvas.setStyleSheet("background-color: #1B2631; border: 2px dashed #34495E;")
        right_layout.addWidget(self.canvas, stretch=4)

        right_layout.addWidget(QLabel("<b>Operation System Console Log</b>"))
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(
            "background-color: #FFFFFF;"
            "color: #1A252C;"
            "font-family: Consolas, 'Courier New', monospace;"
            "font-size: 12px;"
            "border: 1px solid #BDC3C7;"
            "border-radius: 4px;"
            "padding: 6px;"
        )
        right_layout.addWidget(self.console, stretch=1)

        splitter.addWidget(right_panel)
        splitter.setSizes([450, 950])

    def log(self, text: str):
        self.console.append(text)
        self.console.moveCursor(self.console.textCursor().MoveOperation.End)

    def browse_folder(self, target_lineedit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory", "C:/")
        if folder:
            target_lineedit.setText(folder)

    def ensure_image_loaded(self) -> bool:
        img_dir = self.in_img_dir.text().strip()
        well_name = self.in_well_name.text().strip()
        day = self.in_day.text().strip()

        if not img_dir or not well_name or not day:
            self.log("[WARNING]❌: Image Folder, Well Name, and Day Index must all be filled!")
            return False

        bgr, gray, full_path, err = core_crop.load_bf_image(img_dir, well_name, day)
        if err:
            self.log(f"[ERROR]✅: {err}")
            return False

        if self.cached_path != full_path:
            self.cached_bgr = bgr
            self.cached_gray = gray
            self.cached_path = full_path
            self.cached_gray_crop = None
            self.log(f"[SUCCESS]✅: Resolution loaded: {gray.shape[1]}x{gray.shape[0]}")

        return True

    def on_default_size_toggled(self, checked: bool):
        if checked:
            self.cb_other_size.blockSignals(True)
            self.cb_other_size.setChecked(False)
            self.cb_other_size.blockSignals(False)
            self.in_custom_size.setEnabled(False)
            self.in_custom_size.clear()

    def on_other_size_toggled(self, checked: bool):
        if checked:
            self.cb_default_size.blockSignals(True)
            self.cb_default_size.setChecked(False)
            self.cb_default_size.blockSignals(False)
            self.in_custom_size.setEnabled(True)
            self.log("[ATTENTION]: Custom dimension selected. Verify consistency for downstream pipelines.")
        elif not self.cb_default_size.isChecked():
            self.cb_default_size.setChecked(True)

    def on_run_rename(self):
        core_crop.rename_raw_files(
            directory=self.rename_dir_input.text(),
            day=self.rename_day.text(),
            log_callback=self.log
        )

    def on_run_calculation(self):
        if not self.ensure_image_loaded():
            return

        try:
            sq_len = int(self.in_sq_len.text().strip())
            nanowell_r = int(self.in_well_r.text().strip())
        except ValueError:
            self.log("[WARNING]❌: Nanowell R and Square Length must be valid integers!")
            return

        self.log("[CALCULATING]: Running thresholding and computer vision routines...")

        # 1. Square origin detection
        cx_text = self.out_cx.text().strip()
        cy_text = self.out_cy.text().strip()

        if cx_text and cy_text:
            self.log(f"[MANUAL]: Using user-defined Origin at X:{cx_text}, Y:{cy_text}")
        else:
            rect_center, self.cached_gray_crop, err = core_crop.detect_center_square(self.cached_gray, sq_len)
            if rect_center:
                self.out_cx.setText(str(rect_center[0]))
                self.out_cy.setText(str(rect_center[1]))
                self.log(f"[FOUND]✅: Central Origin calibrated at X:{rect_center[0]}, Y:{rect_center[1]}")
            else:
                self.log(f"[ERROR]❌: {err}")
                return

        # 2. Grid rotation angle estimation
        angle_text = self.out_angle.text().strip()
        if angle_text:
            self.log(f"[MANUAL]ℹ️: Using user-defined angle = {angle_text}°")
        else:
            angle, err = core_crop.detect_array_angle(self.cached_gray, nanowell_r)
            if angle is not None:
                self.out_angle.setText(f"{angle:.4f}")
                self.log(f"[FOUND]✅: Grid rotation angle calculated: {angle:.4f}°")
            else:
                self.log(f"[ERROR]❌: {err}")

    def on_run_visualization(self):
        if not self.ensure_image_loaded():
            return

        try:
            cx = int(self.out_cx.text().strip())
            cy = int(self.out_cy.text().strip())
            angle_val = float(self.out_angle.text().strip())
            bound_r = float(self.in_bound_r.text().strip())
            pitch = float(self.in_pitch.text().strip())
            nanowell_r = int(self.in_well_r.text().strip())
        except ValueError:
            self.log("[ERROR]❌: Parsing failed. Check Angle, Pitch, Boundary R, Nanowell R, and Coordinates.")
            return

        self.log("[VISUALIZING]: Regenerating math model grid overlay...")
        self.valid_wells, render_img = core_crop.generate_grid_overlay(
            self.cached_bgr, cx, cy, angle_val, bound_r, pitch, nanowell_r
        )

        h, w, ch = render_img.shape
        bytes_per_line = ch * w
        qimg = QImage(render_img.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
        self.canvas.set_image(QPixmap.fromImage(qimg))
        self.log(f"[SUCCESS]✅: Preview updated. Array micro-nodes tracked: {len(self.valid_wells)}")

    def on_run_cropping(self):
        if not self.valid_wells:
            self.log("[ERROR]❌: Layout grid is empty. Click 'Visualize' beforehand.")
            return

        try:
            nanowell_r = int(self.in_well_r.text().strip())
            if self.cb_other_size.isChecked():
                output_size = int(self.in_custom_size.text().strip())
            else:
                output_size = 380
        except ValueError:
            self.log("[ERROR]: Invalid pixel dimensions specified.")
            return

        if output_size < (2 * nanowell_r):
            self.log(f"[CRITICAL ABORT]❌: Output size ({output_size}px) is smaller than diameter ({2 * nanowell_r}px).")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            core_crop.execute_nanowell_crop(
                load_path=self.in_img_dir.text(),
                well_name=self.in_well_name.text(),
                day=self.in_day.text(),
                nanowell_r=nanowell_r,
                output_size=output_size,
                valid_wells=self.valid_wells,
                log_callback=self.log
            )
        finally:
            QApplication.restoreOverrideCursor()

    def on_run_rollback(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            core_crop.execute_rollback(
                load_path=self.in_img_dir.text(),
                well_name=self.in_well_name.text(),
                day=self.in_day.text(),
                log_callback=self.log
            )
        finally:
            QApplication.restoreOverrideCursor()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MicroscopyApp()
    window.show()
    sys.exit(app.exec())