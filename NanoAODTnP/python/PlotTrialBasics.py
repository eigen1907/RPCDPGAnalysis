from pathlib import Path
from typing import Union

import numpy as np
import uproot
import matplotlib as mpl
mpl.use('agg')
import matplotlib.pyplot as plt
import mplhep as mh

mh.style.use(mh.styles.CMS)


def plot_trial_distribution(values: np.ndarray,
                            xlabel: str,
                            output_path: Path,
                            bins: Union[int, np.ndarray],
                            label: str,
                            year: Union[int, str],
                            com: float,
                            ylabel: str = 'Counts',
                            close: bool = True):
    values = np.asarray(values)
    values = values[np.isfinite(values)]

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.hist(values, bins=bins, histtype='step', linewidth=2)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    mh.cms.label(ax=ax, llabel=label, com=com, year=year)

    fig.savefig(output_path.with_suffix('.png'))
    if close:
        plt.close(fig)

    return fig


def plot_trial_category(values: np.ndarray,
                        xlabel: str,
                        output_path: Path,
                        label: str,
                        year: Union[int, str],
                        com: float,
                        ylabel: str = 'Counts',
                        close: bool = True):
    values = np.asarray(values)
    values = values[np.isfinite(values)]

    uniq, counts = np.unique(values, return_counts=True)

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.bar(uniq, counts, width=0.8)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(uniq)
    mh.cms.label(ax=ax, llabel=label, com=com, year=year)

    fig.savefig(output_path.with_suffix('.png'))
    if close:
        plt.close(fig)

    return fig


def plot_trial_efficiency_summary(is_fiducial: np.ndarray,
                                  is_matched: np.ndarray,
                                  output_path: Path,
                                  label: str,
                                  year: Union[int, str],
                                  com: float,
                                  close: bool = True):
    is_fiducial = np.asarray(is_fiducial, dtype=bool)
    is_matched = np.asarray(is_matched, dtype=bool)

    n_total = len(is_fiducial)
    n_fid = int(np.sum(is_fiducial))
    n_matched_all = int(np.sum(is_matched))
    n_matched_fid = int(np.sum(is_fiducial & is_matched))

    values = np.array([
        n_total,
        n_fid,
        n_matched_all,
        n_matched_fid,
    ], dtype=np.int64)

    labels = [
        'All trials',
        'Fiducial trials',
        'Matched trials',
        'Matched & fiducial',
    ]

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.bar(np.arange(len(values)), values, width=0.7)
    ax.set_xticks(np.arange(len(values)))
    ax.set_xticklabels(labels, rotation=20, ha='right')
    ax.set_ylabel('Counts')

    mh.cms.label(ax=ax, llabel=label, com=com, year=year)

    fig.tight_layout()
    fig.savefig(output_path.with_suffix('.png'))

    if close:
        plt.close(fig)

    return fig


def plot_trial_basics(input_path: Path,
                      output_dir: Path,
                      com: float,
                      year: Union[int, str],
                      label: str):
    input_file = uproot.open(input_path)

    branch_names = [
        'is_fiducial', 'is_matched',
        'region', 'ring', 'station', 'sector', 'layer', 'subsector', 'roll',
        'cls', 'bx',
        'residual_x', 'residual_y',
        'pull_x', 'pull_y', 'pull_x_v2', 'pull_y_v2',
        'probe_dxdz', 'probe_dydz',
        'probe_pt', 'probe_eta', 'probe_phi',
    ]

    trial_tree = input_file['trial_tree'].arrays(branch_names, library='np')

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    is_fiducial = np.asarray(trial_tree['is_fiducial'], dtype=bool)
    is_matched = np.asarray(trial_tree['is_matched'], dtype=bool)
    matched_mask = is_matched
    fid_matched_mask = is_fiducial & is_matched

    plot_trial_efficiency_summary(
        is_fiducial=is_fiducial,
        is_matched=is_matched,
        output_path=output_dir / 'trial_summary',
        label=label,
        year=year,
        com=com,
    )

    plot_trial_category(
        values=trial_tree['region'],
        xlabel='Region',
        output_path=output_dir / 'region',
        label=label,
        year=year,
        com=com,
    )

    plot_trial_category(
        values=trial_tree['station'],
        xlabel='Station',
        output_path=output_dir / 'station',
        label=label,
        year=year,
        com=com,
    )

    plot_trial_category(
        values=trial_tree['ring'],
        xlabel='Ring',
        output_path=output_dir / 'ring',
        label=label,
        year=year,
        com=com,
    )

    plot_trial_category(
        values=trial_tree['layer'],
        xlabel='Layer',
        output_path=output_dir / 'layer',
        label=label,
        year=year,
        com=com,
    )

    plot_trial_category(
        values=trial_tree['sector'],
        xlabel='Sector',
        output_path=output_dir / 'sector',
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['probe_dxdz'],
        xlabel=r'Probe $dX/dZ$',
        output_path=output_dir / 'probe_dxdz',
        bins=np.linspace(-1.0, 1.0, 101),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['probe_dydz'],
        xlabel=r'Probe $dY/dZ$',
        output_path=output_dir / 'probe_dydz',
        bins=np.linspace(-1.0, 1.0, 101),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['probe_pt'],
        xlabel=r'Probe muon $p_{T}$ [GeV] (trial-weighted)',
        output_path=output_dir / 'probe_pt_trial_weighted',
        bins=np.linspace(0, 200, 41),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['probe_eta'],
        xlabel=r'Probe muon $\eta$ (trial-weighted)',
        output_path=output_dir / 'probe_eta_trial_weighted',
        bins=np.linspace(-2.5, 2.5, 51),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['probe_phi'],
        xlabel=r'Probe muon $\phi$ [rad] (trial-weighted)',
        output_path=output_dir / 'probe_phi_trial_weighted',
        bins=np.linspace(-3.2, 3.2, 65),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['cls'][matched_mask],
        xlabel='Cluster size',
        output_path=output_dir / 'cluster_size_matched',
        bins=np.arange(-0.5, 11.5, 1.0),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['bx'][matched_mask],
        xlabel='BX',
        output_path=output_dir / 'bx_matched',
        bins=np.arange(-5.5, 6.5, 1.0),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['residual_x'][fid_matched_mask],
        xlabel='Residual X [cm]',
        output_path=output_dir / 'residual_x_fid_matched',
        bins=np.linspace(-20, 20, 101),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['residual_y'][fid_matched_mask],
        xlabel='Residual Y [cm]',
        output_path=output_dir / 'residual_y_fid_matched',
        bins=np.linspace(-20, 20, 101),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['pull_x'][fid_matched_mask],
        xlabel='Pull X',
        output_path=output_dir / 'pull_x_fid_matched',
        bins=np.linspace(-10, 10, 101),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['pull_y'][fid_matched_mask],
        xlabel='Pull Y',
        output_path=output_dir / 'pull_y_fid_matched',
        bins=np.linspace(-10, 10, 101),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['pull_x_v2'][fid_matched_mask],
        xlabel='Pull X V2',
        output_path=output_dir / 'pull_x_v2_fid_matched',
        bins=np.linspace(-10, 10, 101),
        label=label,
        year=year,
        com=com,
    )

    plot_trial_distribution(
        values=trial_tree['pull_y_v2'][fid_matched_mask],
        xlabel='Pull Y V2',
        output_path=output_dir / 'pull_y_v2_fid_matched',
        bins=np.linspace(-10, 10, 101),
        label=label,
        year=year,
        com=com,
    )