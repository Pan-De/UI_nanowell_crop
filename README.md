# 🔬 Microscopy Nanowell Processor

A standalone GUI desktop tool designed to seamlessly process, align, and crop large-scale stitched microscopy images of circular nanowell arrays.

## 📁 Input Data Requirements (Raw Images)
Before running the processing engine, ensure your files are inside the same directory and adhere to the expected naming conventions. The software uses these patterns to automatically detect experimental groups.

* **Supported Formats:** `.tif` (Optimized for high-resolution stitched slides).
* **Supported Image names:** `[WellName]_[TileMatrix]_Day[Index1]_XY[Index2]_[Channel].tif` ([Channel] has to be one of them in below)
* 
| Channel | Standardized Channel Code | Optical Channel & Configuration Description |
| :--- | :--- | :--- |
| `RGB` | `RGB` | **Merged / Overlay Status**: A composite color image representing all captured channels merged together into a single frame for global previewing. |
| `RGB_BF_20X` | `BF` | **Brightfield Channel**: Transmitted light imaging mode using a **20X** objective lens, primarily utilized for structural tracking and grid calibration. |
| `RGB_EGFP_20X` | `EGFP` | **EGFP Fluorescence Channel**: Green fluorescent protein detection channel captured at a **20X** objective magnification, used to observe target cellular expressions. |
| `RGB_mCherry_20X` | `mCherry` | **mCherry Fluorescence Channel**: Red fluorescent protein detection channel captured at a **20X** objective magnification, optimized for tracking red fluorophore expressions. |
> ⚠️ **Prerequisite Rule:** To perform any cropping operations, the **BF** (Brightfield) channel image **must be present** in the directory as it is strictly required for mathematical grid calibration. All other fluorescence channels (`EGFP`, `mCherry`, `RGB`) are completely optional and can be included or omitted based on your experimental dataset.

## 📤 Output Data
Images will be remaned as `[WellName]_[TileMatrix]_Day[Index]_[Channel].tif`
* **Examples:**
  * `2A_10x10_Day1_BF.tif` (Brightfield image used for grid calibration)
  * `2A_10x10_Day1_EGFP.tif` (Fluorescence channel)
  * `2A_10x10_Day1_mCherry.tif` (Fluorescence channel)

When you execute the batch crop command, the program calculates the absolute grid layout and generates an organized, multi-layered directory structure inside a parent folder named `Processed Wells` or `Wells/`.

For every unique channel found, the program generates isolated subdirectories mapped directly to the individual physical row and column coordinates:

```text
Output Directory Tree/
└── Processed Wells/
    └── 1A/                         <-- Target Well Name
        ├── BF/                     <-- Isolated Channel Folders
        │   ├── R0_C0/              <-- Unique Single-Well Node Folders
        │   │   ├── 1A_R0_C0_Day1.png
        |   |   ├── 1A_R0_C0_Day2.png
        |   |   ├── ...
        │   ├── R0_C1/
        │   │   └── 1A_R0_C1_Day1.png
        │   └── R1_C0/
        │       └── 1A_R1_C0_Day1.png
        ├── EGFP/
        │   ├── R0_C0/
        │   │   └── 1A_R0_C0_Day1.png
        │   └── R0_C1/
        │       └── 1A_R0_C1_Day1.png
        └── mCherry/
* **R** stands for **Row Index** (vertical position starting from 0)
* **C** stands for **Column Index** (horizontal position starting from 0)
R0_C0 is the Central Orientation Rectangle (Origin)
