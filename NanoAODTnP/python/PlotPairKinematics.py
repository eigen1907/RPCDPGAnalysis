from pathlib import Path
from typing import Optional, Union

import numpy as np
import uproot
import matplotlib.pyplot as plt
import matplotlib as mpl
import mplhep as mh

mpl.use('agg')
mh.style.use(mh.styles.CMS)

def plot_pair_distribution(values: np.ndarray,
                           xlabel: str,
                           output_path: Path,
                           bins: Union[int, np.ndarray],
                           label: str,
                           year: Union[int, str],
                           com: float,
                           ylabel: str = 'Counts',
                           close: bool = True,
):
    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]

    fig, ax = plt.subplots(figsize=(12, 9))

    ax.hist(values, bins=bins, histtype='step', linewidth=2)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    mh.cms.label(ax=ax, llabel=label, com=com, year=year)

    if output_path is not None:
        fig.savefig(output_path.with_suffix('.png'))

    if close:
        plt.close(fig)

    return fig


def plot_pair_kinematics(input_path: Path,
                         output_dir: Path,
                         com: float,
                         year: Union[int, str],
                         label: str,
):
    input_file = uproot.open(input_path)

    branch_names = [
        'dimuon_mass',
        'tag_pt', 'tag_eta', 'tag_phi',
        'probe_pt', 'probe_eta', 'probe_phi',
    ]

    pair_tree = input_file['pair_tree'].arrays(branch_names, library='np')

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    plot_pair_distribution(
        values=pair_tree['dimuon_mass'],
        xlabel=r'$m_{\mu\mu}$ [GeV]',
        output_path=output_dir / 'dimuon_mass',
        bins=np.linspace(70, 110, 41),
        label=label,
        year=year,
        com=com,
    )

    plot_pair_distribution(
        values=pair_tree['tag_pt'],
        xlabel=r'Tag muon $p_{T}$ [GeV]',
        output_path=output_dir / 'tag_pt',
        bins=np.linspace(0, 200, 41),
        label=label,
        year=year,
        com=com,
    )

    plot_pair_distribution(
        values=pair_tree['tag_eta'],
        xlabel=r'Tag muon $\eta$',
        output_path=output_dir / 'tag_eta',
        bins=np.linspace(-2.5, 2.5, 51),
        label=label,
        year=year,
        com=com,
    )

    plot_pair_distribution(
        values=pair_tree['tag_phi'],
        xlabel=r'Tag muon $\phi$ [rad]',
        output_path=output_dir / 'tag_phi',
        bins=np.linspace(-3.2, 3.2, 65),
        label=label,
        year=year,
        com=com,
    )

    plot_pair_distribution(
        values=pair_tree['probe_pt'],
        xlabel=r'Probe muon $p_{T}$ [GeV]',
        output_path=output_dir / 'probe_pt',
        bins=np.linspace(0, 200, 41),
        label=label,
        year=year,
        com=com,
    )

    plot_pair_distribution(
        values=pair_tree['probe_eta'],
        xlabel=r'Probe muon $\eta$',
        output_path=output_dir / 'probe_eta',
        bins=np.linspace(-2.5, 2.5, 51),
        label=label,
        year=year,
        com=com,
    )

    plot_pair_distribution(
        values=pair_tree['probe_phi'],
        xlabel=r'Probe muon $\phi$ [rad]',
        output_path=output_dir / 'probe_phi',
        bins=np.linspace(-3.2, 3.2, 65),
        label=label,
        year=year,
        com=com,
    )