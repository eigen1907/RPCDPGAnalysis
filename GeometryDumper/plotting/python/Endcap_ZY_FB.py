import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.offsetbox as offsetbox
import os

path = 'csv/140X_mcRun3_2024_design_v6.csv'
geometry = pd.read_csv(path, sep=',', index_col=False)

region_names = ['RE-3', 'RE-4', 'RE+3', 'RE+4']
size = 1.6

for region_name in region_names:
    fig, ax = plt.subplots(figsize=(size*6, size*6))
    region_geometry = geometry[geometry['roll_name'].str.startswith(region_name)]
    region_mean_z = region_geometry.mean(numeric_only=True).z1


    for i in range(0, region_geometry.shape[0]):
        chamber = region_geometry.iloc[i]

        center_z = (chamber.z1 + chamber.z2 + chamber.z3 + chamber.z4) / 4
        center_y = (chamber.y1 + chamber.y2 + chamber.y3 + chamber.y4) / 4

        p1_p2_z = np.linspace((chamber.z1*9 + center_z)/10, (chamber.z2*9 + center_z)/10, 10)
        p1_p2_y = np.linspace((chamber.y1*9 + center_y)/10, (chamber.y2*9 + center_y)/10, 10)

        p2_p3_z = np.linspace((chamber.z2*9 + center_z)/10, (chamber.z3*9 + center_z)/10, 10)
        p2_p3_y = np.linspace((chamber.y2*9 + center_y)/10, (chamber.y3*9 + center_y)/10, 10)

        p3_p4_z = np.linspace((chamber.z3*9 + center_z)/10, (chamber.z4*9 + center_z)/10, 10)
        p3_p4_y = np.linspace((chamber.y3*9 + center_y)/10, (chamber.y4*9 + center_y)/10, 10)

        p4_p1_z = np.linspace((chamber.z4*9 + center_z)/10, (chamber.z1*9 + center_z)/10, 10)
        p4_p1_y = np.linspace((chamber.y4*9 + center_y)/10, (chamber.y1*9 + center_y)/10, 10)

        p_z = np.concatenate((p1_p2_z, p2_p3_z, p3_p4_z, p4_p1_z))
        p_y = np.concatenate((p1_p2_y, p2_p3_y, p3_p4_y, p4_p1_y))

        if chamber.is_front == True:
            ax.plot(p_z, p_y, c="red", linewidth=size*2)
        if chamber.is_front == False:
            ax.plot(p_z, p_y, c="blue", linewidth=size*2)

    ax.set_xlim(region_mean_z-30, region_mean_z+30)

    ax.set_xlabel('axis-Z', fontsize=size*10)
    ax.set_ylabel('axis-Y', fontsize=size*10)

    plt.plot([], [], c='red', label='front chamber')
    plt.plot([], [], c='blue', label='back chamber')
    ax.legend(fontsize=size*10, loc='upper right')

    ax.set_title(f'{region_name} RPC Geometry(from CMSSW)', fontsize=size*16)

    global_tag = '140X_mcRun3_2024_design_v6'

    tags = offsetbox.AnchoredText(
        f'Global Tag: {global_tag}',
        loc='upper left',
        prop=dict(size=size*8)
    )
    ax.add_artist(tags)

    plt.savefig(f'png/{global_tag}-{region_name}-ZY-FB.png')