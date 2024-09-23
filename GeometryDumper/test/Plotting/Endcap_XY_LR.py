import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.offsetbox as offsetbox
import os

path = 'csv/auto_phase2_realistic_T33.csv'
geometry = pd.read_csv(path, sep=',', index_col=False)

region_name = 'RE+4'
region_geometry = geometry[geometry['roll_name'].str.startswith(region_name)]

fig, ax = plt.subplots(figsize=(40, 32))

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

    if region_name.startswith('W'):
        # W-2_RB3+_S05_Forward
        barrel_chamber_name = chamber.roll_name.split('_') # [W-2, RB3+, S05, Forward]
        ax.text(
            center_x, center_y,
            f'{barrel_chamber_name[0]}/{barrel_chamber_name[2][2]}/{barrel_chamber_name[2][1:]}', # W-2/3/05
            fontsize=16,
            va='center', ha='center'
        )

    elif region_name.startswith('RE'):
        # RE+3_R3_CH29_A
        endcap_chamber_name = chamber.roll_name.split('_') # [RE+3, R3, CH29, A]
        ax.text(
            center_x, center_y,
            f'{endcap_chamber_name[0]}/{endcap_chamber_name[1][-1]}/{endcap_chamber_name[2][2:]}', # RE+3/3/29
            fontsize=16,
            va='center', ha='center'
        )

    ax.plot(p1_p2_x, p1_p2_y, c='black')
    ax.plot(p2_p3_x, p2_p3_y, c='red')
    ax.plot(p3_p4_x, p3_p4_y, c='black')
    ax.plot(p4_p1_x, p4_p1_y, c='blue')


ax.set_title(f'RPC {region_name} Geometry', fontsize=60)
ax.set_xlabel('axis-X', fontsize=50)
ax.set_ylabel('axis-Y', fontsize=50)

global_tag = 'auto_phase2_realistic_T33'
#geometry_tag = 'RPCRECO_Geometry_141DD4hepV2'
#payload = '6fc19c3ffed82f7dfd0a5c51d6cee5f1245862f6'
#
#offsetbox = offsetbox.AnchoredText(
#    f' GT: {global_tag}\n Tag: {geometry_tag}\n payload: {payload} ',
#    loc='upper right',
#    prop=dict(size=30)
#)
#ax.add_artist(offsetbox)

plt.savefig(f'plot_XY_{global_tag}-{region_name}.png')
