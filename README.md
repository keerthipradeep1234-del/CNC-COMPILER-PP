# CNC Impeller Compiler & Visualizer

A Python-based desktop application designed to parse Fanuc G-code programs and simulate CNC turning and facing operations in real time. Built with **CustomTkinter** for a modern user interface and **Matplotlib** for toolpath rendering.

---

## 🚀 Key Features

* **G-Code Parsing & Compilation**: Reads and interprets Fanuc CNC canned cycles, specifically:
  * `G71`: Longitudinal turning and stock removal cycles.
  * `G72`: Facing canned cycles.
* **Interactive Toolpath Visualization**: Real-time rendering of tool passes, cutting inserts (e.g., CNMG 80° Roughing), and stock setup.
* **Customizable Stock Setup**: Adjust stock diameter and length dynamically before executing simulation cycles.
* **Playback & Speed Controls**: Interactive simulation playback with speed adjustments and execution diagnostics logging.
* **Modern GUI**: Responsive dark-themed user interface powered by CustomTkinter.

---

## 🛠️ Project Structure

```text
cnc_compiler_project/
├── main.py          # Main application GUI and event handlers
├── compiler.py      # G-code parser and canned cycle logic engine
├── geometry.py      # Stock profile and toolpath trajectory calculations
└── run_app.bat      # Batch launcher script
