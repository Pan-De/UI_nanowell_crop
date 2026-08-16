import os
import sys
import re
import math
import cv2
import numpy as np
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QTextEdit, QFileDialog, QGridLayout, QHBoxLayout, QVBoxLayout, QSplitter,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, QMouseEvent, QWheelEvent, QPainter

class InteractiveView(QGraphicsView):
    """
    Advanced interactive canvas supporting mouse wheel zooming (centered on the cursor)
    and left-click dragging to pan, allowing high-precision alignment checks.
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
        """Updates the background image while maintaining the current zoom state."""
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        # Enable bilinear filtering to keep edges smooth when zooming in on nanowells
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def wheelEvent(self, event: QWheelEvent):
        """Intercepts the mouse wheel event to zoom centered on the cursor position."""
        if self.pixmap_item is None:
            return

        # Anchor the transformation under the current mouse position
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # define the zoom in/out (scaling) factor（Zoom in/out by 15% per scroll step）
        scale_factor = 1.15
        if event.angleDelta().y() < 0:
            scale_factor = 1.0 / scale_factor
            
        self.scale(scale_factor, scale_factor)

class MicroscopyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔬 Microscopy Nanowell Processor & Crop Tool")
        self.resize(1400, 900)
        
        self.cached_gray = None
        self.cached_gray_crop = None
        self.cached_bgr = None
        self.cached_path = ""
        self.valid_wells = []

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # ---------------- left side ----------------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # Section 1: rename images
        left_layout.addWidget(QLabel("<b>⚡ Step 1: Filename Standardizer</b>"))
        self.rename_dir_input = QLineEdit()
        self.rename_dir_input.setPlaceholderText("Select the directory containing raw TIFs...")
        btn_browse_rename = QPushButton("Browse")
        btn_browse_rename.clicked.connect(lambda: self.browse_folder(self.rename_dir_input))

        h_rename = QHBoxLayout()
        h_rename.addWidget(self.rename_dir_input)
        h_rename.addWidget(btn_browse_rename)
        left_layout.addLayout(h_rename)

        #left_layout.addWidget(QLabel("Day Index:"))
        self.rename_day = QLineEdit()
        self.rename_day.setPlaceholderText("e.g., 1 or 2.")


        self.btn_run_rename = QPushButton("▶ Run Rename Task")
        self.btn_run_rename.setStyleSheet("background-color: #2E86C1; color: white; font-weight: bold;")
        self.btn_run_rename.clicked.connect(self.run_rename)
    
        
        h_rename2 = QHBoxLayout()
        h_rename2.addWidget(QLabel("Day Index:"))
        h_rename2.addWidget(self.rename_day)
        h_rename2.addWidget(self.btn_run_rename)
        left_layout.addLayout(h_rename2)


        left_layout.addWidget(QLabel("<hr>"))

        # Section 2: parameter configuration
        left_layout.addWidget(QLabel("<b>⚙️ Step 2: Parameter Configuration</b>"))
        
        grid = QGridLayout()
        grid.addWidget(QLabel("Well Name:"), 0, 0)
        self.in_well_name = QLineEdit()
        self.in_well_name.setPlaceholderText("e.g. A02 or C05")
        grid.addWidget(self.in_well_name, 0, 1)
  
        grid.addWidget(QLabel("Day Index:"), 2, 0)
        self.in_day = QLineEdit()
        self.in_day.setPlaceholderText("e.g., 1 or 2")
        grid.addWidget(self.in_day, 2, 1)

        grid.addWidget(QLabel("Image Folder:"), 3, 0)
        self.in_img_dir = QLineEdit()
        btn_browse_img = QPushButton("Browse")
        btn_browse_img.clicked.connect(lambda: self.browse_folder(self.in_img_dir))
        h_img = QHBoxLayout()
        h_img.addWidget(self.in_img_dir)
        h_img.addWidget(btn_browse_img)
        grid.addLayout(h_img, 3, 1)

        grid.addWidget(QLabel("Nanowell R (px):"), 4, 0)
        self.in_well_r = QLineEdit('180')
        #self.in_well_r.setPlaceholderText("e.g., 189")
        self.in_well_r.setToolTip("Individual Well Radius: The radius (in pixels) of a single circular nanowell")
        grid.addWidget(self.in_well_r, 4, 1)

        grid.addWidget(QLabel("Boundary R (px):"), 5, 0)
        self.in_bound_r = QLineEdit('7500')
        #self.in_bound_r.setPlaceholderText("e.g., 7500")
        self.in_bound_r.setToolTip("The maximum circular radius (in pixels) within which nanowells will be detected and processed.")
        grid.addWidget(self.in_bound_r, 5, 1)

        grid.addWidget(QLabel("Square Length (px):"), 6, 0)
        self.in_sq_len = QLineEdit('370')
        #self.in_sq_len.setPlaceholderText("e.g., 350")
        self.in_sq_len.setToolTip("Origin Box Size: The side length (in pixels) of the central square marker used to calibrate the grid's starting origin")
        grid.addWidget(self.in_sq_len, 6, 1)

        grid.addWidget(QLabel("Pitch (px):"), 7, 0)
        self.in_pitch = QLineEdit("462")
        #self.in_pitch.setPlaceholderText("e.g., 409")
        self.in_pitch.setToolTip("Pitch: Center-to-center distance between adjacent nanowells.")
        grid.addWidget(self.in_pitch, 7, 1)
        
        left_layout.addLayout(grid)

        # Section 3: Calculation & Parameter Adjustment
        self.btn_calc = QPushButton("📊 Calculate Initial Parameters")
        self.btn_calc.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold;")
        self.btn_calc.clicked.connect(self.run_calculation)
        left_layout.addWidget(self.btn_calc)

        grid_calc = QGridLayout()
        grid_calc.addWidget(QLabel("Calculated Angle (°):"), 0, 0)
        self.out_angle = QLineEdit()
        self.out_angle.setToolTip("The orientation angle (in degrees) of the nanowell array")
        grid_calc.addWidget(self.out_angle, 0, 1)

        grid_calc.addWidget(QLabel("Center X (px):"), 1, 0)
        self.out_cx = QLineEdit()
        self.out_cx.setToolTip("Array Origin: The absolute X pixel coordinates of the central grid origin. Clear the value to trigger autonomous re-detection")
        grid_calc.addWidget(self.out_cx, 1, 1)

        grid_calc.addWidget(QLabel("Center Y (px):"), 2, 0)
        self.out_cy = QLineEdit()
        self.out_cy.setToolTip("Array Origin: The absolute Y pixel coordinates of the central grid origin. Clear the value to trigger autonomous re-detection")
        grid_calc.addWidget(self.out_cy, 2, 1)
        left_layout.addLayout(grid_calc)

        # Section 4: visualize and crop nanowells
        # Section 4.1: visualization
        self.btn_visualize = QPushButton("👁️ Visualize / Update Preview")
        self.btn_visualize.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold;")
        self.btn_visualize.clicked.connect(self.run_visualization)
        left_layout.addWidget(self.btn_visualize)

        # Section 4.2: crop size definItion---
        crop_size_container = QWidget()
        h_crop_size = QHBoxLayout(crop_size_container)
        h_crop_size.setContentsMargins(0, 5, 0, 5) # Clean margins for vertical alignment
        
        h_crop_size.addWidget(QLabel("Crop Resolution (px):"))
        # 1. Default Option (380 px)
        self.cb_default_size = QCheckBox("380")
        self.cb_default_size.setChecked(True)  # Default state is checked
        
        # 2. Custom Option (Other)
        self.cb_other_size = QCheckBox("Other:")
        self.in_custom_size = QLineEdit()
        self.in_custom_size.setPlaceholderText("Enter size...")
        self.in_custom_size.setEnabled(False)
        self.in_custom_size.setToolTip("Specify custom dimension in pixels (Width & Height will be identical).")
        
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
        self.btn_crop.clicked.connect(self.run_cropping)
        left_layout.addWidget(self.btn_crop)

        # ---- INSERTED NEW SECTION: Crop Rollback & Cleanup Engine ----
        left_layout.addWidget(QLabel("<br><hr style='border: 1px dashed #E74C3C;'>"))
        
        rollback_title = QLabel("<b>⚠️ Emergency Rollback & Purge Engine</b>")
        rollback_title.setStyleSheet("color: #E67E22;")
        left_layout.addWidget(rollback_title)
        
        rollback_desc = QLabel("Deletes all exported single-well crops across all channels matching the current configuration criteria below.<br>"
                               "<b>Required:</b> Image Folder path, Well Name, Day Index")
        rollback_desc.setWordWrap(True)
        rollback_desc.setStyleSheet("font-size: 10px; color: #2C3E50;")
        left_layout.addWidget(rollback_desc)

        self.btn_rollback = QPushButton("🗑️ Purge Matching Cropped Wells")
        self.btn_rollback.setStyleSheet("background-color: #7B241C; color: #F5EEF8; font-weight: bold; font-size: 11px; border: 1px solid #C0392B;")
        self.btn_rollback.clicked.connect(self.run_rollback)
        left_layout.addWidget(self.btn_rollback)

        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # ---------------- Right side (visualization & console) ----------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        right_layout.addWidget(QLabel("<b>🖼️ Real-time Interactive Mask Preview (Scales down for display)</b>"))
        
        # Advanced adaptive canvas for high-resolution image rendering
        self.canvas = InteractiveView(self)
        self.canvas.setMinimumSize(600, 500)
        self.canvas.setStyleSheet("background-color: #1B2631; border: 2px dashed #34495E;")
        right_layout.addWidget(self.canvas, stretch=4)
        
        right_layout.addWidget(QLabel("<b>💻 Operation System Console Log</b>"))
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #1C2833; color: #2ECC71; font-family: Consolas; font-size: 11px;")
        right_layout.addWidget(self.console, stretch=1)

        splitter.addWidget(right_panel)
        
        # Set the initial layout split ratio between left and right panels
        splitter.setSizes([450, 950])
        self.log("System initialized. Ready for operations.")

    # ---------------- core business logic ----------------

    def log(self, text):
        self.console.append(text)
        self.console.moveCursor(self.console.textCursor().MoveOperation.End)

    def browse_folder(self, target_lineedit):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory", "C:/")
        if folder:
            target_lineedit.setText(folder)

    def load_bf_images(self):
        # return None if any information is missing
        if not self.in_img_dir.text().strip():
            self.log("[WARNING]: Image Folder cannot be empty!")
            return False
        if not self.in_well_name.text().strip():
            self.log("[WARNING]: Well Name cannot be empty!")
            return False
        if not self.in_day.text().strip():
            self.log("[WARNING]: Day Index cannot be empty!")
            return False

        # big stitched image
        img_dir = self.in_img_dir.text().strip().replace('\\', '/')
        well_name = self.in_well_name.text().strip()
        day = self.in_day.text().strip()

        bf_name = f"{well_name}_Day{day}_BF.tif"
        full_path = os.path.join(img_dir, bf_name)

        if self.cached_path == full_path and self.cached_gray is not None:
            return True

        if not os.path.exists(full_path):
            self.log(f"[ERROR]: Target Brightfield image not found at:\n{full_path}\n"
                    f"Cannot find the image named as {well_name}_Day{day}_BF.tif\n"
                    "Please standardise names first!")
            return False

        self.log(f"[INFO]: Loading high-res tile matrix image (8-bit Optimized Mode)...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.cached_bgr = cv2.imread(full_path, cv2.IMREAD_UNCHANGED)
            if len(self.cached_bgr.shape) == 2:
                self.cached_gray = self.cached_bgr.copy()
                self.cached_bgr = cv2.cvtColor(self.cached_bgr, cv2.COLOR_GRAY2BGR)
            else:
                self.cached_gray = cv2.cvtColor(self.cached_bgr, cv2.COLOR_BGR2GRAY)
            self.cached_path = full_path
            self.cached_gray_crop = None
            self.log(f"[SUCCESS]: Resolution loaded: {self.cached_gray.shape[1]}x{self.cached_gray.shape[0]}")
            return True
        except Exception as e:
            self.log(f"[CRITICAL]: Failed reading file: {e}")
            return False
        finally:
            QApplication.restoreOverrideCursor()

    def on_default_size_toggled(self, checked):
        """If Default is checked, uncheck Other and disable custom text input."""
        if checked:
            # Block signals temporarily to prevent infinite loop recursion between toggles
            self.cb_other_size.blockSignals(True)
            self.cb_other_size.setChecked(False)
            self.cb_other_size.blockSignals(False)
            
            self.in_custom_size.setEnabled(False)
            self.in_custom_size.clear()

    def on_other_size_toggled(self, checked):
        """If Other is checked, uncheck Default, enable text input, and prompt downstream warning."""
        if checked:
            self.cb_default_size.blockSignals(True)
            self.cb_default_size.setChecked(False)
            self.cb_default_size.blockSignals(False)
            
            self.in_custom_size.setEnabled(True)
            self.log("[ATTENTION]: Custom dimension selected. Please document this exact resolution configuration "
                     "to ensure consistency across your downstream automated data analysis pipelines.")
        else:
            # If user unchecks 'Other', automatically fall back to checking 'Default'
            if not self.cb_default_size.isChecked():
                self.cb_default_size.setChecked(True)

    def run_rename(self):
        directory = self.rename_dir_input.text().strip().replace('\\','/')
        day = self.rename_day.text().strip()
        if not day:
            self.log("[WARNING]: Day Index cannot be empty!")
            return False

        if not directory:
            self.log(f"[WARNING]: Directory not found: {directory}")
            return False 


        
        self.log(f"[START]: Scanning files inside directory: {directory}")
        channel_map = {'20X Phase': 'BF', 'mCherry': 'mCherry', 'GFP': 'GFP', 'RGB': 'RGB'}
        match_count = 0
        
        try:
            files = os.listdir(directory)
            for filename in files:
                if not filename.lower().endswith('.tif'):
                    continue
                
                match_check_good = re.match(r"[A-Z]\d{2}_Day\d+_(.*)\.tif$", filename)
                if match_check_good:
                    if match_check_good.group(1)in {"RGB","BF","GFP","mCherry"}: # found correctly named file
                        match_count += 1
                                            
                match_check = re.match(r"^Well([A-Z]\d{2})_(.*)_(.*)\.tif$", filename)
                # need to rename the file
                if match_check:
                    well, rest = match_check.group(1), match_check.group(3)
                    channel = channel_map.get(rest, "UNKNOWN")
                    new_filename = f"{well}_Day{day}_{channel}.tif"
                    match_count += 1                                    
                    os.rename(os.path.join(directory, filename), os.path.join(directory, new_filename))
                    self.log(f"-> Renamed successfully: '{filename}' to '{new_filename}'")

            if match_count > 0:
                self.log(f"[FINISH]: Rename Task Complete. {match_count} total file(s) structured.")
            else:
                self.log("[Warning]: No matching files found. Check your images' names. Example accepted name: WellA02_XXX_20X Phase.tif")

        except Exception as e:
            self.log(f"[ERROR]: Rename engine failed: {e}")

    def run_calculation(self):
        if not self.load_bf_images():
            return
        if not self.in_bound_r.text():
            self.log("[WARNING]: Boundary r cannot be empty!")
            return
        if not self.in_well_r.text():
            self.log("[WARNING]: Nanowell R cannot be empty!")
            return
        if not self.in_sq_len.text():
            self.log("[WARNING]: Square nanowell length cannot be empty!")
            return
        if not self.in_pitch.text():
            self.log("[WARNING]: Pitch cannot be empty!")
            return
        


        self.log("[CALCULATING]: Running background threshold and computer vision segmentations...")
        
        # 1. find square if the center coordinates are empty
        cx_text = self.out_cx.text().strip()
        cy_text = self.out_cy.text().strip()

        #    Skip the center/square detection if user-defined center coordinates are found
        rect_center = None
        if cx_text and cy_text:
            try:
                rect_center = (int(cx_text), int(cy_text))
                self.log(f"[MANUAL]: Using user-defined Central Origin at X:{rect_center[0]}, Y:{rect_center[1]}")
                self.log("[TIP]: To reactivate autonomous detection in center coordinates, please clear the Center X and Y coordinates.")
            except ValueError:
                self.log("[WARNING]: Manual coordinates parsing failed. Falling back to autonomous detection...")
        

        # crop the raw image if it is too large (size > roi_size)
        roi_size = 6000
        img_h, img_w = self.cached_gray.shape[:2]
        img_cx, img_cy = img_w // 2, img_h // 2

        # 1.1 Define bounding coordinates for the central ROI
        half_roi = roi_size // 2
        roi_x1 = max(0, img_cx - half_roi)
        roi_y1 = max(0, img_cy - half_roi)
        roi_x2 = min(img_w, img_cx + half_roi)
        roi_y2 = min(img_h, img_cy + half_roi)


        # find the square
        if rect_center is None:
            if self.cached_gray_crop is None:
                # 1.2 Extract zero-copy ROI slice
                roi_gray = self.cached_gray[roi_y1:roi_y2, roi_x1:roi_x2]

                # 1.3 pre-process the cropped image
                _, binary = cv2.threshold(roi_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13,13))
                # fill white gaps on the nanowell wall
                binary_fill_wt = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
                # fill black gaps inside nanowell
                binary_fil_bk = cv2.morphologyEx(binary_fill_wt, cv2.MORPH_CLOSE, kernel)

                self.cached_gray_crop = binary_fil_bk


            sq_len = int(self.in_sq_len.text()) # user-defined square length
            contours, _ = cv2.findContours(self.cached_gray_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area, max_area = (sq_len - 50)**2, (sq_len + 50)**2

            best_score = float('inf')

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < min_area or area > max_area: continue
             
                (cx, cy), (w, h), _ = cv2.minAreaRect(cnt)
                if h == 0 or w == 0: continue

                rect_box_area = w * h
                extent = float(area) / rect_box_area
                # Remove circles. circle's extent= ~ 0.785 (π/4)
                if extent < 0.85: continue

                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
                # Polygons approximated from circles usually have > 8 vertices, while rounded squares typically have between 4 and 8
                if not (4 <= len(approx) <= 8): continue

                aspect_ratio = float(w)/ h
                score = abs(1- aspect_ratio) # best score is 0.0
                if 0.85 <= aspect_ratio <= 1.15:
                    if score < best_score:
                        rect_center = (int(cx + roi_x1), int(cy + roi_y1))
            
            if rect_center:
                self.out_cx.setText(str(rect_center[0]))
                self.out_cy.setText(str(rect_center[1]))
                self.log(f"[FOUND]: Central Origin calibrated at X:{rect_center[0]}, Y:{rect_center[1]}")
            else:
                self.log("[ERROR]: Could not autonomously locate central origin square.\n Please try another Square Length or enter pixel coordinates manually.")
                return

        # 2. find the rotation angle
        angle_text = self.out_angle.text().strip()

        rotation_angle = None
        if angle_text:
            try:
                rotation_angle = float(angle_text)
                self.log(f"[MANUAL]: Using user-defined angle ={angle_text}")
                self.log("[TIP]: To reactivate autonomous angle detection, please clear the Angle textbox.")
            except ValueError:
                self.log("[WARNING]: Manual angle parsing failed. Falling back to autonomous detection...")

        if rotation_angle is None:
            roi_rotation = 12000
            
            half_roi_rotation = roi_rotation // 2
            roi_r_x1 = max(0, img_cx - half_roi_rotation)
            roi_r_y1 = max(0, img_cy - half_roi_rotation)
            roi_r_x2 = min(img_w, img_cx + half_roi_rotation)
            roi_r_y2 = min(img_h, img_cy + half_roi_rotation)
            roi_r_gray = self.cached_gray[roi_r_y1:roi_r_y2, roi_r_x1:roi_r_x2]
            roi_rotation = min(roi_rotation, min(img_cx, img_cy))

            try:
                nanowell_r = int(self.in_well_r.text())
                
                blurred = cv2.medianBlur(roi_r_gray, 5)
                circles = cv2.HoughCircles(
                    blurred, cv2.HOUGH_GRADIENT, dp=2, minDist=int(nanowell_r * 2),
                    param1=70, param2=30, minRadius=int(nanowell_r * 0.85), maxRadius=int(nanowell_r * 1.15)
                )

                if circles is not None and len(circles[0]) >= 100:
                    centers = circles[0][:, :2]
                    dominant_angles = []
                    centers_sorted = centers[centers[:, 1].argsort()]
                    
                    for _ in range(2000):
                        p1 = centers_sorted[np.random.randint(0, len(centers))]
                        p2 = centers_sorted[np.random.randint(0, len(centers))]
                        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                        if math.sqrt(dx*dx + dy*dy) < roi_rotation // 5: continue
                        angle = math.degrees(math.atan2(dy, dx))
                        temp_angle = angle % 60.0
                        if temp_angle > 30.0: temp_angle -= 60.0
                        dominant_angles.append(temp_angle)

                    counts, bin_edges = np.histogram(dominant_angles, bins=1200, range=(-30, 30))
                    refined_angle = (bin_edges[np.argmax(counts)] + bin_edges[np.argmax(counts) + 1]) / 2.0
                    self.out_angle.setText(f"{refined_angle:.4f}")
                    self.log(f"[FOUND]: Optimized grid rotation angle calculated: {refined_angle:.4f}°")
                
                else:
                    self.log("[ERROR]: Insufficient circular nodes (< 100 circles) extracted via Hough Transform. Kept angle as default.")

            except cv2.error as e:
                self.log("[ERROR]: Entered Nanowell R is likely too small or incorrect for this image size.")
                self.log("[ACTION]: Software saved from crash! Please enter a valid Nanowell R and try again.")
            except Exception as e:
                self.log(f"[ERROR]: Unexpected failure during angle detection: {e}")

    def run_visualization(self):
        if not self.load_bf_images():
            return

        self.log("[VISUALIZING]: Regenerating math model grid overlay...")
        
        try:
            cx = int(self.out_cx.text())
            cy = int(self.out_cy.text())
            angle_val = float(self.out_angle.text())
            bound_r = float(self.in_bound_r.text())
            pitch = float(self.in_pitch.text())
            nanowell_r = int(self.in_well_r.text())
        except ValueError:
            self.log("[ERROR]: Configuration parser exception.")
            self.log("[TIP]: Double check Angle, Pitch, Boundary R, Nanowell R, Center X and Center Y.")
            return

        # Draw the mask on the bright-field nanowell image
        render_img = self.cached_bgr.copy()
        row_spacing = pitch * math.sin(math.pi / 3.0)
        max_rows = int(bound_r / row_spacing) + 2
        max_cols = int(bound_r / pitch) + 2

        theta = math.radians(angle_val)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        
        self.valid_wells = []

        for row in range(-max_rows, max_rows + 1):
            local_y = row * row_spacing
            is_odd_row = (row % 2 != 0)
            x_offset = (pitch / 2.0) if is_odd_row else 0.0
            for col in range(-max_cols, max_cols + 1):
                local_x = col * pitch + x_offset
                
                if local_x**2 + local_y**2 <= bound_r**2:
                    rot_x = local_x * cos_t - local_y * sin_t
                    rot_y = local_x * sin_t + local_y * cos_t
                    gx = int(cx + rot_x)
                    gy = int(cy + rot_y)

                    if is_odd_row:
                        update_col = col + 1 if col >= 0 else col
    
                    else:
                        update_col = col                    
                
                    self.valid_wells.append((gx, gy, row, update_col))
    
                    cv2.circle(render_img, (gx, gy), nanowell_r, (0, 0, 255), 25)

    
        cv2.circle(render_img, (cx, cy), int(bound_r), (255, 0, 0), 30)
        cv2.circle(render_img, (cx, cy), nanowell_r, (0, 255, 0), 25)

        # rescale the image and display
        h, w, ch = render_img.shape
        bytes_per_line = ch * w
        qimg = QImage(render_img.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(qimg)

        # Stream the full-resolution image straight into the interactive view container
        self.canvas.set_image(pixmap)
        self.log(f"[SUCCESS]: Preview sync completed. Total array micro-nodes tracked: {len(self.valid_wells)}")

    def run_cropping(self):
        if not self.valid_wells:
            self.log("[ERROR]: Layout grid is empty. Please trigger 'Visualize' successfully beforehand.")
            return

        try:
            nanowell_r = int(self.in_well_r.text())
        except ValueError:
            self.log("[ERROR] Nanowell R cannot be empty!")

        # Determine target bounding canvas size dynamically based on UI checkbox configuration
        if self.cb_other_size.isChecked():
            try:
                output_size = int(self.in_custom_size.text().strip())
            except ValueError:
                self.log("[ERROR]: Failed to parse the custom crop size input. Please input an integer pixel value.")
                return
            
            # Boundary threshold safety verification rule validation
            if output_size < (2 * nanowell_r):
                self.log(f"[CRITICAL ABORT]: The target custom size ({output_size} px) is structurally smaller "
                         f"than the physical diameter of the current nanowell matrix ({2 * nanowell_r} px). "
                         f"Processing terminated to prevent data truncation errors.")
                return
        else:
            if 2* nanowell_r > 380:
                self.log(f"[CRITICAL ABORT]: The default size (380 px) is structurally smaller "
                         f"than the physical diameter of the current nanowell matrix ({2 * nanowell_r} px). "
                         f"Processing terminated to prevent data truncation errors."
                         f"Please check the box (Other) to define a new size.")
                return
            else: output_size = 380

          
        load_path = self.in_img_dir.text().strip().replace('\\', '/')
        well_name = self.in_well_name.text().strip()
        day = self.in_day.text().strip()
        nanowell_r = int(self.in_well_r.text())

        # Boundary threshold safety verification rule validation
        if output_size < (2 * nanowell_r):
            self.log(f"[CRITICAL ABORT]: The target custom size ({output_size} px) is structurally smaller "
                        f"than the physical diameter of the current nanowell matrix ({2 * nanowell_r} px). "
                        f"Processing terminated to prevent data truncation errors.")

        save_base_path = os.path.join(Path(load_path).parent, "Processed Wells", well_name)
        Path(save_base_path).mkdir(parents=True, exist_ok=True)
        half_size = output_size//2

        files = os.listdir(load_path)
        pattern = rf"^{well_name}_Day{day}_(.*)\.tif$"
        matched_channels = {}
        
        for filename in files:
            match = re.match(pattern, filename)
            if match:
                channel = match.group(1)
                if channel not in matched_channels:
                    matched_channels[channel] = os.path.join(load_path, filename)
                    Path(os.path.join(save_base_path, channel)).mkdir(parents=True, exist_ok=True)

        if not matched_channels:
            self.log("[ERROR]: Could not find any standardized channel image sets. Crop process terminated.")
            return

        # generate a digital mask overlay
        digital_mask = np.zeros((output_size, output_size), dtype=np.uint8)
        cv2.circle(digital_mask, (half_size, half_size), nanowell_r, (255, 255, 255), -1)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for key_channel, img_path in matched_channels.items():
                self.log(f"[BATCHING]: Crop executing for channel [{key_channel}]...")
                
                image = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
                img_h, img_w = image.shape[:2]
                skip_count = 0
                
                for (cx, cy, row, col) in self.valid_wells:
                    y1 = int(cy) - nanowell_r
                    y2 = y1 + output_size
                    x1 = int(cx) - nanowell_r
                    x2 = x1 + output_size

                    if y1 < 0 or x1 < 0 or y2 > img_h or x2 > img_w:
                        skip_count += 1
                        continue

                    square_crop = image[y1:y2, x1:x2]
                    cropped_with_mask = cv2.bitwise_and(square_crop, square_crop, mask=digital_mask)

                    new_filename = f"{well_name}_R{row}_C{col}_Day{day}_{key_channel}.png"
                    #new_folder = os.path.join(save_base_path, key_channel, f"R{row}_C{col}")
                    new_folder = os.path.join(save_base_path, key_channel)
                    Path(new_folder).mkdir(parents=True, exist_ok=True)
                    save_path = os.path.join(new_folder, new_filename)
                    cv2.imwrite(save_path, cropped_with_mask)
                    
                self.log(f"-> Channel [{key_channel}] extracted. Skipped {skip_count} boundary nodes safely.")
            
            self.log(f"[COMPLETE 🏁]: All channels cropped flawlessly. Destination root:\n{save_base_path}")
        except Exception as e:
            self.log(f"[CRITICAL ERROR]: Crop runtime failure: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def run_rollback(self):
        """
        Scans all channels under the 'Wells/{well_name}' tracking directory and purges 
        individual cropped images matching the current parameters to resolve human configuration mistakes.
        """
        # Validate that necessary parameter entries are available
        if not self.in_img_dir.text().strip():
            self.log("[ROLLBACK ABORT]: Image Folder path must be filled to determine the parent destination root.")
            return
        if not self.in_well_name.text().strip():
            self.log("[ROLLBACK ABORT]: Well Name parameter cannot be empty.")
            return
        if not self.in_day.text().strip():
            self.log("[ROLLBACK ABORT]: Day Index parameter cannot be empty.")
            return

        load_path = self.in_img_dir.text().strip().replace('\\', '/')
        well_name = self.in_well_name.text().strip()
        day = self.in_day.text().strip()

        # Reconstruct the precise export base directory matching the run_cropping output scheme
        save_base_path = os.path.join(Path(load_path).parent, "Processed Wells", well_name)

        if not os.path.exists(save_base_path):
            self.log(f"[ROLLBACK INFO]: Target root directory does not exist. No files found to purge:\n{save_base_path}")
            return

        self.log(f"[ROLLBACK START]: Initializing safe filesystem search inside: {save_base_path}")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        purged_file_count = 0
        purged_folder_count = 0
        
        try:
            # Iterate through all available channel folders (e.g., BF, mCherry, GFP)
            for channel_item in os.listdir(save_base_path):
                channel_dir = os.path.join(save_base_path, channel_item)
                if not os.path.isdir(channel_dir):
                    continue
                if channel_item not in ("BF", "RGB", "mCherry", "GFP"): continue
               
                for img_name in os.listdir(channel_dir):
                    match_check = re.match(rf"{well_name}_(.*)_Day{day}_(.*)\.png$", img_name)
                    if match_check:
                        target_file_path = os.path.join(channel_dir, img_name)
                        os.remove(target_file_path)
                        purged_file_count += 1
                        
                # Clean up: If the coordinate folder is now completely empty, delete it to keep directories pristine
                if len(os.listdir(channel_dir)) == 0:
                    os.rmdir(channel_dir)
                    purged_folder_count += 1                       
                    

            if purged_file_count > 0:
                self.log(f"[ROLLBACK COMPLETE 🏁]: Purged {purged_file_count} single-well target files and wiped "
                         f"{purged_folder_count} empty coordinate folders safely across all tracked channels.")
            else:
                self.log(f"[ROLLBACK WARNING]: No image files matched the specific naming template: "
                         f"'{well_name}_R*_C*_Day{day}.png' inside the directory layout.")
                         
        except Exception as e:
            self.log(f"[CRITICAL ROLLBACK ERROR]: Filesystem interaction exception occurred: {e}")
        finally:
            QApplication.restoreOverrideCursor()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MicroscopyApp()
    window.show()
    sys.exit(app.exec())