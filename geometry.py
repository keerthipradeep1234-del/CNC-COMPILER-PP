import matplotlib.patches as patches
import numpy as np

def validate_lathe_boundaries(target_x, target_z, stock_radius=30.0, stock_len=45.0, chuck_z_limit=-70.0, tool_holder_offset=12.0):
    """
    Validates whether the target tool position or its holder envelope 
    violates chuck body limits, centerline limits, or chuck jaw grip zones.
    """
    # 1. Absolute chuck face / back limit check
    effective_collision_z = target_z - tool_holder_offset
    if effective_collision_z < chuck_z_limit or target_z < chuck_z_limit:
        raise ValueError(
            f"CRASH ALERT: Tool position Z={target_z} (Effective Z={effective_collision_z:.1f}) violates chuck limit (Z={chuck_z_limit})."
        )
        
    # 2. Chuck Jaw Collision Check
    jaw_front_z = max(-70.0 + 25.0, -stock_len + 10.0) 
    jaw_outer_radius = 50.0
    
    if chuck_z_limit <= effective_collision_z <= jaw_front_z or chuck_z_limit <= target_z <= jaw_front_z:
        if stock_radius <= abs(target_x) <= jaw_outer_radius:
            raise ValueError(
                f"CHUCK JAW COLLISION ALERT: Tool at Z={target_z}, X={target_x} overlaps the chuck jaws zone!"
            )
        
    # 3. Centerline limit for lathe turning
    if target_x < -2.0:
        raise ValueError(
            f"AXIS LIMIT ERROR: X-axis radius {target_x} is past the centerline limit."
        )
        
    return True

def generate_arc_points(start_z, start_x, end_z, end_x, i_off, j_off, is_cw, num_points=30):
    """
    Generates smooth interpolated points along a circular arc (G02/G03) for simulation and plotting.
    """
    center_z = start_z + i_off  # I is Z-axis center offset
    center_x = start_x + j_off  # J or K is X-axis center offset
    radius = np.hypot(start_z - center_z, start_x - center_x)
    
    start_angle = np.arctan2(start_x - center_x, start_z - center_z)
    end_angle = np.arctan2(end_x - center_x, end_z - center_z)
    
    if is_cw:
        if end_angle >= start_angle:
            end_angle -= 2 * np.pi
    else:
        if end_angle <= start_angle:
            end_angle += 2 * np.pi
            
    angles = np.linspace(start_angle, end_angle, num_points)
    arc_z = center_z + radius * np.cos(angles)
    arc_x = center_x + radius * np.sin(angles)
    
    return arc_z.tolist(), arc_x.tolist()

def draw_rotating_chuck_and_jaws(ax, stock_len, stock_radius, rotation_angle=0.0, job_fixed=False):
    fixed_chuck_face_z = -70.0
    chuck_width = 25.0
    fixed_chuck_back_z = fixed_chuck_face_z - chuck_width
    fixed_body_radius = 90.0
    
    chuck_body = patches.Rectangle(
        (fixed_chuck_back_z, -fixed_body_radius), chuck_width, fixed_body_radius * 2,
        linewidth=1.2, edgecolor='#1e272c', facecolor='#485460', alpha=0.95, zorder=2
    )
    ax.add_patch(chuck_body)
    ax.plot([fixed_chuck_back_z, fixed_chuck_back_z], [-fixed_body_radius, fixed_body_radius], color='#1e272c', lw=2, zorder=3)
    
    for angle_offset in [0, np.pi/2, np.pi, 3*np.pi/2]:
        curr_ang = rotation_angle + angle_offset
        slot_x = fixed_body_radius * 0.7 * np.sin(curr_ang)
        ax.plot([fixed_chuck_face_z, fixed_chuck_face_z], [slot_x*0.8, slot_x], color='#1e272c', lw=3, zorder=3)
        
    clamp_depth = 10.0 if job_fixed else 0.0
    jaw_grip_end_z = -stock_len + clamp_depth
    jaw_z_back = fixed_chuck_face_z
    jaw_z_front = max(jaw_grip_end_z, fixed_chuck_face_z + 5.0) if job_fixed else fixed_chuck_face_z + 12.0
    
    top_jaw_contact_x = stock_radius if job_fixed else 20.0
    jaw_height = 20.0
    jaw_pulsate = 2.5 * np.sin(rotation_angle)
    
    top_jaw_pts = [
        [jaw_z_back, top_jaw_contact_x + jaw_height + jaw_pulsate],
        [jaw_z_front - 8, top_jaw_contact_x + jaw_height + jaw_pulsate],
        [jaw_z_front - 8, top_jaw_contact_x + jaw_height * 0.5 + jaw_pulsate * 0.5],
        [jaw_z_front, top_jaw_contact_x + jaw_height * 0.5 + jaw_pulsate * 0.5],
        [jaw_z_front, top_jaw_contact_x],
        [jaw_z_back, top_jaw_contact_x]
    ]
    ax.add_patch(patches.Polygon(top_jaw_pts, closed=True, edgecolor='black', facecolor='#808e9b', lw=1.2, zorder=4))
    
    bottom_jaw_pulsate = 2.5 * np.sin(rotation_angle + np.pi)
    bottom_jaw_pts = [
        [jaw_z_back, -(top_jaw_contact_x + jaw_height + bottom_jaw_pulsate)],
        [jaw_z_front - 8, -(top_jaw_contact_x + jaw_height + bottom_jaw_pulsate)],
        [jaw_z_front - 8, -(top_jaw_contact_x + jaw_height * 0.5 + bottom_jaw_pulsate * 0.5)],
        [jaw_z_front, -(top_jaw_contact_x + jaw_height * 0.5 + bottom_jaw_pulsate * 0.5)],
        [jaw_z_front, -top_jaw_contact_x],
        [jaw_z_back, -top_jaw_contact_x]
    ]
    ax.add_patch(patches.Polygon(bottom_jaw_pts, closed=True, edgecolor='black', facecolor='#808e9b', lw=1.2, zorder=4))

def draw_lathe_tool(ax, tip_z, tip_x, tool_type="CNMG (80° Roughing)", color="#f39c12"):
    shank_len = 14.0
    shank_width = 4.5
    
    if "DNMG" in tool_type:
        insert_pts = [[tip_z, tip_x], [tip_z + 7.0, tip_x + 3.5], [tip_z + 8.5, tip_x + 1.2], [tip_z + 3.0, tip_x]]
        shank_pts = [[tip_z + 7.0, tip_x + 3.5], [tip_z + 7.0 + shank_len, tip_x + 3.5], [tip_z + 7.0 + shank_len, tip_x + 3.5 + shank_width], [tip_z + 5.0, tip_x + 3.5 + shank_width]]
    elif "Grooving" in tool_type:
        blade_width = 2.0
        blade_depth = 6.0
        insert_pts = [[tip_z, tip_x], [tip_z + blade_width, tip_x], [tip_z + blade_width, tip_x + blade_depth], [tip_z, tip_x + blade_depth]]
        shank_pts = [[tip_z + blade_width, tip_x + blade_depth], [tip_z + blade_width + shank_len, tip_x + blade_depth], [tip_z + blade_width + shank_len, tip_x + blade_depth + shank_width], [tip_z + blade_width, tip_x + blade_depth + shank_width]]
    else:
        inset_length = 6.0
        half_width = 2.5
        insert_pts = [[tip_z, tip_x], [tip_z + inset_length * 0.6, tip_x + half_width], [tip_z + inset_length, tip_x + half_width * 0.4], [tip_z + inset_length * 0.4, tip_x]]
        shank_pts = [[tip_z + inset_length * 0.6, tip_x + half_width], [tip_z + inset_length * 0.6 + shank_len, tip_x + half_width], [tip_z + inset_length * 0.6 + shank_len, tip_x + half_width + shank_width], [tip_z + inset_length * 0.6 - 2, tip_x + half_width + shank_width]]
        
    tool_insert = patches.Polygon(insert_pts, closed=True, facecolor=color, edgecolor='black', lw=1, zorder=9)
    tool_holder = patches.Polygon(shank_pts, closed=True, facecolor='#2f3640', edgecolor='black', lw=1, zorder=8)
    
    return ax.add_patch(tool_insert), ax.add_patch(tool_holder)

def render_dynamic_workpiece(ax, stock_len, stock_radius, current_anim_idx, animated_segs):
    z_grid = np.linspace(-stock_len, 0.0, 500)
    ax.fill_between(z_grid, stock_radius, -stock_radius, color='#34495e', label="Raw Stock Cylinder", zorder=3)
    
    envelope_x = np.full_like(z_grid, stock_radius)
    if animated_segs and current_anim_idx > 0:
        for idx in range(min(current_anim_idx, len(animated_segs))):
            seg = animated_segs[idx]
            # Check segment format (supports standard tuples or dicts)
            if len(seg) >= 3:
                z_pts, x_pts, g = seg[0], seg[1], seg[2]
                i_off = seg[3] if len(seg) > 3 else 0.0
                j_off = seg[4] if len(seg) > 4 else 0.0
                
                if g == 1:
                    if len(z_pts) >= 2 and len(x_pts) >= 2:
                        z0, z1 = z_pts[0], z_pts[1]
                        x0, x1 = x_pts[0], x_pts[1]
                        z_min_seg, z_max_seg = min(z0, z1), max(z0, z1)
                        mask = (z_grid >= z_min_seg) & (z_grid <= z_max_seg)
                        if np.any(mask):
                            z_vals = z_grid[mask]
                            x_vals = x0 + (x1 - x0) * (z_vals - z0) / (z1 - z0) if abs(z1 - z0) > 1e-6 else np.full_like(z_vals, min(x0, x1))
                            envelope_x[mask] = np.minimum(envelope_x[mask], np.abs(x_vals))
                            
                elif g in [2, 3]:
                    if len(z_pts) >= 2 and len(x_pts) >= 2:
                        is_cw = (g == 2)
                        arc_z, arc_x = generate_arc_points(z_pts[0], x_pts[0], z_pts[1], x_pts[1], i_off, j_off, is_cw)
                        for az, ax_val in zip(arc_z, arc_x):
                            # Find closest point on z_grid
                            idx_z = np.argmin(np.abs(z_grid - az))
                            envelope_x[idx_z] = min(envelope_x[idx_z], abs(ax_val))
                            
    ax.fill_between(z_grid, stock_radius, envelope_x, color='white', zorder=4)
    ax.fill_between(z_grid, -envelope_x, -stock_radius, color='white', zorder=4)