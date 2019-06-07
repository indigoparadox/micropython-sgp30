import time
from micropython import const

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/alexmrqt/Adafruit_CircuitPython_SGP30.git"

_SGP30_DEFAULT_I2C_ADDR = const(0x58)
_SGP30_FEATURESET = const(0x0020)

_SGP30_CRC8_POLYNOMIAL = const(0x31)
_SGP30_CRC8_INIT = const(0xFF)
_SGP30_WORD_LEN = const(2)


class SGP30:
    """
    A driver for the SGP30 gas sensor.

    :param i2c: The `I2C` object to use. This is the only required parameter.
    :param int address: (optional) The I2C address of the device.
    """

    def __init__(self, i2c, address=_SGP30_DEFAULT_I2C_ADDR):
        """Initialize the sensor, get the serial # and verify that we found a proper SGP30"""
        self._i2c = i2c
        self._addr = address

        # get unique serial, its 48 bits so we store in an array
        self.serial = self._i2c_read_words_from_cmd([0x36, 0x82], 0.01, 3)
        # get featuerset
        featureset = self._i2c_read_words_from_cmd([0x20, 0x2f], 0.01, 1)
        if featureset[0] != _SGP30_FEATURESET:
            raise RuntimeError('SGP30 Not detected')
        self.initalise_indoor_air_quality()

    @property
    def tvoc(self):
        """Total Volatile Organic Compound in parts per billion."""
        return self.iaq_measure()[1]

    @property
    def baseline_tvoc(self):
        """Total Volatile Organic Compound baseline value"""
        return self.get_iaq_baseline()[1]

    @property
    def co2_equivalent(self):
        """Carbon Dioxide Equivalent in parts per million"""
        return self.iaq_measure()[0]

    @property
    def baseline_co2_equivilant(self):
        """Carbon Dioxide Equivalent baseline value"""
        return self.get_iaq_baseline()[0]

    def initalise_indoor_air_quality(self):
        """Initialize the IAQ algorithm"""
        # name, command, signals, delay
        self._run_profile(["initalise_indoor_air_quality", [0x20, 0x03], 0, 0.01])

    def iaq_measure(self):
        """Measure the CO2eq and TVOC"""
        # name, command, signals, delay
        return self._run_profile(["iaq_measure", [0x20, 0x08], 2, 0.05])

    @property
    def iaq_baseline(self):
        """Get the IAQ algorithm baseline for CO2eq and TVOC"""
        # name, command, signals, delay
        return self._run_profile(["iaq_get_baseline", [0x20, 0x15], 2, 0.01])

    @iaq_baseline.setter
    def iaq_baseline(self, co2_equivalent, total_volatile_organic_compounds):
        """Set the previously recorded IAQ algorithm baseline for CO2eq and TVOC"""
        if co2_equivalent == 0 and total_volatile_organic_compounds == 0:
            raise RuntimeError('Invalid baseline')
        buffer = []
        for value in [total_volatile_organic_compounds, co2_equivalent]:
            arr = [value >> 8, value & 0xFF]
            arr.append(generate_crc(arr))
            buffer += arr
        self._run_profile(["iaq_set_baseline", [0x20, 0x1e] + buffer, 0, 0.01])

    # Low level command functions
    def _run_profile(self, profile):
        """Run an SGP 'profile' which is a named command set"""
        _, command, signals, delay = profile
        return self._i2c_read_words_from_cmd(command, delay, signals)

    def _i2c_read_words_from_cmd(self, command, delay, reply_size):
        """Run an SGP command query, get a reply and CRC results if necessary"""
        self._i2c.writeto(self._addr, bytes(command))
        time.sleep(delay)
        if not reply_size:
            return None
        crc_result = bytearray(reply_size * (_SGP30_WORD_LEN +1))
        self._i2c.readfrom_into(self._addr, crc_result)
        result = []
        for i in range(reply_size):
            word = [crc_result[3*i], crc_result[3*i+1]]
            crc = crc_result[3*i+2]
            if generate_crc(word) != crc:
                raise RuntimeError('CRC Error')
            result.append(word[0] << 8 | word[1])
        return result


def generate_crc(data):
    """8-bit CRC algorithm for checking data"""
    crc = _SGP30_CRC8_INIT
    # calculates 8-Bit checksum with given polynomial
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ _SGP30_CRC8_POLYNOMIAL
            else:
                crc <<= 1
    return crc & 0xFF
