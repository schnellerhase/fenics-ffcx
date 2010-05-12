"""This script runs a benchmark study on the form files found in the
current directory. It relies on the regression test script for
timings."""

__author__ = "Anders Logg"
__date__ = "2010-05-11"
__copyright__ = "Copyright (C) 2010 " + __author__
__license__  = "GNU GPL version 3 or any later version"

import os, glob
from utils import print_table

# Test options
test_options = ["-r tensor", "-r tensor -O", "-r quadrature", "-r quadrature -O"]

# Get list of test cases
test_cases = [f.split(".")[0] for f in glob.glob("*.ufl")]

# Sort test cases by prefix and polynomial degree (demonstrating some Python skill here...)
forms = list(set([f.split("_")[0] for f in test_cases]))
degrees = [(f, sorted([int(g.split("_")[1]) for g in test_cases if "%s_" % f in g])) for f in forms]

# Iterate over options
os.chdir("../test/regression")
results = {}
for (j, test_option) in enumerate(test_options):

    # Run benchmark
    os.system("python test.py --bench %s" % test_option)

    # Collect results
    for (i, test_case) in enumerate(test_cases):
        output = open("output/%s.out" % test_case).read()
        lines = [line for line in output.split("\n") if "bench" in line]
        if not len(lines) == 1:
            raise RuntimeError, "Unable to extract benchmark data for test case %s" % test_case
        timing = float(lines[0].split(":")[-1])
        results[(i, j)] = (test_case, test_option, timing)

# Print results
print_table(results, "FFC bench")
