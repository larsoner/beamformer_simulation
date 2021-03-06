import mne
from config import fname, subject_id

epochs = mne.read_epochs(fname.epochs)
noise_cov = mne.compute_covariance(epochs, tmin=-0.2, tmax=0, method='shrunk', rank='info')
data_cov = mne.compute_covariance(epochs, tmin=0, tmax=0.4, method='empirical', rank='info')
fwd = mne.read_forward_solution(fname.fwd)
inv = mne.beamformer.make_lcmv(epochs.info, fwd, data_cov, reg=0.05, noise_cov=noise_cov, weight_norm=None, pick_ori=None)
stc = mne.beamformer.apply_lcmv(epochs.average(), inv)
stc.subject = subject_id
stc.save(fname.stc_lcmv)

stc_peak = abs(stc.copy().crop(0.030, 0.050).mean())
stc_peak.save_as_volume(fname.nii_lcmv, src=fwd['src'])

fig = stc_peak.plot(subject=subject_id, subjects_dir=fname.subjects_dir, src=fwd['src'],
                    clim=dict(kind='percent', lims=[99.8, 99.9, 100]))
with mne.open_report(fname.report) as report:
    report.add_figs_to_section(fig, 'LCMV Source estimate at 40ms', 'Source level', replace=True)
    report.save(fname.report_html, overwrite=True, open_browser=False)
