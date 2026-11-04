import logging
import re

import numpy as np
from numpy.polynomial import Chebyshev

logger = logging.getLogger(__name__)

"""
Opens the file 'filename', checks its validity, formats it into an 2D numpy array and returns this array.
"""

def get_data(filename):
    return format_data(validate_data(load_file(filename)))


"""
Opens the file 'filename' and returns an array containing the lines of the file.
"""
def load_file(filename):
    if filename == "":
        raise Exception("Error in function 'load_file': filename is empty")
    with open(filename, "r") as file:
        lines = []
        for line in file.readlines():
            lines.append(line)
        return lines


"""
Validates the entries of the array 'data', removes the invalid lines and returns the valid entries.
The entries must contain two decimal numbers separated by either ' ', '\t' or ',' to be counted as valid.
"""
def validate_data(data):
    if data == []:
        raise Exception("Error in function 'validate_data': data array is empty")

    valid = [
        line
        for line in data
        if re.match(
            r"^\s*\d+\.?\d*(?:[eE][+\-]?\d+)?(?:\s*|\,*|\t*)-?\d+\.?\d*(?:[eE][+\-]?\d+)?\s*(\n?)", line
        )
        is not None
    ]
    if len(valid) == 0:
        raise Exception("Error in function 'validate_data': array has no valid entry")
    return valid


"""
Formats the entries of the array 'data' by splitting it into two decimal numbers, creates a 2D numpy array, 
fills the array with the decimal numbers and returns the array.
"""
def format_data(data):
    formatted_data = np.array([[0.0, 0.0] for _ in range(len(data))])
    for i in range(len(data)):
        formatted_data[i] = re.split(r'[\s*|\,*|\t*]', data[i].strip())
    return formatted_data


"""
Fits the array 'data' with a Chebyshev polynom of degree 'degree' and returns the fitted function.
"""
def fit_data(data, degree=5):
    try:
        return Chebyshev.fit(data[:, 0], data[:, 1], degree)
    except Exception as e:
        logger.warning("Error in 'fit_data()': %s", e)


"""
Interpolates the function 'fit' by evaluating it either at the entries of xdata or at every delta_x, from x_min to x_max
and returns the interpolated data in a 2D numpy array.
"""
def interpolate_data(fit, xdata, x_min=None, x_max=None, delta_x=None):
    if xdata is not None or (x_min is not None and x_max is not None and delta_x is not None):
        if xdata is not None:
            interpolated_data = np.array([[0.0, 0.0] for _ in range(len(xdata))])
            for i in range(len(xdata)):
                interpolated_data[i] = [xdata[i], fit(xdata[i])]
        else:
            length = int(((x_max - x_min) / delta_x) + 1)
            interpolated_data = np.array([[0.0, 0.0] for _ in range(length)])
            for i in range(length):
                x = x_min + i * delta_x
                interpolated_data[i] = [x, fit(x)]
        return interpolated_data
    else:
        raise Exception("Error in 'interpolate_data()': xdata oder x_min, x_max, delta_x muss übergeben werden")

def save_data(path, data, x_legend="", y_legends=[]):
    # Check if saving was aborted
    if(path == ""):
        return
    
    x_array = data[0]
    y_arrays = data[1:]
    with open(path, "w") as file:
        legend = x_legend
        if (legend != ""):
            legend += "\t"
        for y_legend in y_legends:
                legend += f"{y_legend}\t"
        legend = legend.strip()
        legend +="\n"
        file.write(legend)

        for i in range(max([max([len(col) for col in data]), len(x_array)])):
            if (len(x_array) > i):
               file.write(f"{x_array[i]}")
            for y_array in y_arrays:
                if (len(y_array) > i):
                    file.write(f"\t{y_array[i]}")
                else:
                    file.write(f"\t")
            file.write(f"\n")

def save_params(path, para_dict):
    # Check if saving was aborted
    if(path == ""):
        return
    
    with open(path, "w") as file:
        for key in para_dict:
            file.write(f"{key}\t{para_dict[key]}\n")
