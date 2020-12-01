from labscript_utils.unitconversions.UnitConversionBase import UnitConversion


class FrequencyConverter(UnitConversion):
    base_unit = 'Hz'
    # Putting Hz as a derived unit as well lets us take advantage of
    # UnitConverion's built in prefix conversions. The only downside is that Hz
    # will appear as an option twice in the blacs dropdown menu, once as the
    # base unit and once as the derived unit.
    derived_units = ['Hz']

    def __init__(self, params=None):
        if params is None:
            params = {}
        if 'magnitudes' not in params:
            params['magnitudes'] = ['k', 'M', 'G']
        super().__init__(params)

    def Hz_from_base(self, base):
        return base

    def Hz_to_base(self, Hz):
        return Hz
