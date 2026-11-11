"""Portfolio calculations.

Plain Python on purpose: the data is small (thousands of rows) and the standard library
does not change under us. Ledger numbers are converted to floats here because market
prices are floats anyway; results are rounded only when displayed.
"""
