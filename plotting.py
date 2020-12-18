"""
This module contains functions to visualize accelerator physics data. Right now
there are mainly routines to display the relationships between the 4D phase
space coordinates of a 2D distribution of particles.

To do:
    * Add `grid` option to `corner` and `corner_env`.
    * Possibly create separate file for plotting utility functions.
    * Add function: tune space resonance lines (complete; on hardrive currently)
    * Create function: tune footprint.
"""

# Standard
from cycler import cycler
# Third party
import numpy as np
import pandas as pd
import matplotlib
from matplotlib import pyplot as plt, animation, ticker
import seaborn as sns
import scipy
from pandas.plotting._matplotlib.tools import _set_ticks_props
# Local
from . import envelope_analysis as ea
from .utils import rand_rows, merge_dicts

# Module level variables
_labels = [r"$x$", r"$x'$", r"$y$", r"$y'$"]
_labels_norm = [r"$x_n$", r"$x_n'$", r"$y_n$", r"$y_n'$"]
plt_kws_default = dict(s=3, c='steelblue', marker='.', ec='none', zorder=5)
diag_kws_default = dict(histtype='step', bins='auto', color='steelblue')
env_kws_default = dict(color='k', lw=1, zorder=5)
text_kws_default = dict(horizontalalignment='center')


def save(figname, dir, **kwargs):
    """Save figure to directory `dir`."""
    if not dir.endswith('/'):
        dir += '/'
    filename = ''.join([dir, figname, '.png'])
    plt.savefig(filename, facecolor='white', **kwargs)


def get_u_up_max(X):
    """Get the maximum x{y} and x'{y'} extents for any frame in `coords`.

    X : ndarray, shape (nparts, 4)
        The beam coordinate array.
    """
    xmax, xpmax, ymax, ypmax = np.max(X, axis=0)
    umax, upmax = max(xmax, ymax), max(xpmax, ypmax)
    return np.array([umax, upmax])
    
    
def get_u_up_max_global(coords):
    """Get the maximum x{y} and x'{y'} extents for any frame in `coords`.

    coords : ndarray, shape (nframes, nparts, 4)
        The beam coordinate arrays at each frame.
    """
    u_up_local_maxes = np.array([get_u_up_max(X) for X in coords])
    umax_global, upmax_global = np.max(u_up_local_maxes, axis=0)
    return np.array([umax_global, upmax_global])
    
    
def despine(ax_list, sides=('top', 'right')):
    """Remove the axis spines."""
    # Might want to look at this function in seaborn: https://github.com/mwaskom/seaborn/blob/master/seaborn/utils.py
    if type(sides) is str:
        sides = (sides,)
    for ax in ax_list:
        for side in sides:
            if ax is not None:
                ax.spines[side].set_visible(False)
                if side == 'left':
                    ax.yaxis.set_visible(False)
                if side == 'bottom':
                    ax.xaxis.set_visible(False)
            
            
def make_lower_triangular(axes):
    """"Remove all top-right subplots (above diagonal)."""
    for i, j in zip(*np.triu_indices(axes.shape[0], 1)):
        axes[i, j].axis('off')
        

def get_labels(units=None, norm_labels=False):
    """Return phase space labels ([x, xp, y, yp]), possibly with units."""
    labels = _labels_norm if norm_labels else _labels
    if units == 'm-rad':
        unit_labels = 2 * [' [m]', ' [rad]']
    elif units == 'mm-mrad':
        unit_labels = 2 * [' [mm]', ' [mrad]']
    else:
        unit_labels = 4 * ['']
    return [lab + ulab for (lab, ulab) in zip(labels, unit_labels)]
    
    
def set_labels(ax_list, labels=[], kind='xlabel', **kws):
    """Set the axis labels/titles for the list of subplots."""
    for ax, label in zip(ax_list, labels):
        if kind == 'xlabel':
            ax.set_xlabel(label, **kws)
        elif kind == 'ylabel':
            ax.set_ylabel(label, **kws)
        if kind == 'title':
            ax.set_title(label, **kws)

            
def set_limits(ax_list, limits=[], dim='x'):
    """Set the x or y axis limits for the list of subplots."""
    for ax, lim in zip(ax_list, limits):
        if dim == 'x':
            ax.set_xlim(lim)
        elif dim == 'y':
            ax.set_ylim(lim)
            

def hide_axis_labels(ax_list, dim='x'):
    """Turn off tick labels and offset text along u axis, where u = x or y"""
    for ax in ax_list:
        uaxis = {'x':ax.xaxis, 'y':ax.yaxis}[dim]
        uaxis.set_tick_params(which='both', labelbottom=False, labeltop=False)
        uaxis.offsetText.set_visible(False)
        
        
def toggle_grid(axes_list, switch='off', **kws):
    grid = {'off':False, 'on':True}[switch]
    for ax in axes_list:
        ax.grid(grid, **kws)
            
        
def set_share_axes(axes, sharex=False, sharey=False, type_if_1D='row'):
    """Custom axis sharing.
    
    Taken from StackOverflow answer by 'herrlich10': 'https://stackoverflow.com/questions/23528477/share-axes-in-matplotlib-for-only-part-of-the-subplots'.

    Parameters
    ----------
    axes : ndarray of Axes objectes
        The axes to group together.
    sharex{y} : bool
        Whether to share the x{y} axis.
    type_if_1D : {'row', 'col'}
        Determines if we are working with a column or row if `axes` is 1D.
    """
    if axes.ndim == 1:
        if type_if_1D == 'row':
            axes = axes[np.newaxis, :]
        elif type_if_1D == 'col':
            axes = axes[:, np.newaxis]
    target = axes.flat[0]
    for ax in axes.flat:
        if sharex:
            target._shared_x_axes.join(target, ax)
        if sharey:
            target._shared_y_axes.join(target, ax)
    if sharex:
        hide_axis_labels(axes[:-1, :].flat, 'x')
    if sharey:
        hide_axis_labels(axes[:, 1:].flat, 'y')


def setup_corner(limits, figsize, norm_labels, units, space=None,
                 plt_diag=False, **text_kws):
    """Set up lower left corner plot.
    
    X O O O
    X X O O
    X X X O
    X X X X
    
    Inputs
    ------
    limits : (umax, upmax)
        The maximum position (umax) and slope (upmax) in the plot windows.
    figsize : tuple or int
        Size of the figure (x_size, y_size). If an int is provided, the number
        is used as the size for both dimensions.
    norm_labels : boolean
        If True, add an 'n' subscript to axis labels. E.g. 'x' -> 'x_n'
    units : str
        If `m-rad` or `mm-mrad`, the appropriat units are attached to each
        axis label (such as x [mm] or x' [mrad]). Otherwise no units are
        displayed.
    space : float
        Size of the space between subplots. If None, the `tight_layout`
        optimizer is used to determined the spacing.
    plt_diag : bool
        Whether to include the subplots on the diagonal (4x4 vs. 3x3).
    **text_kws
        Key word arguments for axis text.

    Returns
    -------
    fig, axes
    """
    # Preliminaries
    tight = space is None
    sharey = False if plt_diag else 'row'
    if type(figsize) is int:
        figsize = (figsize, figsize)
    if norm_labels:
        units = None
    labels = get_labels(units, norm_labels)
    umax, upmax = limits
    limits = 2 * [(-umax, umax), (-upmax, upmax)]
    f_u, f_up = ticker.MaxNLocator(3), ticker.MaxNLocator(3)
    mf_u, mf_up = ticker.AutoMinorLocator(4), ticker.AutoMinorLocator(4)
    fmtrs = 2 * [f_u, f_up]
    mfmtrs = 2 * [mf_u, mf_up]
    
    # Create figure
    nrows, ncols = (4, 4) if plt_diag else (3, 3)
    fig, axes = plt.subplots(nrows, ncols, sharex='col', sharey=sharey,
                             figsize=figsize)
    if not tight:
        fig.subplots_adjust(wspace=space, hspace=space)
    make_lower_triangular(axes)
    despine(axes.flat, ('top', 'right'))

    # Configure axis sharing
    l_col, b_row, diag = axes[:, 0], axes[-1, :], axes.diagonal()
    if plt_diag:
        l_col = l_col[1:]
        l_col_labels = labels[1:]
        l_col_limits = limits[1:]
        l_col_fmtrs = fmtrs[1:]
        l_col_mfmtrs = mfmtrs[1:]
        b_row_labels = labels
        b_row_limits = limits
        b_row_fmtrs = fmtrs
        b_row_mfmtrs = mfmtrs
        for i, row in enumerate(axes[1:, :]): # share scatter plot y axis
            set_share_axes(row[:i+1], sharey=True)
        set_share_axes(diag, sharey=True) # share histogram y axis
        # Don't show y-axis on histogram subplots
        despine(diag, 'left')
        toggle_grid(diag, 'off')
    else:
        l_col_labels = labels[1:]
        l_col_limits = limits[1:]
        l_col_fmtrs = fmtrs[1:]
        l_col_mfmtrs = mfmtrs[1:]
        b_row_labels = labels[:-1]
        b_row_limits = limits[:-1]
        b_row_fmtrs = fmtrs[:-1]
        b_row_mfmtrs = mfmtrs[:-1]
        for row in axes:
            set_share_axes(row, sharey=True)

    # Set axis limits, labels, and ticks
    set_labels(b_row, b_row_labels, 'xlabel', **text_kws)
    set_labels(l_col, l_col_labels, 'ylabel', **text_kws)
    fig.align_labels()
    set_limits(b_row, b_row_limits, 'x')
    set_limits(l_col, l_col_limits, 'y')
    for ax, fmtr, mfmtr in zip(l_col, l_col_fmtrs, l_col_mfmtrs):
        ax.yaxis.set_major_locator(fmtr) # better way to do this?
        ax.yaxis.set_minor_locator(mfmtr)
    for ax, fmtr, mfmtr in zip(b_row, b_row_fmtrs, b_row_mfmtrs):
        ax.xaxis.set_major_locator(fmtr)
        ax.xaxis.set_minor_locator(mfmtr)
    if tight:
        plt.tight_layout(rect=[0, 0, 1.025, 0.975])
    return fig, axes

    
def corner(
    X,
    env_params=None,
    samples=2000,
    pad=0.5,
    figsize=(6, 6),
    kind='scatter',
    diag_kind='hist',
    hist_height=0.7,
    units='mm-mrad',
    norm_labels=False,
    text=None,
    diag_kws={},
    env_kws={},
    text_kws={},
    **plt_kws
):
    """Plot the pairwise relationships between the beam phase space coordinates.
    
    Of course other routines exist such as `scatter_matrix` in Pandas or
    `pairplot` in Seaborn; however, I could not find an option to only plot
    a small sample of the particles in the scatter plots while keeping all
    the particles for the histogram calculation.
        
    Parameters
    ----------
    X : ndarray, shape (nparts, 4)
        The transverse beam coordinate array.
    env_params : array-like, shape (8,)
        The beam envelope parameters.
    samples : int
        The number of randomly sampled points to use in the scatter plots.
    pad : float
        Padding for the axis ranges: umax_new = (1 + pad) * umax_old.
    figsize : tuple or int
        Size of the figure (x_size, y_size). If an int is provided, the number
        is used as the size for both dimensions.
    kind : {'scatter', 'hist', 'kde'}
        The kind of plot to make on the off-diagonal subplots. Note: the 'kde'
        and 'hist' options are not implemented yet.
    diag_kind : {'hist', 'kde', 'none'}
        The kind of plot to make on the diagonal subplots. If 'none', these are
        excluded and a 3x3 grid is produced. Note: the 'kde' option is not
        implemented yet.
    hist_height : float in range [0, 1]
        Reduce the height of the histograms on the diagonal, which normally
        extend to the top of the plotting window, by this factor.
    units : str or bool
        Whether to display units on the axis labels. Options are 'mm-mrad' or
        'm-rad'. No units are displayed if None.
    norm_labels : bool
        Whether to add an 'n' subscript to axis labels. Ex: 'x' --> 'x_n'.
    text : str
        If provided, annotate the figure with `text`.
    {plt, diag, env, text}_kws : dict
        Key word arguments. They are passed to the following functions:
        * plt_kws  : `plt.scatter`. This doesn't need to be passed as a dict.
                     For example, `s=10` can be added to the function call to
                     change the marker size.
        * diag_kws : `plt.hist`. More options will be added in the future like
                     kde.
        * env_kws  : `plt.plot`. For plotting the envelope ellipses.
        * text_kws : `plt.annotate`. For any text displayed on the figure.
        
    Returns
    -------
    numpy.ndarray
        The array of subplots.
    """
    # Configure key word arguments
    plt_kws = merge_dicts(plt_kws_default, plt_kws)
    if diag_kws_default['color'] != plt_kws['c']:
        diag_kws_default['color'] = plt_kws['c']
    diag_kws = merge_dicts(diag_kws_default, diag_kws)
    env_kws = merge_dicts(env_kws_default, env_kws)
    text_kws = merge_dicts(text_kws_default, text_kws)
    
    # Get data
    X_samp = rand_rows(X, samples) # sample of particles for scatter plots
    X_env = None
    if env_params is not None:
        env = ea.Envelope(params=env_params)
        X_env = env.generate_dist(50, 'on_ellipse')
    
    # Plot
    plt_diag = diag_kind != 'none'
    limits = (1 + pad) * get_u_up_max(X) # axis limits
    fig, axes = setup_corner(limits, figsize, norm_labels, units,
                             plt_diag=plt_diag, fontsize='medium')
    
    if diag_kind == 'none':
        hdata, vdata = X_samp[:, :-1], X_samp[:, 1:]
        if X_env is not None:
            hdata_env, vdata_env = X_env[:, :-1], X_env[:, 1:]
        for i in range(3):
            for j in range(i + 1):
                ax = axes[i, j]
                ax.scatter(hdata[:, j], vdata[:, i], **plt_kws)
                if X_env is not None:
                    ax.plot(hdata_env[:, j], vdata_env[:, i], **env_kws)
    else:
        for i in range(4):
            for j in range(i + 1):
                ax = axes[i, j]
                if i == j:
                    ax.hist(X[:, i], **diag_kws)
                else:
                    ax.scatter(X_samp[:, j], X_samp[:, i], **plt_kws)
                    if env_params is not None:
                        ax.plot(X_env[:, j], X_env[:, i], **env_kws)

        # Change height of histograms
        top_left_ax = axes[0, 0]
        new_ylim = (1.0 / hist_height) * top_left_ax.get_ylim()[1]
        top_left_ax.set_ylim(0, new_ylim)

    if text is not None:
        text_pos = (0.35, 0) if plt_diag else (0.35, 0.5)
        axes[1, 2].annotate(text, xy=text_pos, xycoords='axes fraction',
                            **text_kws)
    return axes
    
    
def corner_env(
    params,
    fill=False,
    pad=0.5,
    space=None,
    figsize=(5, 5),
    cmap=None,
    units='mm-mrad',
    norm_labels=False,
    legend_kws=None,
    fill_kws={},
    **plt_kws
):
    """Plot the 6 transverse phase space ellipses of the beam.
    
    Inputs
    ------
    params : array-like
        Envelope parameters [a, b, a', b', e, f, e', f']. If a list of array of
        these vectors is provided, each row will be plotted.
    pad : float
        Fraction of umax and upmax to pad the axis ranges with. The edge of the 
        plot will be at umax * (1 + pad).
    space : float
        Size of the space between subplots. If None, the `tight_layout`
        optimizer is used to determined the spacing.
    figsize : tuple or int
        Size of the figure (x_size, y_size). If an int is provided, the number
        is used as the size for both dimensions.
    ec, fc : str
        Color of the ellipse boundary (ec) and interior (fc). If either are
        None,
    cmap : Matplotlib colormap
        If plotting a sequence of envelopes, this sets the color cycle. If
        None, it will use the default color cycle. If we provide something
        like plt.cm.viridis, the different envelopes will be perceptually
        uniform from blue to yellow.
    units : str or bool
        Whether to display units on the axis labels. Options are 'mm-mrad' or
        'm-rad'. No units are displayed if None.
    norm_labels : boolean
        If True, add '_n' to the axis labels. E.g. 'x' -> 'x_n'.
    legend_kws : dict
        Key word args for the legend.
        
    Returns
    -------
    axes : Matplotlib axes object
        3x3 array of Axes objects.
    """    
    # Get ellipse boundary data
    if type(params) not in [list, tuple, np.ndarray]:
        params = [params]
    coords = ea.get_ellipse_coords(params)
    
    # Set up figure
    limits = (1 + pad) * get_u_up_max_global(coords)
    fig, axes = setup_corner(limits, figsize, norm_labels, units, space,
                             plt_diag=False)
    if len(params) > 1 and cmap is not None:
        colors = [cmap(i) for i in np.linspace(0, 1, len(params))]
        for ax in axes.flat:
            ax.set_prop_cycle(cycler('color', colors))
            
    # Plot data
    color = None if len(params) > 1 else 'k'
    plt_kws = merge_dicts(dict(lw=None, color=color, zorder=10), plt_kws)
    fill_kws = merge_dicts(dict(lw=1, fc='lightsteelblue', ec='k', zorder=10),
                           fill_kws)
    for X in coords:
        X_horiz, X_vert = X[:, :-1], X[:, 1:]
        for i in range(3):
            for j in range(i + 1):
                ax = axes[i, j]
                if fill:
                    ax.fill(X_horiz[:, j], X_vert[:, i], **fill_kws)
                else:
                    ax.plot(X_horiz[:, j], X_vert[:, i], **plt_kws)
    # Add legend (this messes up formatting if tight_layout is used)
    if legend_kws is not None:
        axes[1, 1].legend(**legend_kws)
    return axes
    
    
def fft(x, y, grid=True, legend=False, figname=None):
    """Compute and plot the FFT of two signals x and y on the same figure.
    
    Uses scipy.fft package. Particularly useful for plotting the horizontal
    tunes of a particle from its turn-by-turn x and y coordinates.

    Let N be the number of samples, M=N/2, x(t)=signal as function of time, 
    and w(f) be the FFT of x. Then w[0] is zero frequency component, w[1:M] 
    are positive frequency components, and w[M:N] are negative frequency 
    components.
    
    Inputs
    ------
    x{y} : ndarray, shape (n,):
        Contains the x{y} coordinate at n time steps.
    grid : bool
        Whether to put grid on plot.
        
    Returns
    -------
    ax: Matplotlib.axes object
    """
    N = len(x)
    M = N // 2
    f = (1/N) * np.arange(M)
    xf = (1/M) * abs(scipy.fft.fft(x)[:M])
    yf = (1/M) * abs(scipy.fft.fft(y)[:M])

    fig, ax = plt.subplots()
    ax.set_xlabel('Tune')
    ax.set_ylabel('Amplitude')
    ax.plot(f[1:], xf[1:], label=r'$\nu_x$')
    ax.plot(f[1:], yf[1:], label=r'$\nu_y$')
    ax.set_xticks(np.arange(0, 0.55, 0.05))
    ax.grid(grid)
    if legend:
        ax.legend(loc='upper right', framealpha=1)
    return ax


def scatter_color_by_density(ax, x, y):
    """Scatter plot with color weighted by density.
    
    Taken from StackOverflow answer by Joe Kington: 'https://stackoverflow.com/questions/20105364/how-can-i-make-a-scatter-plot-colored-by-density-in-matplotlib'
    """
    # Calculate the point density
    xy = np.vstack([x, y])
    z = scipy.stats.gaussian_kde(xy)(xy)

    # Sort the points by density, so that the densest points are plotted last
    idx = z.argsort()
    x, y, z = x[idx], y[idx], z[idx]

    ax.scatter(x, y, c=z, s=4, ec='')
    return ax


def vector(ax, v, origin=(0, 0), c='k', lw=None):
    """Plot 2D vector `v` as an arrow."""
    prop = dict(arrowstyle='->,head_width=0.4,head_length=0.8',
                shrinkA=0, shrinkB=0, fc=c, ec=c, lw=lw)
    ax.annotate('', xy=(origin[0]+v[0], origin[1]+v[1]),
                xytext=origin, arrowprops=prop)
    return ax


def eigvec_trajectory(ax, M, i='x', j='y', colors=('r','b'), s=None, lw=2,
                      alpha=0.3):
    """Plot the trajectory of the eigenvectors of the transfer matrix.
    
    Parameters
    ----------
    ax : matplotlib.pyplot.axes object
        The axis on which to plot.
    M : ndarray, shape (4, 4)
        The lattice transfer matrix.
    i{j} : str or int
        The component of the eigenvector to plot on the x{y} axis. Can be
        either {'x', 'xp', 'y', 'yp'} or {0, 1, 2, 3}.
    colors : two-element list or tuple
        The colors to use for eigenvector 1 and 2.
    s : float
        The marker size for the scatter plot.
    lw : float
        The lineweight for the arrrows.
    alpha : float
        The alpha parameter for the scatter plot.
        
    Returns
    -------
    ax : matplotlib.pyplot.axes object
        The modified axis.
    """
    def track(x, M, nturns=1):
        X = [x]
        for i in range(nturns):
            X.append(np.matmul(M, X[i]))
        return np.array(X)
    
    if type(i) is str:
        str_to_int = {'x':0, 'xp':1, 'y':2, 'yp':3}
        i, j = str_to_int[i], str_to_int[j]
        
    eigvals, eigvecs = np.linalg.eig(M)
    v1, _, v2, _ = eigvecs.T
    for v, color in zip((v1, v2), colors):
        X = track(v.real, M, nturns=20)
        ax.scatter(X[:, i], X[:, j], s=s, c=color, alpha=alpha, marker='o')
        vector(ax, v[[i, j]].real, c=color, lw=lw)
    return ax
