#!/usr/bin/env python3
"""
XRD, VSM, and SEM Plotting Module
- XRD: 2θ vs Intensity plot
- VSM: Hysteresis loop
- SEM: Display image
"""

import matplotlib.pyplot as plt
import numpy as np
import customtkinter as ctk
import subprocess
import sys
import os
from pathlib import Path
from PIL import Image
from functools import partial
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg   
from stage_two.parsers.parse_xrd_v2 import parse_xy_file, find_peaks
from stage_two.parsers.parse_vsm_v2 import parse_vsm_file

def plot_xrd(file_path, figure=None, master=None):
    """Plot XRD data with peaks marked.

    If master is provided (a tkinter frame), embeds the canvas directly
    into it and adds a launch button for xrd_analyzer_standalone.py --
    same pattern as plot_sem(). Returns early from the app's viewer
    flow when master is used.
    """
    data = parse_xy_file(file_path)
    if data is None:
        return None, "Failed to parse file"

    two_theta = data['two_theta']
    intensity = data['intensity']
    peaks = find_peaks(two_theta, intensity)

    if figure is not None:
        plt.close(figure)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(two_theta, intensity, 'b-', linewidth=0.8, label='XRD pattern')
    ax.set_xlabel('2θ (degrees)')
    ax.set_ylabel('Intensity (counts)')
    ax.set_title(f'XRD Pattern: {Path(file_path).name}')
    ax.legend()
    ax.grid(True, alpha=0.3)

    info = (f"Peaks: {len(peaks)}\nMax: {data['max_intensity']:.0f}\n"
            f"Range: {data['start']:.1f}° - {data['end']:.1f}°")
    ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    plt.tight_layout()

    if master is not None:
        # The app already clears viewer_plot_frame children before calling
        # this function (lines 490-494 in alloy_desktop_v2.py) -- do NOT
        # destroy children here, or viewer_plot_label gets destroyed and
        # subsequent "file not found" error paths break.
        container = ctk.CTkFrame(master)
        container.pack(fill="both", expand=True)

        button_frame = ctk.CTkFrame(container, fg_color="blue", height=60)
        button_frame.pack(side="top", pady=5, fill="x", padx=10)
        button_frame.pack_propagate(False)

        xrd_analyzer_path = os.path.join(os.path.dirname(__file__), 'xrd_analyzer_standalone.py')
        if os.path.exists(xrd_analyzer_path):
            def launch_xrd_analyzer():
                subprocess.Popen([sys.executable, xrd_analyzer_path, file_path])

            ctk.CTkButton(
                button_frame,
                text="📐 Analyze XRD",
                command=launch_xrd_analyzer,
                fg_color="green",
                text_color="white",
                font=ctk.CTkFont(size=14, weight="bold"),
                width=200, height=35,
            ).grid(row=0, column=0, padx=10, pady=10)
            ctk.CTkLabel(
                button_frame, text="(opens in new window)",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=1, padx=5, pady=10)
        else:
            ctk.CTkLabel(
                button_frame, text="xrd_analyzer_standalone.py not found",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=0, padx=10, pady=10)

        canvas = FigureCanvasTkAgg(fig, master=container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        return fig, None

    return fig, None


def plot_vsm(file_path, figure=None, master=None):
    """Plot VSM hysteresis loop with proper Hc and Mr markers.

    If master is provided (a tkinter frame), embeds the canvas directly
    into it and adds a launch button for vsm_mh_analyzer_standalone.py
    -- same pattern as plot_sem(). Returns early from the app's viewer
    flow when master is used.
    """
    result = parse_vsm_file(file_path)
    if 'error' in result:
        return None, result['error']

    fields = np.array(result['fields'])
    moments = np.array(result['moments'])

    if figure is not None:
        plt.close(figure)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(fields, moments, 'b-', linewidth=1.2, label='Hysteresis loop')

    hc = result.get('hc')
    mr = result.get('mr')
    ms = result.get('ms')

    x_min, x_max = np.min(fields), np.max(fields)
    y_min, y_max = np.min(moments), np.max(moments)
    x_pad = (x_max - x_min) * 0.05
    y_pad = (y_max - y_min) * 0.05
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)

    ax.set_xlabel('Field (Oe)')
    ax.set_ylabel('Moment (emu)')
    ax.set_title(f'VSM Hysteresis Loop: {Path(file_path).name}')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color='black', linewidth=0.5, alpha=0.3)
    ax.axvline(0, color='black', linewidth=0.5, alpha=0.3)

    info = f"Ms: {ms:.4f} emu\nMr: {mr:.4f} emu\nHc: {hc:.1f} Oe"
    if result.get('mass'):
        info += f"\nMass: {result['mass']*1000:.1f} mg"
    if result.get('ms_per_g'):
        info += f"\nMs/g: {result['ms_per_g']:.2f} emu/g"
    ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    plt.tight_layout()

    if master is not None:
        # Same reasoning as plot_xrd -- app already cleared the frame.
        container = ctk.CTkFrame(master)
        container.pack(fill="both", expand=True)

        button_frame = ctk.CTkFrame(container, fg_color="blue", height=60)
        button_frame.pack(side="top", pady=5, fill="x", padx=10)
        button_frame.pack_propagate(False)

        vsm_analyzer_path = os.path.join(os.path.dirname(__file__), 'vsm_mh_analyzer_standalone.py')
        if os.path.exists(vsm_analyzer_path):
            def launch_vsm_analyzer():
                subprocess.Popen([sys.executable, vsm_analyzer_path, file_path])

            ctk.CTkButton(
                button_frame,
                text="📊 Analyze VSM",
                command=launch_vsm_analyzer,
                fg_color="green",
                text_color="white",
                font=ctk.CTkFont(size=14, weight="bold"),
                width=200, height=35,
            ).grid(row=0, column=0, padx=10, pady=10)
            ctk.CTkLabel(
                button_frame, text="(opens in new window)",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=1, padx=5, pady=10)
        else:
            ctk.CTkLabel(
                button_frame, text="vsm_mh_analyzer_standalone.py not found",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=0, padx=10, pady=10)

        canvas = FigureCanvasTkAgg(fig, master=container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        return fig, None

    return fig, None

def plot_sem(file_path, figure=None, master=None):
    import os
    from PIL import Image
    import matplotlib.pyplot as plt
    
    print(f"DEBUG: plot_sem called with master={master}")
    
    # ===== CLOSE ALL OLD FIGURES =====
    plt.close('all')
    print(f"🔍 DEBUG: Closed all old figures")
    
    try:
        import customtkinter as ctk
        import subprocess
        import sys
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        
        print(f"🔍 DEBUG: About to open image: {file_path}")
        img = Image.open(file_path)
        print(f"🔍 DEBUG: Image opened successfully! Size: {img.size}")
        
        # Create the figure
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Display the image
        ax.imshow(img, cmap='gray')
        ax.axis('off')
        ax.set_title(f'SEM Image: {Path(file_path).name}')
        
        # Add metadata
        from stage_two.parsers.parse_sem_v2 import parse_sem_file
        metadata = parse_sem_file(file_path)
        if metadata and not metadata.get('error'):
            info = []
            if metadata.get('magnification'):
                info.append(f"Mag: {metadata['magnification']}")
            if metadata.get('eht_kv'):
                info.append(f"EHT: {metadata['eht_kv']}")
            if metadata.get('working_distance_mm'):
                info.append(f"WD: {metadata['working_distance_mm']}")
            if metadata.get('pixel_size_nm'):
                info.append(f"Pixel: {metadata['pixel_size_nm']}")
            if info:
                ax.text(0.02, 0.98, '\n'.join(info), transform=ax.transAxes, fontsize=9,
                        verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        
        # ===== EMBED THE FIGURE IN THE TKINTER FRAME =====
        if master is not None:
            print(f"🔍 DEBUG: Cleared master frame")

            # Create a container frame
            container = ctk.CTkFrame(master)
            container.pack(fill="both", expand=True)
            
            # ===== CREATE BUTTON AT THE TOP =====
            button_frame = ctk.CTkFrame(container, fg_color="blue", height=60)
            button_frame.pack(side="top", pady=5, fill="x", padx=10)
            button_frame.pack_propagate(False)
            print(f"🔍 DEBUG: Button frame created at TOP")
            
            # ✅ NEW — points to current phase fraction standalone tool
            sem_analyzer_path = os.path.join(
                os.path.dirname(__file__), 
                'sem_phase_fraction_standalone.py'
            )

            if os.path.exists(sem_analyzer_path):
                def launch_analyzer():
                    subprocess.Popen([sys.executable, sem_analyzer_path, file_path])
                
                analyze_btn = ctk.CTkButton(
                    button_frame,
                    text="📊 Phase Fraction",
                    command=launch_analyzer,
                    fg_color="green",
                    text_color="white",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    width=200,
                    height=35
                )
                analyze_btn.grid(row=0, column=0, padx=10, pady=10)
                
                note = ctk.CTkLabel(
                    button_frame,
                    text="(opens in new window)",
                    font=ctk.CTkFont(size=11)
                )
                note.grid(row=0, column=1, padx=5, pady=10)
            else:
                note = ctk.CTkLabel(
                    button_frame,
                    text="sem_phase_fraction_standalone.py not found",
                    font=ctk.CTkFont(size=11)
                )
                note.grid(row=0, column=0, padx=10, pady=10)
            
            # ===== CREATE CANVAS BELOW THE BUTTON =====
            canvas = FigureCanvasTkAgg(fig, master=container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            print(f"🔍 DEBUG: Canvas created below button")
            
            return fig, None
        else:
            # Fallback: show in separate window
            plt.show()
            return fig, None
        
    except Exception as e:
        print(f"🔍 DEBUG: EXCEPTION CAUGHT: {e}")
        import traceback
        traceback.print_exc()
        return None, f"Error displaying SEM image: {str(e)}"
    
    
def close_figures():
    """Close all matplotlib figures to free memory"""
    plt.close('all')


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python plot_v2.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not Path(file_path).exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    if file_path.lower().endswith('.xy'):
        fig, error = plot_xrd(file_path)
    elif file_path.lower().endswith('.dat'):
        fig, error = plot_vsm(file_path)
    elif file_path.lower().endswith(('.tif', '.tiff')):
        fig, error = plot_sem(file_path)
    else:
        print("Unsupported file type")
        sys.exit(1)
    
    if error:
        print(f"Error: {error}")
    else:
        plt.show()
