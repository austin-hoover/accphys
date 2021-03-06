"""
This script repeatedly tracks a beam through the RTBT, each time varying the 
optics and computing the phase advance, transfer matrix, and beam moments at 
the 5 wire-scanners.
""" 
import sys
import numpy as np
from numpy import pi
import pandas as pd

from bunch import Bunch
from orbit_utils import Matrix
from spacecharge import SpaceChargeCalc2p5D
from orbit.analysis import AnalysisNode, WireScannerNode, add_analysis_node
from orbit.envelope import DanilovEnvelope
from orbit.space_charge.envelope import set_env_solver_nodes, set_perveance
from orbit.space_charge.sc2p5d.scLatticeModifications import setSC2p5DAccNodes
from orbit.teapot import TEAPOT_Lattice
from orbit.utils import helper_funcs as hf

sys.path.append('/Users/46h/Research/code/accphys')
from tools.utils import delete_files_not_folders

sys.path.append('/Users/46h/Research/code/accphys/pyorbit/measurement')
from utils import PhaseController


# Settings
#------------------------------------------------------------------------------
# General
mass = 0.93827231 # GeV/c^2
kin_energy = 0.8 # GeV
intensity = 0.0e1
bunch_length = 150.0 # [m]
nparts = int(0.2e5)
max_solver_spacing = 1.0
min_solver_spacing = 0.00001
gridpts = (128, 128, 1)
latfile = '_input/rtbt.lat'
latseq = 'surv'

# Initial beam
eps = 40e-6 # nonzero intrinsice emittance ex + ey [m*rad]
mode = 1
ex_frac = 0.4
ex, ey = ex_frac * eps, (1 - ex_frac) * eps
init_twiss = (-8.082, 4.380, 23.373, 13.455) # (ax, ay, bx, by)

# Scan parameters
ws_names = ['ws02', 'ws20', 'ws21', 'ws23', 'ws24']
ref_ws_name = 'ws24' 
steps_per_dim = 6 # number of steps for each dimension
method = 2
ws_bins = 25
phase_coverage = 180 # [deg]
max_betas = (40, 40) # (x, y)
diag_wire_angle = np.radians(30.0)


# Initialization
#------------------------------------------------------------------------------
delete_files_not_folders('_output/')

dummy_lattice = hf.lattice_from_file(latfile, latseq)
controller = PhaseController(dummy_lattice, init_twiss, mass, kin_energy, ref_ws_name)

# Save default optics
twiss_df = pd.DataFrame(np.copy(controller.tracked_twiss), 
                        columns=['s','nux','nuy','ax','ay','bx','by'])
twiss_df[['nux','nuy']] %= 1
twiss_df.to_csv('_output/data/twiss.dat', index=False)

# Save wire-scanner positions
ws_positions = [controller.get_node_position(ws) for ws in ws_names]
np.savetxt('_output/data/ws_positions.dat', ws_positions)
    
# Set up initial bunch
init_env = DanilovEnvelope(eps, mode, ex_frac, mass, kin_energy, length=0.66*248.0)
ax0, ay0, bx0, by0 = init_twiss
init_env.fit_twiss2D(ax0, ay0, bx0, by0, ex_frac)
init_env.set_twiss_param_4D('nu', np.radians(100))
X0 = init_env.generate_dist(nparts)

def reset_bunch():
    bunch, params_dict = hf.initialize_bunch(mass, kin_energy)
    hf.dist_to_bunch(X0, bunch, bunch_length)
    bunch.macroSize(intensity / nparts)
    return bunch, params_dict

np.savetxt('_output/data/init_env_params.dat', init_env.params)


# Create lattice
#------------------------------------------------------------------------------
lattice = hf.lattice_from_file(latfile, latseq)

# Add space charge nodes
if intensity > 0:
    lattice.split(max_solver_spacing)    
    calc2p5d = SpaceChargeCalc2p5D(*gridpts)
    sc_nodes = setSC2p5DAccNodes(lattice, min_solver_spacing, calc2p5d)
    
# Add wire-scanner nodes
ws_nodes = {}
for ws in ws_names:
    parent_node = lattice.getNodeForName(ws)
    ws_node = WireScannerNode(ws_bins, diag_wire_angle, name=ws)
    parent_node.addChildNode(ws_node, parent_node.ENTRANCE)
    ws_nodes[ws] = ws_node

# Create separate lattice for envelope tracking
env_lattice = hf.lattice_from_file('_input/rtbt.lat', 'surv')
env = init_env.copy()
env.set_intensity(intensity)
env_solver_nodes = set_env_solver_nodes(env_lattice, env.perveance, max_solver_spacing)
env_monitor_nodes = {ws: add_analysis_node(env_lattice, ws, 'env_monitor')
                     for ws in ws_names}


# Perform scan
#------------------------------------------------------------------------------
def init_dict():
    return {ws:[] for ws in ws_names}

transfer_mats = init_dict()
moments = init_dict()
coords = init_dict()
ws_phases = init_dict()
env_params = init_dict()

scan_phases = controller.get_phases_for_scan(phase_coverage, steps_per_dim, method)

for scan_index, (nux, nuy) in enumerate(scan_phases, start=1):
    # Set phases at reference wire-scanner
    print 'Scan {} of {}.'.format(scan_index, 2 * steps_per_dim)
    print '  Setting phases: nux, nuy = {:.3f}, {:.3f}.'.format(nux, nuy)
    controller.set_ref_ws_phases(nux, nuy, max_betas, verbose=2)
    controller.track_twiss()
    controller.apply_settings(lattice)

    # Track bunch
    print '  Tracking bunch.'
    bunch, params_dict = reset_bunch()
    lattice.trackBunch(bunch, params_dict)
    
    # Compute moments and transfer matrix at each wire-scanner
    for ws in ws_names:
        moments[ws].append(ws_nodes[ws].get_moments())
        transfer_mats[ws].append(controller.get_transfer_matrix(ws))
        ws_phases[ws].append(controller.get_phases(ws))

    # Track envelope for comparison
    controller.apply_settings(env_lattice)
    for node in env_monitor_nodes.values():
        node.clear_data()
    env.params = init_env.params
    env.track(env_lattice)
    for ws in ws_names:
        env_params[ws].append(env_monitor_nodes[ws].get_data('env_params'))

            
# Save data
#------------------------------------------------------------------------------
for ws in ws_names:
    np.save('_output/data/{}/phases.npy'.format(ws), ws_phases[ws])
    np.save('_output/data/{}/transfer_mats.npy'.format(ws), transfer_mats[ws])
    np.save('_output/data/{}/moments.npy'.format(ws), moments[ws])
    np.save('_output/data/{}/env_params.npy'.format(ws), env_params[ws])
    
np.save('_output/data/Sigma0_env.npy', env.cov())
np.savetxt('_output/data/Sigma0.dat', np.cov(X0.T))
np.savetxt('_output/data/X0.dat', X0)