import mne
import numpy as np
from tqdm import tqdm

from mne.simulation import simulate_sparse_stc, simulate_raw
from time_series import generate_signal, generate_random
from utils import add_volume_stcs
from matplotlib import pyplot as plt

import config
from config import vfname

info = mne.io.read_info(vfname.sample_raw)
info = mne.pick_info(info, mne.pick_types(info, meg=True, eeg=False))

fwd = mne.read_forward_solution(vfname.fwd)
fwd = mne.pick_types_forward(fwd, meg=True, eeg=False)
src = fwd['src']

bem_fname = vfname.bem
bem = mne.read_bem_surfaces(bem_fname)
trans = mne.read_trans(vfname.trans)

rng = config.random

times = np.arange(0, config.trial_length * info['sfreq']) / info['sfreq']

# there is only one volume source space
vertno = src[0]['vertno']

###############################################################################
# Simulate a single signal dipole source as signal
###############################################################################

signal_vertex = src[0]['vertno'][config.vertex]
data = np.asarray([generate_signal(times, freq=config.signal_freq)])
vertices = np.array([signal_vertex])
stc_signal = mne.VolSourceEstimate(data=data, vertices=vertices, tmin=0,
                                   tstep=1 / info['sfreq'], subject='sample')

stc_signal.save(vfname.stc_signal)

###############################################################################
# Create discrete source space based on voxels in volume source space
###############################################################################

rr = src[0]['rr']
nn = src[0]['nn']

pos = {'rr': rr, 'nn': nn}

# make discrete source space
src_disc = mne.setup_volume_source_space(subject='sample', pos=pos,
                                         mri=None, bem=bem)

# setup_volume_source_space sets coordinate frame to MRI
# coordinates we supplied are in head frame
src_disc[0]['coord_frame'] = fwd['src'][0]['coord_frame']

# np.array_equal(fwd_sel['src'][0]['rr'], fwd['src'][0]['rr'][stc.vertices]) is True
# np.isclose(fwd_sel['src'][0]['nn'], fwd['src'][0]['nn'][stc.vertices]) is True for all entries
fwd_disc = mne.make_forward_solution(info, trans=trans, src=src_disc,
                                     bem=bem_fname, meg=True, eeg=False)

fwd_disc = mne.convert_forward_solution(fwd_disc, surf_ori=True,
                                        force_fixed=True)


###############################################################################
# Create trials of simulated data
###############################################################################

volume_labels = mne.get_volume_labels_from_aseg(vfname.aseg)
n_noise_dipoles = config.n_noise_dipoles_vol

# select n_noise_dipoles entries from rr and their corresponding entries from nn
poss_indices = np.arange(rr.shape[0])

raw_list = []

for i in tqdm(range(config.n_trials), desc='Generating trials',
              total=config.n_trials, unit='trials'):
    ###########################################################################
    # Simulate random noise dipoles
    ###########################################################################
    stc_noise = simulate_sparse_stc(
        src,
        n_noise_dipoles,
        times,
        data_fun=generate_random,
        random_state=config.random,
        labels=None
    )

    ###########################################################################
    # Project to sensor space
    ###########################################################################

    stc = add_volume_stcs(stc_signal, config.SNR * stc_noise)

    raw = simulate_raw(
        info,
        stc,
        trans=None,
        src=None,
        bem=None,
        forward=fwd_disc,
        duration=config.trial_length,
        cov=None,
        random_state=rng,
    )

    raw_list.append(raw)

raw = mne.concatenate_raws(raw_list)


###############################################################################
# Use empty room noise as sensor noise
###############################################################################
er_raw = mne.io.read_raw_fif(vfname.ernoise, preload=True)
raw_picks = mne.pick_types(raw.info, meg=True, eeg=False)
er_raw_picks = mne.pick_types(er_raw.info, meg=True, eeg=False)
raw._data[raw_picks] += er_raw._data[er_raw_picks, :len(raw.times)]

###############################################################################
# Save everything
###############################################################################

raw.save(vfname.simulated_raw, overwrite=True)

###############################################################################
# Plot it!
###############################################################################
with mne.open_report(vfname.report) as report:
    fig = plt.figure()
    plt.plot(times, generate_signal(times, freq=10))
    plt.xlabel('Time (s)')
    report.add_figs_to_section(fig, 'Signal time course',
                               section='Sensor-level', replace=True)

    fig = raw.plot()
    report.add_figs_to_section(fig, 'Simulated raw', section='Sensor-level',
                               replace=True)
    report.save(vfname.report_html, overwrite=True, open_browser=False)
