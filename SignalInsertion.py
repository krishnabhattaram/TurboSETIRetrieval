from astropy import units as u
import setigen as stg
import matplotlib.pyplot as plt
from IPython.utils import io

import sys
import numpy as np
import os

import math

from blimpy import Waterfall
import random 

outfilename = "setigenframe"

def waterfall_generator(waterfall_fn, fchans, f_begin=None, f_end=None, f_shift=None):
    """
    Adapted from setigen's split_waterfall_generator method
    """

    info_wf = Waterfall(waterfall_fn, load_data=False)
    fch1 = info_wf.header['fch1']
    nchans = info_wf.header['nchans']
    df = abs(info_wf.header['foff'])
    tchans = info_wf.container.selection_shape[0]

    if f_end is None or f_end > fch1:
        f_stop = fch1
        f_end = fch1
    else:
        f_stop = f_end
        
    if f_begin is None or f_begin < fch1 - nchans * df:
        f_start = fch1 - fchans * df
        f_begin = fch1 - nchans * df
    else:
        f_start = f_end - fchans*df
    
    if f_shift == None:
        f_shift = fchans

    # Iterates down frequencies, starting from highest
    print("\nStarting at f_begin = ", f_begin)
    print("Ending at f_end = ", f_end)
    print("Iterating with width = ", f_shift * df, '\n')
    while f_start >= f_begin:
        waterfall = Waterfall(waterfall_fn,
                              f_start=f_start,
                              f_stop=f_stop,
                              t_start=0,
                              t_stop=tchans)

        yield waterfall

        f_start -= f_shift * df
        f_stop -= f_shift * df

def num_frames(waterfall_fn, fchans, f_begin=None, f_end=None, f_shift=None):
    info_wf = Waterfall(waterfall_fn, load_data=False)
    fch1 = info_wf.header['fch1']
    nchans = info_wf.header['nchans']
    df = abs(info_wf.header['foff'])
    tchans = info_wf.container.selection_shape[0]

    if f_end is None or f_end > fch1:
        f_stop = fch1
        f_end = fch1
    else:
        f_stop = f_end

    if f_begin is None or f_begin < fch1 - nchans * df:
        f_start = fch1 - fchans * df
        f_begin = fch1 - nchans * df
    else:
        f_start = f_end - fchans*df

    if f_shift == None:
        f_shift = fchans

    # Iterates down frequencies, starting from highest
    i = 0
    while f_start >= f_begin:
        i += 1

        f_start -= f_shift * df
        f_stop -= f_shift * df
    return i

def insert_signal(frame, freq, drift, snr, width):
    print("Inserting signal", freq, drift, snr, width, frame.df, frame.dt, frame.fch1, frame.tchans, frame.fchans)
    tchans = frame.tchans*u.pixel
    dt = frame.dt*u.s

    fexs = freq*u.MHz - math.copysign(1, drift)*width*u.Hz
    fex = (freq*u.MHz + ((drift*u.Hz/u.s)*dt*tchans/u.pixel)
               + math.copysign(1, drift)*width*u.Hz)/u.Hz

    signal = frame.add_signal(stg.constant_path(f_start=freq*u.MHz,
                                       drift_rate=drift*u.Hz/u.s),
                                       stg.constant_t_profile(level=frame.get_intensity(snr=snr)),
                                       stg.gaussian_f_profile(width=width*u.Hz),
                                       stg.constant_bp_profile(level=1),
                                       bounding_f_range=(min(fexs/u.Hz,fex), max(fexs/u.Hz,fex)))

def save_frame(frame):
    frame.save_fil(filename=outfilename+'.fil')

def drifts_default(N, val=0):
    return N*[val]

def snrs_default(N, val=50):
    return N*[val]

def widths_default(N, val=40):
    return N*[val]

def noise_parameters(frame, near=False, drift_max=2):
    parameters = [0]*2
    
    drift = random.uniform(-1,1)*drift_max
    parameters[1] = drift

    if near:
        parameters[0] = (frame.get_frequency(frame.fchans//2) + random.uniform(-1, 1)*(drift*frame.dt*frame.tchans))*u.Hz/u.MHz
    else :
        parameters[0] = frame.get_frequency(int(random.uniform(0, frame.fchans)))*u.Hz/u.MHz
    return parameters

def turbo_runner(waterfall_itr, drifts=None, snrs=None, widths=None, snrRatio=None, max_drift=5, min_snr=15, num_inserted=1):
    obs_info = {} 
    obs_info['pulsar'] = 0  # Bool if pulsar detection.
    obs_info['pulsar_found'] = 0  # Bool if pulsar detection.
    obs_info['pulsar_dm'] = 0.0  # Pulsar expected DM.
    obs_info['pulsar_snr'] = 0.0 # SNR
    obs_info['pulsar_stats'] = np.zeros(6)
    obs_info['RFI_level'] = 0.0
    obs_info['Mean_SEFD'] = 0.0
    obs_info['psrflux_Sens'] = 0.0
    obs_info['SEFDs_val'] = [0.0]
    obs_info['SEFDs_freq'] = [0.0]
    obs_info['SEFDs_freq_up'] = [0.0]

    turbo_vals = []
    signal_capture = []

    for i, waterfall in enumerate(waterfall_itr):
        frame = stg.Frame(waterfall=waterfall)
        freq = frame.get_frequency(frame.fchans//2)*u.Hz/u.MHz
        
        noise_recovered = 0

        if drifts is None:
            drift = 0
        else: 
            drift = drifts[i]

        if snrs is None:
            snr = 40
        else:
            snr = snrs[i]
        
        if widths is None:
            width = 40
        else:
            width = widths[i]

        drift_noise = max_drift

        if snrRatio is None:
            snr_noise = 0.5*snr
        else:
            snr_noise = snr*snrRatio[i]

        width_noise = width

        insert_signal(frame, freq, drift, snr, width)
        
        noise = [0*u.Hz, 0]
        for _ in range(num_inserted - 1):
            noise = noise_parameters(frame, False, drift_noise)
            insert_signal(frame, noise[0], noise[1], snr_noise, width_noise)
       
        save_frame(frame)
        try:
            os.remove(out_directory + '/' + outfilename + '.dat')
            os.remove(out_directory + '/' + outfilename +'.log')
        except:
            pass

        fil_fn = outfilename + '.fil'
        find_seti_event = FindDoppler(fil_fn,
                     max_drift=max_drift,snr=min_snr,out_dir=out_directory,
                     obs_info=obs_info)
        find_seti_event.search()

        f = open(out_directory + '/' + outfilename + '.dat', 'r')
        try:
            data = [dataline.split() for dataline in [line for line in f.readlines() if line[0] != '#']]
            data = [[float(val) for val in dataline] for dataline in data]
        except:
            data = []
        if len(data) == 0:
            data = [[0.0]*12]
            num_recovered = 0
        else:
            num_recovered = len(data)
        turbo_vals += [data]

        signal_capture += [[num_recovered, num_inserted, freq.value/1e6, drift, snr, width, [data], [noise[0].value/1e6, noise[1], snr_noise]]] 
        print(i, signal_capture[i])
        print("")
    return signal_capture

from turbo_seti.find_doppler.find_doppler import FindDoppler

out_directory = './turboOutput'

file_path ='/mnt_blpd7/datax/hard_linked_in_dl/gbl/spliced_blc0001020304050607_guppi_57557_47744_HIP3092_0005.gpuspec.0000.h5'

fchans = 1024
f_begin = 1340
f_shift = 102400
f_end = None

waterfall_itr = waterfall_generator(file_path,
                                    fchans,
                                    f_begin=f_begin,
                                    f_end=f_end,
                                    f_shift=f_shift)

N = num_frames(file_path,fchans,f_begin=f_begin,f_end=f_end,f_shift=102400)
turbo_vals = turbo_runner(waterfall_itr, max_drift=5, num_inserted=2)

print("#Index #RatioCaptured #FreqIns #FreqCap #driftIns #driftCap #snrIns #snrCap #widthIns #DistanceNoiseCenter #DriftNoise #SNRNoise")
for n,row in enumerate(turbo_vals):
    print(n, 
    row[0]/row[1], 
    row[2], 
    row[6][0][0][1], 
    row[3], 
    row[6][0][0][3], 
    row[4],
    row[6][0][0][2], 
    row[5],
    row[7][0] - row[2], 
    row[7][1],
    row[7][2])

