import mne
from mne.beamformer import make_lcmv, apply_lcmv
import numpy as np
from itertools import product
import pandas as pd

import config
from config import vfname
from utils import make_dipole_volume, evaluate_stc_volume

# Read in the simulated data
stc_signal = mne.read_source_estimate(vfname.stc_signal(noise=config.noise, vertex=config.vertex))
epochs = mne.read_epochs(vfname.simulated_epochs(noise=config.noise, vertex=config.vertex))
fwd_disc = mne.read_forward_solution(vfname.fwd_discrete)

# For pick_ori='normal', the fwd needs to be in surface orientation
# TODO: this should not be necessary since convert_forward_solution has used during fwd_disc creation
fwd_disc = mne.convert_forward_solution(fwd_disc, surf_ori=True)

# The DICS beamformer currently only uses one sensor type
epochs_grad = epochs.copy().pick_types(meg='grad')
epochs_mag = epochs.copy().pick_types(meg='mag')

# Make cov matrix
cov = mne.compute_covariance(epochs)

evoked_grad = epochs_grad.average()
evoked_mag = epochs_mag.average()

# Compute the settings grid
regs = [0.05, 0.1, 0.5]
sensor_types = ['grad', 'mag']
pick_oris = [None, 'normal', 'max-power']
weight_norms = ['unit-noise-gain', 'nai', None]
settings = list(product(regs, sensor_types, pick_oris, weight_norms))

# Compute DICS beamformer with all possible settings
dists = []
evals = []
for setting in settings:
    reg, sensor_type, pick_ori, weight_norm = setting
    try:
        if sensor_type == 'grad':
            evoked = evoked_grad
        elif sensor_type == 'mag':
            evoked = evoked_mag
        else:
            raise ValueError('Invalid sensor type: %s', sensor_type)

        filters = make_lcmv(evoked.info, fwd_disc, cov, reg=reg, pick_ori=pick_ori,
                            weight_norm=weight_norm)
        stc = apply_lcmv(evoked, filters)

        # Compute distance between true and estimated source
        dip_true = make_dipole_volume(stc_signal, fwd_disc['src'])
        dip_est = make_dipole_volume(stc, fwd_disc['src'])
        dist = np.linalg.norm(dip_true.pos - dip_est.pos)

        # Fancy evaluation metric
        ev = evaluate_stc_volume(stc, stc_signal)
    except Exception as e:
        print(e)
        dist = np.nan
        ev = np.nan
    print(setting, dist, ev)

    dists.append(dist)
    evals.append(ev)

# Save everything to a pandas dataframe
df = pd.DataFrame(settings, columns=['reg', 'sensor_type', 'pick_ori',
                                     'weight_norm'])
df['dist'] = dists
df['eval'] = evals
df.to_csv(vfname.lcmv_results(noise=config.noise, vertex=config.vertex))