import re
import numpy as np
from geometry import validate_lathe_boundaries

def r_to_ij(z1, x1, z2, x2, r, is_cw):
    """
    Accurately converts arc radius R into center offsets I (Z-axis offset) and K (X-axis offset)
    for a CNC lathe (X-Z plane).
    """
    dz = z2 - z1
    dx = x2 - x1
    q = np.hypot(dz, dx)
    
    if q < 1e-6:
        return 0.0, 0.0
    
    h = q / 2.0
    if abs(r) < h:
        r = h * 1.0001  # Prevent floating point precision errors underflow
        
    # Distance from chord midpoint to arc center
    discriminant = r**2 - h**2
    factor = np.sqrt(max(0.0, discriminant)) / q
    
    # Perpendicular vector components
    p_z = -dx * factor
    p_x = dz * factor
    
    mz = (z1 + z2) / 2.0
    mx = (x1 + x2) / 2.0
    
    # Correct arc center selection based on CW (G02) / CCW (G03) and sign of R
    if is_cw:
        if r > 0:
            cz = mz + p_z
            cx = mx + p_x
        else:
            cz = mz - p_z
            cx = mx - p_x
    else:  # CCW (G03)
        if r > 0:
            cz = mz - p_z
            cx = mx - p_x
        else:
            cz = mz + p_z
            cx = mx + p_x
            
    # Return incremental offsets (I for Z offset, K for X offset relative to start point)
    return cz - z1, cx - x1

def parse_gcode(raw_lines, stock_radius, stock_len=45.0):
    """
    Parses raw G-code lines, handles R-radius arcs by converting them to I/K centers,
    and validates safety boundaries against chuck jaws and stock dimensions.
    """
    expanded_instructions = []
    logs = []
    
    curr_x = stock_radius
    curr_z = 5.0
    
    g71_active = False
    g71_u = 0.0
    g71_r = 0.0
    g71_p = None
    g71_q = None
    g71_stock_u = 0.0
    g71_stock_w = 0.0
    g71_feed = 0.25
    
    labeled_blocks = {}
    clean_lines = []
    for line in raw_lines:
        line = line.split("(")[0].split(";")[0].strip()
        if not line:
            continue
        clean_lines.append(line)
        match_n = re.match(r"^(N\d+)\s+(.*)", line)
        if match_n:
            labeled_blocks[match_n.group(1)] = match_n.group(2)

    logs.append(f"[Compiler] Successfully parsed {len(clean_lines)} valid G-code statements.")

    i = 0
    while i < len(clean_lines):
        line = clean_lines[i]
        i += 1
        
        tokens = re.findall(r"([A-Z])([-+]?\d*\.?\d+)", line)
        cmd_dict = {k: float(v) for k, v in tokens}
        
        if "G71" in cmd_dict:
            if "U" in cmd_dict and "R" in cmd_dict and "P" not in cmd_dict:
                g71_u = cmd_dict.get("U", 2.0)
                g71_r = cmd_dict.get("R", 1.0)
                logs.append(f"[G71 Canned Cycle]: Roughing parameters set (Depth U={g71_u}, Retract R={g71_r}).")
                continue
            elif "P" in cmd_dict and "Q" in cmd_dict:
                g71_active = True
                g71_p = f"N{int(cmd_dict['P'])}"
                g71_q = f"N{int(cmd_dict['Q'])}"
                g71_stock_u = cmd_dict.get("U", 0.0)
                g71_stock_w = cmd_dict.get("W", 0.0)
                g71_feed = cmd_dict.get("F", 0.25)
                logs.append(f"[G71 Canned Cycle]: Expanding roughing passes between {g71_p} and {g71_q}...")
                
                contour_moves = []
                capturing = False
                for blk_id, blk_cmd in labeled_blocks.items():
                    if blk_id == g71_p:
                        capturing = True
                    if capturing:
                        contour_moves.append(blk_cmd)
                    if blk_id == g71_q:
                        break
                
                if contour_moves:
                    target_final_x = stock_radius
                    min_contour_z = -50.0
                    for cm in contour_moves:
                        toks = re.findall(r"([A-Z])([-+]?\d*\.?\d+)", cm)
                        d = {k: float(v) for k, v in toks}
                        if "X" in d:
                            target_final_x = min(target_final_x, d["X"] / 2.0)
                        if "Z" in d:
                            min_contour_z = min(min_contour_z, d["Z"])
                            
                    current_rough_x = stock_radius
                    while current_rough_x > target_final_x + g71_stock_u + 0.1:
                        current_rough_x = max(target_final_x + g71_stock_u, current_rough_x - g71_u)
                        try:
                            validate_lathe_boundaries(current_rough_x, min_contour_z, stock_radius=stock_radius, stock_len=stock_len)
                        except ValueError as e:
                            logs.append(f"[CRASH ALARM] {str(e)}")
                            return expanded_instructions, logs
                            
                        expanded_instructions.append(f"G00 X{current_rough_x * 2.0:.1f} Z2.0")
                        expanded_instructions.append(f"G01 X{current_rough_x * 2.0:.1f} Z{min_contour_z} F{g71_feed}")
                        expanded_instructions.append(f"G00 X{(current_rough_x + 1.0) * 2.0:.1f}")
                continue

        if "G" in cmd_dict:
            g_code = int(cmd_dict["G"])
            if g_code in [0, 1, 2, 3]:
                target_x = cmd_dict.get("X", curr_x * 2.0) / 2.0
                target_z = cmd_dict.get("Z", curr_z)
                
                try:
                    validate_lathe_boundaries(target_x, target_z, stock_radius=stock_radius, stock_len=stock_len)
                except ValueError as e:
                    logs.append(f"[CRASH ALARM] {str(e)}")
                    return expanded_instructions, logs
                
                # Handle Arc conversion if R is specified and I/K are missing
                if g_code in [2, 3] and "R" in cmd_dict and "I" not in cmd_dict and "K" not in cmd_dict:
                    r_val = cmd_dict["R"]
                    is_cw = (g_code == 2)
                    i_offset, k_offset = r_to_ij(curr_z, curr_x, target_z, target_x, r_val, is_cw)
                    line = f"G{g_code} X{target_x * 2.0:.3f} Z{target_z:.3f} I{i_offset:.3f} K{k_offset:.3f}"
                    if "F" in cmd_dict:
                        line += f" F{cmd_dict['F']}"

                curr_x, curr_z = target_x, target_z
                
        expanded_instructions.append(line)
        
    logs.append("Compiled successfully!")
    return expanded_instructions, logs