from labscript_utils.unitconversions.UnitConversionBase import UnitConversion


class ELL14_Unit_Converter(UnitConversion):
    base_unit = 'counts'
    derived_units = ['deg']

    # slope is degrees per encoder count.
    # ELL14 moves 360 degrees per 143,360 encoder counts.
    default_slope = 360. / 143360.
    default_offset = 0.0

    def __init__(self, calibration_parameters=None):
        # These parameters are loaded from a globals.h5 type file
        # automatically.
        if calibration_parameters is None:
            calibration_parameters = {}
        self.parameters = calibration_parameters

        # Position_deg = slope * Position_counts + offset.
        # slope is in degrees per encoder count.
        self.parameters.setdefault('slope', self.default_slope)
        # offset is in degrees.
        self.parameters.setdefault('offset', self.default_offset)

        UnitConversion.__init__(self, self.parameters)

    def deg_to_base(self, position_deg):
        # Convert to range 0 to +360 degrees (including 0 but not +360).
        position_deg = position_deg % 360.

        # Now convert to encoder counts.
        slope = self.parameters['slope']
        offset = self.parameters['offset']
        position_counts = (position_deg - offset) / slope

        return position_counts

    def deg_from_base(self, position_counts):
        slope = self.parameters['slope']
        offset = self.parameters['offset']
        position_deg = slope * position_counts + offset
        return position_deg
