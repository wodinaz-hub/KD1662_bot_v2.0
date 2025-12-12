import matplotlib.pyplot as plt
import io
from PIL import Image
import numpy as np
import logging

logger = logging.getLogger('core.graphics')

def create_progress_gif(current, total, filename="progress.gif", title="Progress", color="#00ff00"):
    """
    Generates an animated gauge chart GIF.
    current: Current value (e.g., Kills)
    total: Target value (e.g., Required Kills)
    filename: Output filename (not used if returning bytes, but good for debug)
    """
    try:
        frames = []
        
        # Calculate percentage
        if total <= 0:
            pct = 100 if current > 0 else 0
        else:
            pct = min(100, (current / total) * 100)
            
        # Number of frames for animation
        n_frames = 15
        
        # Setup figure size
        fig_size = (6, 4)
        
        for i in range(n_frames + 1):
            # Current progress for this frame
            frame_pct = (pct * i) / n_frames
            
            # Create figure
            fig, ax = plt.subplots(figsize=fig_size, subplot_kw={'projection': 'polar'})
            
            # Background track (0 to 100%)
            # Polar coordinates: theta (angle), r (radius)
            # We want a semi-circle gauge from -90 deg to +90 deg? Or 0 to 180?
            # Let's do a standard gauge: start at 180 (left), end at 0 (right).
            # Matplotlib polar: 0 is East, 90 is North, 180 is West.
            # We want 180 -> 0 (Clockwise? No, counter-clockwise is standard in math, but we want visual clockwise fill)
            # Let's try: Start at Pi (180), go to 0.
            
            # Background arc (gray)
            # bar(x, height, width, bottom, ...)
            # x = angle center, height = radius length, width = angle width
            
            # We use a thick line for the arc
            # Draw full semi-circle background
            ax.barh(1, np.pi, left=np.pi, height=0.5, color='#333333', edgecolor='none') # Background
            
            # Draw progress arc
            # Angle width corresponds to percentage
            # 100% = Pi radians
            progress_radians = (frame_pct / 100.0) * np.pi
            
            # We want to start from Pi (left) and move towards 0 (right)
            # So the bar should be centered correctly or we use `left` parameter.
            # If we start at Pi, and width is progress_radians (negative? or positive?)
            # In polar, positive is counter-clockwise.
            # So Pi -> 2Pi is bottom half. Pi -> 0 is top half (clockwise).
            # Let's use negative width to go clockwise from Pi?
            
            ax.barh(1, progress_radians, left=np.pi, height=0.5, color=color, edgecolor='none', align='edge')
            
            # Center text
            ax.text(0, 0, f"{int(frame_pct)}%", ha='center', va='center', fontsize=24, color='white', fontweight='bold')
            ax.text(0, -0.4, title, ha='center', va='center', fontsize=14, color='white')

            # Styling
            ax.set_axis_off()
            ax.set_ylim(0, 1.5) # Control thickness/hole size
            
            # Save frame to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', dpi=100)
            buf.seek(0)
            frames.append(Image.open(buf))
            
            plt.close(fig)

        # Save frames as GIF to a bytes buffer
        output_buffer = io.BytesIO()
        frames[0].save(
            output_buffer,
            format='GIF',
            save_all=True,
            append_images=frames[1:],
            duration=50, # ms per frame
            loop=0,
            transparency=0,
            disposal=2
        )
        output_buffer.seek(0)
        return output_buffer

    except Exception as e:
        logger.error(f"Error generating GIF: {e}")
        return None


def create_player_stats_card(current_kills, req_kills, current_deaths, req_deaths, player_name):
    """
    Generates a static image with two concentric gauge charts: Kills (Outer) and Deaths (Inner).
    Matches the design: Semi-circle, dark theme (transparent bg), specific colors.
    """
    try:
        # Setup figure
        # Increase figure size for better quality text
        fig, ax = plt.subplots(figsize=(8, 6), subplot_kw={'projection': 'polar'})
        
        # Colors
        color_kills = "#cfa035" # Gold/Yellowish
        color_deaths = "#d462d1" # Purple/Pink
        color_bg_track = "#404040" # Dark Gray for empty track
        
        # Data prep
        # Kills
        if req_kills <= 0:
            pct_kills = 100 if current_kills > 0 else 0
        else:
            pct_kills = (current_kills / req_kills) * 100
        
        # Deaths
        if req_deaths <= 0:
            pct_deaths = 100 if current_deaths > 0 else 0
        else:
            pct_deaths = (current_deaths / req_deaths) * 100
            
        # Cap visual bars at 100% (or slightly more? Design shows 103% filling more?)
        # Let's cap the BAR at 100% (Pi radians) so it doesn't loop around weirdly, 
        # but the text will show true percentage.
        # Actually, if it's > 100%, it should probably fill the whole bar.
        bar_pct_kills = min(100, pct_kills)
        bar_pct_deaths = min(100, pct_deaths)

        # --- Drawing ---
        
        # We want a semi-circle from Pi (left) to 0 (right)
        # Matplotlib polar: 0 is East, 90 is North, 180 is West.
        # We draw counter-clockwise by default.
        # To draw "clockwise" from left to right, we can start at Pi and use negative width?
        # Or start at Pi and go to 0?
        # Let's stick to: Start at Pi (180 deg), width is negative to go clockwise?
        # Wait, standard polar is CCW.
        # 180 -> 0 is CW.
        # Let's try using `left=np.pi` and negative width.
        
        # Radii for concentric bars
        # Outer bar (Kills): Radius 2.0 to 2.5
        # Inner bar (Deaths): Radius 1.4 to 1.9
        # Gap: 0.1
        
        # Outer Track (Background)
        ax.barh(2.25, -np.pi, left=np.pi, height=0.5, color=color_bg_track, edgecolor='none', alpha=0.5)
        
        # Inner Track (Background)
        ax.barh(1.65, -np.pi, left=np.pi, height=0.5, color=color_bg_track, edgecolor='none', alpha=0.5)
        
        # Outer Bar (Kills)
        # Width in radians = (pct / 100) * Pi
        width_kills = (bar_pct_kills / 100.0) * np.pi
        ax.barh(2.25, -width_kills, left=np.pi, height=0.5, color=color_kills, edgecolor='none', alpha=0.9)
        
        # Inner Bar (Deaths)
        width_deaths = (bar_pct_deaths / 100.0) * np.pi
        ax.barh(1.65, -width_deaths, left=np.pi, height=0.5, color=color_deaths, edgecolor='none', alpha=0.9)
        
        # --- Text ---
        
        # Center Name
        # In polar, (0, 0) is the center.
        ax.text(0, 0, player_name, ha='center', va='bottom', fontsize=22, color='#cccccc', fontweight='bold')
        ax.text(0, 0, "Progress", ha='center', va='top', fontsize=18, color='#888888')
        
        # Stats Text below the arc
        # We can place text using polar coordinates or relative figure coords.
        # Let's use polar coords but with radius < 0? Or just different angles?
        # Actually, for the text below "Kills" and "Deaths" on left/right sides:
        # Left side (Kills info): Angle ~ 180+20 deg? Or just below the left end.
        # Right side (Deaths info): Angle ~ 360-20 deg?
        
        # Let's try to position them nicely.
        # Kills (Left side) - Gold color
        # Angle: 5*Pi/4 (225 deg) is bottom left quadrant.
        # Radius: 2.5
        
        # We can also use ax.text with transform=ax.transAxes for easier positioning relative to the box.
        # But let's try to stick to the plot area.
        
        # Kills Text Group (Left)
        # Position: x=-0.5, y=-0.5 roughly in cartesian?
        # Let's use text at specific angles/radii.
        
        # Kills Label
        ax.text(5*np.pi/4 - 0.2, 2.5, "Kills:", ha='center', va='center', fontsize=16, color=color_kills)
        ax.text(5*np.pi/4 - 0.2, 3.2, f"Cur: {current_kills:,.0f}\nReq: {req_kills:,.0f}\n({int(pct_kills)}%)", 
                ha='center', va='top', fontsize=14, color=color_kills)

        # Deaths Label (Right)
        # Angle: 7*Pi/4 (315 deg) is bottom right quadrant.
        ax.text(7*np.pi/4 + 0.2, 2.5, "Deaths:", ha='center', va='center', fontsize=16, color=color_deaths)
        ax.text(7*np.pi/4 + 0.2, 3.2, f"Cur: {current_deaths:,.0f}\nReq: {req_deaths:,.0f}\n({int(pct_deaths)}%)", 
                ha='center', va='top', fontsize=14, color=color_deaths)

        # Styling
        ax.set_axis_off()
        ax.set_ylim(0, 3.5) # Adjust to fit text
        
        # Limit the view to the upper half + some bottom for text
        # Polar plots are circles. We can't easily crop to a semi-circle in the plot logic itself without masking.
        # But since we put text at the bottom, we want the full circle area but only draw on top half?
        # No, we drew on top half (Pi to 0).
        # Text is at bottom.
        # So we need the full circle area.
        
        # Save to buffer
        buf = io.BytesIO()
        # Transparent background
        plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', dpi=100)
        buf.seek(0)
        plt.close(fig)
        return buf

    except Exception as e:
        logger.error(f"Error generating stats card: {e}")
        return None
