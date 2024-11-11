import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.offsetbox as offsetbox
import os

path = 'csv/test.csv'
geometry = pd.read_csv(path, sep=',', index_col=False)

region_names = ['RE-3', 'RE-4', 'RE+3', 'RE+4']
size = 1.6

for region_name in region_names:
    region_geometry = geometry[geometry['roll_name'].str.startswith(region_name)]
    fig, ax = plt.subplots(figsize=(size*20, size*20))

    for i in range(0, region_geometry.shape[0]):
        chamber = region_geometry.iloc[i]

        center_x = (chamber.x1 + chamber.x2 + chamber.x3 + chamber.x4) / 4
        center_y = (chamber.y1 + chamber.y2 + chamber.y3 + chamber.y4) / 4

        p1_p2_x = np.linspace((chamber.x1*9 + center_x)/10, (chamber.x2*9 + center_x)/10, 10)
        p1_p2_y = np.linspace((chamber.y1*9 + center_y)/10, (chamber.y2*9 + center_y)/10, 10)

        p2_p3_x = np.linspace((chamber.x2*9 + center_x)/10, (chamber.x3*9 + center_x)/10, 10)
        p2_p3_y = np.linspace((chamber.y2*9 + center_y)/10, (chamber.y3*9 + center_y)/10, 10)

        p3_p4_x = np.linspace((chamber.x3*9 + center_x)/10, (chamber.x4*9 + center_x)/10, 10)
        p3_p4_y = np.linspace((chamber.y3*9 + center_y)/10, (chamber.y4*9 + center_y)/10, 10)

        p4_p1_x = np.linspace((chamber.x4*9 + center_x)/10, (chamber.x1*9 + center_x)/10, 10)
        p4_p1_y = np.linspace((chamber.y4*9 + center_y)/10, (chamber.y1*9 + center_y)/10, 10)

        if region_name.startswith('RE'):
            # RE+3_R3_CH29_A
            endcap_chamber_name = chamber.roll_name.split('_') # [RE+3, R3, CH29, A]
            if endcap_chamber_name[1][1] == "1":
                ax.text(center_x, center_y,
                        f'{endcap_chamber_name[1][-1]}/{endcap_chamber_name[2][2:]}/{endcap_chamber_name[3]}', # 3/29
                        fontsize=size*8,
                        va='center', ha='center')
            else:        
                ax.text(center_x, center_y,
                        f'{endcap_chamber_name[1][-1]}/{endcap_chamber_name[2][2:]}/{endcap_chamber_name[3]}', # 3/29
                        fontsize=size*10,
                        va='center', ha='center')

        p_x = np.concatenate((p1_p2_x, p2_p3_x, p3_p4_x, p4_p1_x))
        p_y = np.concatenate((p1_p2_y, p2_p3_y, p3_p4_y, p4_p1_y))

        if chamber.is_front == True:
            ax.plot(p_x, p_y, c="red")
        if chamber.is_front == False:
            ax.plot(p_x, p_y, c="blue")

    ax.set_xlabel('axis-X', fontsize=size*20)
    ax.set_ylabel('axis-Y', fontsize=size*20)

    plt.plot([], [], c='red', label='front chamber')
    plt.plot([], [], c='blue', label='back chamber')
    ax.legend(fontsize=size*20)

    ax.set_title(f'{region_name} RPC Geometry(from CMSSW)', fontsize=size*30)


    global_tag = '140X_mcRun4_realistic_v3'

    tags = offsetbox.AnchoredText(
        f'Global Tag: {global_tag}',
        loc='upper left',
        prop=dict(size=size*20)
    )
    ax.add_artist(tags)

    plt.savefig(f'png/{global_tag}-{region_name}-XY-FB.png')
