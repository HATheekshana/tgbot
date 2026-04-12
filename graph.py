import matplotlib.pyplot as plt
import numpy as np
import io
import json
from PIL import Image

ELEMENT_COLORS = {
    "Pyro": "#FF9999",
    "Electro": "#E0B0FF",
    "Hydro": "#80C0FF",
    "Dendro": "#A5C531",
    "Anemo": "#72E2C2",
    "Geo": "#FFE070",
    "Cryo": "#A0E9FF",
    "Physical": "#FFFFFF"
}

# Load targets once
with open("targets.json", "r", encoding="utf-8") as f:
    TARGETS = json.load(f)

# Exact labels from your reference, matching the angles (clockwise from 12 o'clock)
LABELS = ['HP', 'ATK', 'DEF', 'EM', 'Crit DMG', 'Crit Rate', 'ER', 'Elem DMG']

def generate_full_radar_chart(values, color="#bb86fc", element="Physical"):
    num_vars = len(LABELS)
    angles = np.linspace(np.pi/2, np.pi/2 - 2*np.pi, num_vars, endpoint=False).tolist()
    
    # 1. Close the loop
    MAX_LIMIT = 1.3   # 100% max
    clamped_values = [min(v, MAX_LIMIT) for v in values]
    plot_values = clamped_values + [clamped_values[0]]
    plot_angles = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    
    # Tighten margins to allow the graph to expand
    plt.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.95)
    
    ax.set_facecolor('none')
    fig.patch.set_alpha(0.0)
    
    # 2. THE SCALE: Setting ylim to 1.25 makes the 1.0 (Target) 
    # the second line from the outside.
    ax.set_ylim(0, MAX_LIMIT) 
    
    ax.spines['polar'].set_color('white')
    ax.spines['polar'].set_alpha(0.3)
    ax.spines['polar'].set_linewidth(2.0)
    
    # 3. THE GRID: explicitly draw rings up to the target
    ax.set_yticks(np.arange(0.2, MAX_LIMIT + 0.1, 0.2))
    ax.set_yticklabels([]) 
    ax.grid(True, color='white', alpha=0.2, linestyle='-')

    # Draw the data
    ax.plot(plot_angles, plot_values, color=color, linewidth=6.0, solid_capstyle='round')
    ax.fill(plot_angles, plot_values, color=color, alpha=0.45)

    display_labels = [l if l != 'Elem DMG' else f"{element} DMG" for l in LABELS]
    
    for angle, label in zip(angles, display_labels):
        ha = 'center'
        # Dynamic alignment based on angle
        if 0.1 < angle < 3.0: ha = 'left' 
        elif 3.2 < angle < 6.0: ha = 'right'
        
        # 4. LABEL POSITION: Set to 1.35 or 1.4 to be outside the whole graph
        # Since ylim is 1.25, anything > 1.25 is outside the web.
        ax.text(angle, 1.38, label, size=22, color='white', 
                weight='bold', ha=ha, va='center', alpha=1)

    ax.set_xticklabels([])

    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=300)
    plt.close(fig)
    buf.seek(0)
    
    return Image.open(buf).convert("RGBA")

def get_complete_radar_module(char_stats, char_id, final_size=(450, 450)):
    """
    Looks up targets from targets.json and calls the dynamic chart generator.
    """
    cid_str = str(char_id)
    if cid_str not in TARGETS:
        # Falls back to no-data image logic if character missing from DB
        return None

    targets = TARGETS[cid_str]
    
    # Automatic dynamic settings based on element
    element = char_stats.get("element", "Physical") 
    char_color = ELEMENT_COLORS.get(element, "#FFFFFF")

    # Map the relative values against your manual targets database
    
    values_list = [
        char_stats.get('hp', 0) / targets['hp'],
        char_stats.get('atk', 0) / targets['atk'],
        char_stats.get('def', 0) / targets['def'],
        char_stats.get('em', 0) / targets['em'],
        char_stats.get('cd', 0) / targets['cd'],
        char_stats.get('cr', 0) / targets['cr'],
        char_stats.get('er', 0) / targets['er'],
        char_stats.get('elem_bonus', 0) / targets.get('dmg_val', 46.6),
    ]

    # Generate the complete image (Web + Data + Text) in one step
    radar_img = generate_full_radar_chart(values_list, char_color, element)
    
    # Scale to fit your card layout
    return radar_img.resize(final_size, Image.Resampling.LANCZOS)