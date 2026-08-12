# 🔬 Microscopy Nanowell Processor

A standalone GUI desktop tool designed to seamlessly process, align, and crop large-scale stitched microscopy images of circular nanowell arrays.

## 📁 Input Data Requirements (Raw Images)
Before running the processing engine, ensure your files are inside the same directory and adhere to the expected naming conventions. The software uses these patterns to automatically detect experimental groups.

* **Supported Formats:** `.tif` (Optimized for high-resolution stitched slides).
* **Supported Image names:** `Well[A-Z][0-9][0-9]_XXX_[Channel].tif` ( XXX can be anything. [Channel] has to be one of them in below)

| Channel | Standardized Channel Code | Optical Channel & Configuration Description |
| :--- | :--- | :--- |
| `RGB` | `RGB` | **Merged / Overlay Status**: A composite color image representing all captured channels merged together into a single frame for global previewing. |
| <code>20&nbsp;Phase</code>| `BF` | **Brightfield Channel**: Transmitted light imaging mode using a **20X** objective lens, primarily utilized for structural tracking and grid calibration. |
| `GFP` | `GFP` | **eGFP Fluorescence Channel**: Green fluorescent protein detection channel captured at a **20X** objective magnification, used to observe target cellular expressions. |
| `mCherry` | `mCherry` | **mCherry Fluorescence Channel**: Red fluorescent protein detection channel captured at a **20X** objective magnification, optimized for tracking red fluorophore expressions. |
> ⚠️ **Prerequisite Rule:** To perform any cropping operations, the **BF** (Brightfield) channel image **must be present** in the directory as it is strictly required for mathematical grid calibration. All other fluorescence channels (`GFP`, `mCherry`, `RGB`) are completely optional and can be included or omitted based on your experimental dataset.

## 📤 Output Data
Images will be remaned as `[WellName]_[TileMatrix]_Day[Index]_[Channel].tif`
* **Examples:**
  * `A02_Day1_BF.tif` (Brightfield image used for grid calibration)
  * `A02_Day1_GFP.tif` (Fluorescence channel)
  * `A02_Day1_mCherry.tif` (Fluorescence channel)

When you execute the batch crop command, the program calculates the absolute grid layout and generates an organized, multi-layered directory structure inside a parent folder named `Processed Wells`.

For every unique channel found, the program generates isolated subdirectories mapped directly to the individual physical row and column coordinates:

```text
Output Directory Tree/
└── Processed Wells/
    └── A01/                         <-- Target Well Name
        ├── BF/                     <-- Isolated Channel Folders
        │   ├── A01_R0_C0_Day1_BF.png            
        │   ├── A01_R0_C0_Day2_BF.png
        |   ├── A01_R0_C0_Day3_BF.png
        |   ├── ...
        │   ├── A01_R0_C1_Day1_BF.png
        │   ├── ... 
        │   └── A01_R5_C10_Day1_BF.png
        │    
        ├── GFP/
        │   ├── A01_R0_C0_Day1_GFP.png            
        │   ├── A01_R0_C0_Day2_GFP.png
        |   ├── A01_R0_C0_Day3_GFP.png
        |   ├── ...
        └── mCherry/
* **R** stands for **Row Index** (vertical position starting from 0)
* **C** stands for **Column Index** (horizontal position starting from 0)
R0_C0 is the Central Orientation Rectangle (Origin)
```

<img width="1351" height="900" alt="demo" src="https://github.com/user-attachments/assets/f7f32eb0-4bbc-43f5-9426-84753f429b06" />

Recommended tif exporting using NIS:
<img width="1277" height="857" alt="NIS_export" src="https://github.com/user-attachments/assets/a0c885a1-2759-43a8-99a7-f838d23832c4" />


