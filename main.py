import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import re
from tkinter import filedialog
from geometry import draw_rotating_chuck_and_jaws, draw_lathe_tool, render_dynamic_workpiece
from compiler import parse_gcode, r_to_ij

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("CNC Learning Compiler & Visualizer")
app.geometry("450x320")
app.resizable(True, True)

animation_job = None
current_anim_index = 0
animated_segments = []
is_playing = False
active_insert_patch = None
active_holder_patch = None
chuck_rotation_angle = 0.0
global_move_segments = []
active_chips = []
chosen_machine = "CNC Lathe Machine"
job_fixed = False
spindle_status = "OFF"
spindle_speed = 0
coolant_status = "OFF"

def export_gcode():
    file_path = filedialog.asksaveasfilename(defaultextension=".nc", filetypes=[("G-Code Files", "*.nc *.gcode *.txt"), ("All Files", "*.*")])
    if file_path:
        try:
            with open(file_path, "w") as f:
                f.write(text_editor.get("0.0", "end"))
            feedback_textbox.insert("end", f"\n💾 G-Code successfully exported to:\n{file_path}\n")
            feedback_textbox.see("end")
        except Exception as e:
            feedback_textbox.insert("end", f"\n❌ Failed to save: {e}\n", "error")
            feedback_textbox.see("end")

def parse_and_plot():
    global animation_job, current_anim_index, animated_segments, is_playing
    global global_move_segments, job_fixed, spindle_status, spindle_speed, coolant_status
    
    if not job_fixed:
        feedback_textbox.delete("0.0", "end")
        feedback_textbox.insert("end", "⚠ Please click 'Fix Job' first to mount the workpiece!\n", "error")
        feedback_textbox.see("end")
        return
        
    if animation_job is not None:
        app.after_cancel(animation_job)
        animation_job = None
    is_playing = False
    play_btn.configure(text="▶ Play")
    active_chips.clear()
    
    ax.clear()
    selected_tool = tool_dropdown.get()
    ax.set_title(f"CNC Lathe ({selected_tool}) | Spindle: {spindle_status} ({spindle_speed} RPM) | Coolant: {coolant_status}")
    ax.set_xlabel("Z Axis (Length mm)")
    ax.set_ylabel("X Radius (mm)")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.set_facecolor("white")
    
    stock_dia = float(stock_dia_entry.get())
    stock_len = float(stock_len_entry.get())
    stock_radius = stock_dia / 2.0
    
    raw_gcode = text_editor.get("0.0", "end").strip().splitlines()
    feedback_textbox.delete("0.0", "end")
    feedback_textbox.insert("end", f"=== CNC {chosen_machine.upper()} COMPILER ===\n\n")
    
    expanded_instructions, logs = parse_gcode(raw_gcode, stock_radius=stock_radius, stock_len=stock_len)
    for log in logs:
        feedback_textbox.insert("end", log + "\n")
        
    has_collision_error = any("ALARM" in log or "COLLISION" in log or "CRASH" in log for log in logs)
    
    if has_collision_error:
        feedback_textbox.insert("end", "\n❌ COMPILATION HALTED: Chuck collision or safety boundary violation detected!\n", "error")
        feedback_textbox.see("end")
        draw_rotating_chuck_and_jaws(ax, stock_len, stock_radius, chuck_rotation_angle, job_fixed)
        ax.axhline(0, color="white", linestyle="-.", linewidth=0.8, alpha=0.7, label="Centerline", zorder=5)
        ax.legend(loc="upper left")
        ax.axis("equal")
        canvas.draw()
        return

    curr_x, curr_z = stock_radius, 5.0
    global_move_segments = []
    
    for line_num, cmd_line in enumerate(expanded_instructions, 1):
        tokens = re.findall(r"([A-Z])([-+]?\d*\.?\d+)", cmd_line)
        command_dict = {key: float(val) for key, val in tokens}
        
        if "G" in command_dict:
            g_code = int(command_dict["G"])
            if g_code in [0, 1]:
                new_x = command_dict.get("X", curr_x * 2.0) / 2.0
                new_z = command_dict.get("Z", curr_z)
                global_move_segments.append(([curr_z, new_z], [curr_x, new_x], g_code))
                curr_x, curr_z = new_x, new_z
            elif g_code in [2, 3]:
                new_x = command_dict.get("X", curr_x * 2.0) / 2.0
                new_z = command_dict.get("Z", curr_z)
                i_off = command_dict.get("I", 0.0)
                j_off = command_dict.get("J", 0.0)
                r_val = command_dict.get("R", None)
                if r_val is not None:
                    i_off, j_off = r_to_ij(curr_z, curr_x, new_z, new_x, r_val, g_code == 2)
                from geometry import generate_arc_points
                arc_z, arc_x = generate_arc_points(curr_z, curr_x, new_z, new_x, i_off, j_off, g_code == 2)
                global_move_segments.append((arc_z, arc_x, g_code))
                curr_x, curr_z = new_x, new_z
        elif "M" in command_dict:
            m_code = int(command_dict["M"])
            if m_code == 3:
                spindle_status = "CW"
                spindle_speed = int(command_dict.get("S", 1200))
            elif m_code == 5:
                spindle_status = "OFF"
                spindle_speed = 0
            elif m_code == 8:
                coolant_status = "ON"
            elif m_code == 9:
                coolant_status = "OFF"
                
    animated_segments = []
    for z_pts, x_pts, g in global_move_segments:
        if len(z_pts) == 2:
            steps = 15
            interp_z = np.linspace(z_pts[0], z_pts[1], steps).tolist()
            interp_x = np.linspace(x_pts[0], x_pts[1], steps).tolist()
            for k in range(len(interp_z) - 1):
                animated_segments.append(([interp_z[k], interp_z[k+1]], [interp_x[k], interp_x[k+1]], g))
        else:
            for k in range(len(z_pts) - 1):
                animated_segments.append(([z_pts[k], z_pts[k+1]], [x_pts[k], x_pts[k+1]], g))
                
    current_anim_index = 0
    draw_rotating_chuck_and_jaws(ax, stock_len, stock_radius, chuck_rotation_angle, job_fixed)
    render_dynamic_workpiece(ax, stock_len, stock_radius, current_anim_index, animated_segments)
    ax.axhline(0, color="white", linestyle="-.", linewidth=0.8, alpha=0.7, label="Centerline", zorder=5)
    
    for z_pts, x_pts, g in global_move_segments:
        color = "#ff4d4d" if g == 0 else ("#00d2d3" if g == 1 else "#ff9f43")
        ax.plot(z_pts, x_pts, color=color, linestyle="--" if g == 0 else "-", linewidth=1.5, alpha=0.4, zorder=6)
        
    if global_move_segments:
        draw_lathe_tool(ax, global_move_segments[0][0][0], global_move_segments[0][1][0], selected_tool)
        
    ax.legend(loc="upper left")
    ax.axis("equal")
    canvas.draw()
    feedback_textbox.insert("end", "\nCompiled successfully!")
    feedback_textbox.see("end")

def render_initial_chuck_and_tool():
    ax.clear()
    selected_tool = tool_dropdown.get()
    ax.set_title(f"CNC Lathe Visualizer ({selected_tool}) - Job Unclamped")
    ax.set_xlabel("Z Axis (Length mm)")
    ax.set_ylabel("X Radius (mm)")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.set_facecolor("white")
    stock_len = float(stock_len_entry.get())
    stock_dia = float(stock_dia_entry.get())
    draw_rotating_chuck_and_jaws(ax, stock_len, stock_dia / 2.0, chuck_rotation_angle, job_fixed)
    ax.axhline(0, color="white", linestyle="-.", linewidth=0.8, alpha=0.7, zorder=5)
    draw_lathe_tool(ax, 20.0, 40.0, selected_tool)
    ax.axis("equal")
    canvas.draw()

def fix_job():
    global job_fixed
    job_fixed = True
    parse_and_plot()

def remove_job():
    global job_fixed, animation_job, is_playing
    if animation_job is not None:
        app.after_cancel(animation_job)
    is_playing = False
    play_btn.configure(text="▶ Play")
    job_fixed = False
    render_initial_chuck_and_tool()

def toggle_play_pause():
    global is_playing, current_anim_index
    if not animated_segments: return
    if not is_playing:
        if current_anim_index >= len(animated_segments): current_anim_index = 0
        is_playing = True
        play_btn.configure(text="⏸ Pause")
        update_animation_step()
    else:
        is_playing = False
        play_btn.configure(text="▶ Play")

def update_animation_step():
    global current_anim_index, animation_job, is_playing, chuck_rotation_angle
    if not animated_segments or current_anim_index >= len(animated_segments):
        is_playing = False
        play_btn.configure(text="▶ Play")
        return
    chuck_rotation_angle += 0.45 if spindle_status != "OFF" else 0.0
    z_seg, x_seg, g = animated_segments[current_anim_index]
    
    ax.clear()
    selected_tool = tool_dropdown.get()
    stock_len = float(stock_len_entry.get())
    stock_dia = float(stock_dia_entry.get())
    ax.set_title(f"CNC Lathe ({selected_tool})")
    ax.set_xlabel("Z Axis (Length mm)")
    ax.set_ylabel("X Radius (mm)")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.set_facecolor("white")
    
    draw_rotating_chuck_and_jaws(ax, stock_len, stock_dia / 2.0, chuck_rotation_angle, job_fixed)
    render_dynamic_workpiece(ax, stock_len, stock_dia / 2.0, current_anim_index + 1, animated_segments)
    ax.axhline(0, color="white", linestyle="-.", linewidth=0.8, alpha=0.7, zorder=5)
    
    for z_pts, x_pts, grp in global_move_segments:
        color = "#ff4d4d" if grp == 0 else ("#00d2d3" if grp == 1 else "#ff9f43")
        ax.plot(z_pts, x_pts, color=color, linestyle="--" if grp == 0 else "-", linewidth=1.2, alpha=0.3, zorder=6)
        
    draw_lathe_tool(ax, z_seg[1], x_seg[1], selected_tool, "#e74c3c" if g == 0 else "#f39c12")
    ax.axis("equal")
    canvas.draw_idle()
    current_anim_index += 1
    if is_playing:
        animation_job = app.after(int(speed_slider.get()), update_animation_step)

def reset_animation():
    global current_anim_index, is_playing, animation_job, chuck_rotation_angle
    if animation_job is not None: app.after_cancel(animation_job)
    is_playing = False
    play_btn.configure(text="▶ Play")
    current_anim_index = 0
    chuck_rotation_angle = 0.0
    if job_fixed: parse_and_plot()
    else: render_initial_chuck_and_tool()

def launch_main_workspace():
    global text_editor, tool_dropdown, stock_dia_entry, stock_len_entry
    global dia_slider, len_slider, play_btn, reset_btn, speed_slider, feedback_textbox, fig, ax, canvas
    
    for widget in app.winfo_children(): widget.destroy()
    app.geometry("1180x880")
    app.title("CNC Learning Compiler & Visualizer - Main Workspace")
    
    left_frame = ctk.CTkScrollableFrame(app, width=380, height=840)
    left_frame.pack(side="left", fill="y", padx=10, pady=10)
    
    editor_header = ctk.CTkFrame(left_frame, fg_color="transparent")
    editor_header.pack(padx=5, pady=(2, 2), fill="x")
    ctk.CTkLabel(editor_header, text="G-Code Editor", font=("Arial", 13, "bold")).pack(side="left", padx=2)
    ctk.CTkButton(editor_header, text="💾 Save", width=70, height=24, command=export_gcode, fg_color="#c0392b", hover_color="#e74c3c", font=("Arial", 10, "bold")).pack(side="right", padx=2)
    
    text_editor = ctk.CTkTextbox(left_frame, width=340, height=130)
    text_editor.pack(padx=5, pady=3)
    text_editor.insert("0.0", "M03 S1800 ;\nM08 ;\nG00 X60 Z5 ;\nG01 X20 Z0 F0.2 ;\nG03 X30 Z-10 R5 ;\nG02 X30 Z-25 R7.5 ;\nG01 X50 Z-40 ;\nM09 ;\nM30 ;")
    
    def paste_text(event):
        try:
            text_editor.insert("insert", app.clipboard_get())
        except Exception:
            pass
        return "break"

    def copy_text(event):
        try:
            selected = text_editor.get("sel.first", "sel.last")
            app.clipboard_clear()
            app.clipboard_append(selected)
        except Exception:
            pass
        return "break"

    def cut_text(event):
        try:
            selected = text_editor.get("sel.first", "sel.last")
            app.clipboard_clear()
            app.clipboard_append(selected)
            text_editor.delete("sel.first", "sel.last")
        except Exception:
            pass
        return "break"

    def undo_text(event):
        try:
            text_editor.edit_undo()
        except Exception:
            pass
        return "break"

    text_editor.bind("<Control-v>", paste_text)
    text_editor.bind("<Control-V>", paste_text)
    text_editor.bind("<Control-c>", copy_text)
    text_editor.bind("<Control-C>", copy_text)
    text_editor.bind("<Control-x>", cut_text)
    text_editor.bind("<Control-X>", cut_text)
    text_editor.bind("<Control-z>", undo_text)
    text_editor.bind("<Control-Z>", undo_text)

    tool_frame = ctk.CTkFrame(left_frame)
    tool_frame.pack(padx=5, pady=3, fill="x")
    ctk.CTkLabel(tool_frame, text="Tool Insert Selection", font=("Arial", 11, "bold")).pack(padx=5, pady=2)
    tool_dropdown = ctk.CTkOptionMenu(tool_frame, values=["CNMG (80° Roughing)", "DNMG (55° Profiling)", "Grooving / Parting"])
    tool_dropdown.pack(padx=5, pady=4, fill="x")
    tool_dropdown.set("CNMG (80° Roughing)")
    
    stock_frame = ctk.CTkFrame(left_frame)
    stock_frame.pack(padx=5, pady=3, fill="x")
    ctk.CTkLabel(stock_frame, text="Stock Dimensions & Setup", font=("Arial", 11, "bold")).pack(padx=5, pady=2)
    
    dia_row = ctk.CTkFrame(stock_frame, fg_color="transparent")
    dia_row.pack(padx=5, pady=2, fill="x")
    ctk.CTkLabel(dia_row, text="Dia (mm):").pack(side="left", padx=2)
    stock_dia_entry = ctk.CTkEntry(dia_row, width=45)
    stock_dia_entry.pack(side="left", padx=2)
    stock_dia_entry.insert(0, "60")
    dia_slider = ctk.CTkSlider(dia_row, from_=30, to=100, number_of_steps=70, command=lambda v: stock_dia_entry.delete(0, 'end') or stock_dia_entry.insert(0, f"{int(v)}") or (parse_and_plot() if job_fixed else render_initial_chuck_and_tool()))
    dia_slider.pack(side="right", fill="x", expand=True, padx=5)
    dia_slider.set(60)
    
    len_row = ctk.CTkFrame(stock_frame, fg_color="transparent")
    len_row.pack(padx=5, pady=2, fill="x")
    ctk.CTkLabel(len_row, text="Len (mm):").pack(side="left", padx=2)
    stock_len_entry = ctk.CTkEntry(len_row, width=45)
    stock_len_entry.pack(side="left", padx=2)
    stock_len_entry.insert(0, "45")
    len_slider = ctk.CTkSlider(len_row, from_=30, to=65, number_of_steps=35, command=lambda v: stock_len_entry.delete(0, 'end') or stock_len_entry.insert(0, f"{int(v)}") or (parse_and_plot() if job_fixed else render_initial_chuck_and_tool()))
    len_slider.pack(side="right", fill="x", expand=True, padx=5)
    len_slider.set(45)
    
    job_btn_row = ctk.CTkFrame(stock_frame, fg_color="transparent")
    job_btn_row.pack(padx=5, pady=4, fill="x")
    ctk.CTkButton(job_btn_row, text="🔒 Fix Job", command=fix_job, fg_color="#27ae60", hover_color="#2ecc71", font=("Arial", 11, "bold")).pack(side="left", expand=True, fill="x", padx=2)
    ctk.CTkButton(job_btn_row, text="🗑 Remove Job", command=remove_job, fg_color="#c0392b", hover_color="#e74c3c", font=("Arial", 11, "bold")).pack(side="right", expand=True, fill="x", padx=2)
    
    action_btn_row = ctk.CTkFrame(left_frame, fg_color="transparent")
    action_btn_row.pack(padx=5, pady=4, fill="x")
    ctk.CTkButton(action_btn_row, text="▶ Compile & Run Toolpath", command=parse_and_plot, fg_color="#10ac84", hover_color="#1dd1a1", font=("Arial", 11, "bold")).pack(side="left", expand=True, fill="x", padx=2)
    
    anim_frame = ctk.CTkFrame(left_frame)
    anim_frame.pack(padx=5, pady=3, fill="x")
    ctk.CTkLabel(anim_frame, text="Playback Controls", font=("Arial", 11, "bold")).pack(padx=5, pady=2)
    
    btn_row = ctk.CTkFrame(anim_frame, fg_color="transparent")
    btn_row.pack(padx=5, pady=2, fill="x")
    play_btn = ctk.CTkButton(btn_row, text="▶ Play", width=75, command=toggle_play_pause, fg_color="#0984e3")
    play_btn.pack(side="left", padx=4)
    reset_btn = ctk.CTkButton(btn_row, text="🔄 Reset", width=75, command=reset_animation, fg_color="#d63031")
    reset_btn.pack(side="left", padx=4)
    
    speed_row = ctk.CTkFrame(anim_frame, fg_color="transparent")
    speed_row.pack(padx=5, pady=2, fill="x")
    ctk.CTkLabel(speed_row, text="Speed:").pack(side="left", padx=2)
    speed_slider = ctk.CTkSlider(speed_row, from_=200, to=10, number_of_steps=19)
    speed_slider.set(50)
    speed_slider.pack(side="right", fill="x", expand=True, padx=5)
    
    ctk.CTkLabel(left_frame, text="Diagnostics Log", font=("Arial", 11, "bold")).pack(padx=5, pady=(3, 0))
    feedback_textbox = ctk.CTkTextbox(left_frame, width=340, height=85)
    feedback_textbox.pack(padx=5, pady=3)
    
    right_frame = ctk.CTkFrame(app)
    right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
    
    fig, ax = plt.subplots(figsize=(6, 5), dpi=100)
    canvas = FigureCanvasTkAgg(fig, master=right_frame)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
    
    render_initial_chuck_and_tool()

ctk.CTkLabel(app, text="Select CNC Manufacturing Unit", font=("Arial", 16, "bold")).pack(padx=20, pady=(25, 10))
ctk.CTkLabel(app, text="Select machine type:", font=("Arial", 11), text_color="#a4b0be").pack(padx=20, pady=(0, 20))
machine_var = ctk.StringVar(value="CNC Lathe Machine")
ctk.CTkRadioButton(app, text="CNC Lathe Machine", variable=machine_var, value="CNC Lathe Machine").pack(padx=40, pady=5, anchor="w")
ctk.CTkButton(app, text="Initialize Environment 🚀", command=launch_main_workspace, fg_color="#10ac84", font=("Arial", 12, "bold")).pack(padx=30, pady=(25, 20), fill="x")

app.mainloop()