import os

import numpy as np
import pandas as pd
import sympy
import IPython
from numpy import linalg as la
from sympy import pprint, Matrix
from IPython.display import display, HTML


def is_number(x):
    return type(x) in [float, int, np.float64, np.int]


# File processing
def list_files(path, join=True):
    files = []
    for file in os.listdir(path):
        file_path = os.path.join(path, file)
        if os.path.isfile(file_path) and not file.startswith('.'):
            if join:
                files.append(file_path)
            else:
                files.append(file)
    return files
    
    
def is_empty(path):
    return len(list_files(path)) > 0
    
    
def delete_files_not_folders(path):
    for root, folders, files in os.walk(path):
        for file in files:
            os.remove(os.path.join(root, file))
                
                
def file_exists(file):
    return os.path.isfile(file)
    
    
# Lists and dicts
def merge_lists(x, y):
    """Returns [x[0], y[0], ..., x[-1], y[-1]]"""
    return [x for pair in zip(a, b) for x in pair]
    
    
def split_list(items, token):
    """Split `items` into sublists, excluding `token`.

    Example:
    >>> items = ['cat', 'dog', 'x', 'tree', 'bark']
    >>> split_list(items, 'x')
    [['cat', 'dog'], ['tree', 'bark']]
    """
    indices = [i for i, item in enumerate(items) if item == token]
    sublists = []
    if items[0] != token:
        sublists.append(items[:indices[0]])
    for lo, hi in zip(indices[:-1], indices[1:]):
        sublists.append(items[lo + 1:hi])
    if items[-1] != token:
        sublists.append(items[indices[-1] + 1:])
    return sublists
    
    
def repeat_list(items, n=2):
    new = []
    for item in items:
        for _ in range(n):
            new.append(item)
    return new
    

def sort_list_using_another_list(list1, list2):
    return [item0 for item0, item1
            in sorted(zip(list1, list2), key=lambda item: item[1])]
    
    
def merge_dicts(*dictionaries):
    """Given any number of dictionaries, shallow copy and merge into a new dict.
    
    Precedence goes to key value pairs in latter dictionaries. This function
    will work in Python 2 or 3. Note that in version 3.5 or greater we can just
    call `z = {**x, **y}`, and in 3.9 we can call `z = x | y`, to merge two
    dictionaries (with the values of y replacing those in x).
    
    Example usage:
        >> w = dict(a=1, b=2, c=3)
        >> x = dict(e=4, f=5, c=6)
        >> y = dict(g=7, h=8, f=7)
        >> merge_dicts(w, x, y)
        >> {'a': 1, 'b': 2, 'c': 6, 'e': 4, 'f': 7, 'g': 7, 'h': 8}
    
    Copied from the accepted answer here: 'https://stackoverflow.com/questions//38987/how-do-i-merge-two-dictionaries-in-a-single-expression-in-python-taking-union-o'.
    """
    result = {}
    for dictionary in dictionaries:
        result.update(dictionary)
    return result
    
    
# Display
def tprint(string, indent=4):
    """Print with indent."""
    print(indent*' ' + str(string))
             
             
def show(V, name=None, dec=3):
    """Pretty print matrix with rounded entries."""
    if name:
        print(name, '=')
    pprint(Matrix(np.round(V, dec)))
    
    
def play(anim, center=True):
    """Display matplotlib animation using HTML."""
    html_string = anim.to_jshtml()
    if center:
        html_string = ''.join(['<center>', html_string, '<center>'])
    display(HTML(html_string))
    
    
# Arrays
def apply(M, X):
    """Apply M to each row of X."""
    return np.apply_along_axis(lambda x: np.matmul(M, x), 1, X)


def normalize(X):
    """Normalize all rows of X to unit length."""
    return np.apply_along_axis(lambda x: x/la.norm(x), 1, X)


def symmetrize(M):
    """Return a symmetrized version of M.
    
    M : A square upper or lower triangular matrix.
    """
    return M + M.T - np.diag(M.diagonal())
    
    
def rand_rows(X, n):
    """Return n random elements of X."""
    Xsamp = np.copy(X)
    if n < len(X):
        idx = np.random.choice(Xsamp.shape[0], n, replace=False)
        Xsamp = Xsamp[idx]
    return Xsamp


def mat2vec(Sigma):
    """Return vector of independent elements in 4x4 symmetric matrix Sigma."""
    return Sigma[np.triu_indices(4)]
                  
                  
def vec2mat(moment_vec):
    """Inverse of `mat2vec`."""
    Sigma = np.zeros((4, 4))
    indices = np.triu_indices(4)
    for moment, (i, j) in zip(moment_vec, zip(*indices)):
        Sigma[i, j] = moment
    return symmetrize(Sigma)
    
    
# The following three functions are from Tony Yu's blog post: https://tonysyu.github.io/ragged-arrays.html#.YKVwQy9h3OR
    
def stack_ragged(array_list, axis=0):
    """Stacks list of arrays along first axis.
    
    Example: (25, 4) + (75, 4) -> (100, 4). It also returns the indices at
    which to split the stacked array to regain the original list of arrays.
    """
    lengths = [np.shape(array)[axis] for array in array_list]
    idx = np.cumsum(lengths[:-1])
    stacked = np.concatenate(array_list, axis=axis)
    return stacked, idx
    

def save_stacked_array(filename, array_list, axis=0):
    """Save list of ragged arrays as single stacked array. The index from
    `stack_ragged` is also saved."""
    stacked, idx = stack_ragged(array_list, axis=axis)
    np.savez(filename, stacked_array=stacked, stacked_index=idx)
    
    
def load_stacked_arrays(filename, axis=0):
    """"Load stacked ragged array from .npz file as list of arrays."""
    npz_file = np.load(filename)
    idx = npz_file['stacked_index']
    stacked = npz_file['stacked_array']
    return np.split(stacked, idx, axis=axis)
    

# Math
def cov2corr(cov_mat):
    """Form correlation matrix from covariance matrix."""
    D = np.sqrt(np.diag(cov_mat.diagonal()))
    Dinv = la.inv(D)
    corr_mat = la.multi_dot([Dinv, cov_mat, Dinv])
    return corr_mat
    
    
def rotation_matrix(angle):
    """2D rotation matrix (cw)."""
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, s], [-s, c]])
