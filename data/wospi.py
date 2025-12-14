# 2025-08-10: converted to python3 syntax and manual changes
#
# originally python2 binary
#   Compiled at: 2019-11-27 08:35:35
import os
import sys
import time
import datetime
import subprocess
import serial
import struct
import urllib.request
import urllib.parse
import urllib.error
import socket
from dateutil.relativedelta import relativedelta
from pathlib import Path

PROGRAMVERSION = '20250825-RPi'
PROGRAMNAME = 'WOSPi_' + PROGRAMVERSION
BRAGLINE = ' Data proudly brought to you by <a href="https://www.annoyingdesigns.com/wospi/" target="_blank" class="url">WOSPi</a> and a very dedicated <a href="https://www.raspberrypi.org" target="_blank" class="url">Raspberry Pi</a>.\n'
COMMISSIONDATE = '01.01.1970'
BEAGLEBONE = False
WXRX_MUX = 'uart1_rxd'
WXTX_MUX = 'uart1_txd'
WXMUX_MODE = 0
WXRECEIVE_ENABLE = 32
USRLED = '/sys/class/leds/beaglebone::usr3/brightness'
WXBAUDRATE = 19200
WXBYTESIZE = serial.EIGHTBITS
WXPARITY = serial.PARITY_NONE
WXSTOPBITS = serial.STOPBITS_ONE
WXXONOFF = False
WXTIMEOUT = 3
WXDELAY = 0.2
beaufortText = {
   0: 'Calm',
   1: 'Light air',
   2: 'Light breeze',
   3: 'Gentle breeze',
   4: 'Moderate breeze',
   5: 'Fresh breeze',
   6: 'Strong breeze',
   7: 'Near gale',
   8: 'Gale',
   9: 'Strong gale',
   10: 'Storm',
   11: 'Violent storm',
   12: 'Hurricane'
   }

DEBUG = False
from config import *

wx = None
wxDict = {}
wxMinMax = {}
lastUpdateTime = datetime.date(1970, 1, 1)
lastWxYearMonth = '1970-01'
uptime = ''
MONTHNAMES = [
 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
 'September', 'October', 'November', 'December']
PRESENTMONTH = ''
L1 = ''
L2 = ''
HL = ''


class WxError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def blinkLED(value=0, duration=0):
    """Activate/deactivate BeagleBone USRLED, then wait duration. BeagleBone only."""
    if BEAGLEBONE == False:
        return
    l = open(USRLED, 'w')
    l.write(str(value))
    l.close()
    time.sleep(duration)
    l = open(USRLED, 'w')
    l.write(str(0))
    l.close()


def blinkOnce():
    """Blink BeagleBone USRLED once."""
    blinkLED(0, 0)
    blinkLED(1, 1)


def FtoC(f):
    """Convert degrees Fahrenheit to degrees Celsius."""
    return round((f - 32) * 5 / 9, 1)


def CtoF(c):
    """Convert degrees Celsius to degrees Fahrenheit."""
    return round(c * 1.8 + 32, 1)


def mmToIn(mm):
    """Convert mm to inches, keep two decimal places."""
    return round(mm * 0.03937, 2)


def inToMm(i):
    """Convert inches to mm."""
    return round(i * 25.4, 1)


def dumpDict():
    """Dump all contents of the global wxData and wxMinMax dictionaries to stdout, for debug purposes."""
    global wxDict
    global wxMinMax
    for i in wxDict:
        print(i + ' = ' + str(wxDict[i]))

    for i in wxMinMax:
        print(i + ' = ' + str(wxMinMax[i]))


def debugWrite(filename, s):
    """Writes string s to specified filename (in the TMPPATH folder)."""
    filename = TMPPATH + filename
    f = open(filename, 'w')
    f.write(tStamp() + '\n\n')
    f.write(s + '\n\n')
    f.close()


def tStamp():
    """Returns timestamp string (LOCAL TIME)."""
    return datetime.datetime.now().ctime() + ' LT: '


def wxWrite(s, termChar='\n'):
    """Write s to wx, terminate string with termChar, then DELAY execution."""
    if wx is not None:
        if isinstance(s, str):
            message = (s + termChar).encode('ascii')
        elif isinstance(s, bytes):
            message = s
        else:
            raise TypeError(f"wxWrite() expects str or bytes, got {type(s).__name__}")

        wx.write(message)
        if isinstance(s, str) and s == 'VER':
            time.sleep(WXDELAY * 3)
        else:
            time.sleep(WXDELAY)

    return


def wxRead(as_text=True, encoding='ascii'):
    """Read all available data from wx. Return str or bytes based on as_text flag."""
    global wx

    if wx is None:
        raise WxError("wx serial connection is not initialized")

    if wx.in_waiting == 0:
        return '' if as_text else b''

    raw = wx.read(wx.in_waiting)

    if as_text:
        try:
            return raw.decode(encoding, errors='replace')  # avoid crashing
        except UnicodeDecodeError as e:
            print(f"{tStamp()} Decode error: {e}")
            return ''  # or re-raise/log
    else:
        return raw


def openWxComm():
    """Open UART for communication with the Davis console."""
    global wx, MAXATTEMPTS

    if BEAGLEBONE == True:
        open('/sys/kernel/debug/omap_mux/' + WXRX_MUX, 'wb').write('%X' % (WXRECEIVE_ENABLE + WXMUX_MODE))
        open('/sys/kernel/debug/omap_mux/' + WXTX_MUX, 'wb').write('%X' % WXMUX_MODE)

    try:
        wx = serial.Serial(WXPORT, WXBAUDRATE, WXBYTESIZE, WXPARITY, WXSTOPBITS, WXTIMEOUT, WXXONOFF)
    except serial.SerialException as e:
        raise WxError(f"Failed to open serial port {WXPORT}: {e}")

    time.sleep(WXDELAY)
    if wx == None or not wx.is_open:
        return
    else:
        wakeUpSuccess = False
        if MAXATTEMPTS < 0 or MAXATTEMPTS > 100:
            MAXATTEMPTS = 3
        for attemptNo in range(1, MAXATTEMPTS + 1):
            print(tStamp() + 'Console wakeup call, attempt no. %d of 3.' % attemptNo)
            wxWrite('')
            time.sleep(WXDELAY)

            if wx.in_waiting == 2:
                dummyBuffer = wxRead()
                print(tStamp() + 'Console is awake after %d wakeup call(s).' % attemptNo)
                wakeUpSuccess = True
                wxWrite('TEST')
                time.sleep(WXDELAY)
                dummyBuffer = wxRead()
                break
            else:
                print(tStamp() + 'Console NOT responding to wakeup call.')
                dummyBuffer = wxRead()
                time.sleep(1.5)

        if wakeUpSuccess == True:
            print(tStamp() + 'The console is responding.')
        else:
            print(tStamp() + 'Unable to wake up the console. Check connections.')
            wx.close()
            wx = None
        return wx


def insertTestData(negative=0):
    """Populate global dictionaries wxDict and wxMinMax with test data."""
    global wxDict
    global wxMinMax
    wxDict = {}
    wxMinMax = {}
    wxDict['VER'] = 'JAN 01 1942'
    wxDict['NVER'] = 'NVER TEST 1.42'
    wxDict['BARDATA'] = 'BARDATA TEST 42'
    wxDict['RXCHECK'] = '4242 42 0 42 42'
    wxDict['STATIONMODEL'] = 'TEST Stationtype=42'
    wxDict['PROGRAMVERSION'] = PROGRAMVERSION
    if negative != 0:
        wxDict['DEWPOINT_F'] = -42
        wxDict['DEWPOINT_C'] = FtoC(-42)
    else:
        wxDict['DEWPOINT_F'] = 42
        wxDict['DEWPOINT_C'] = FtoC(42)
    wxDict['BAROTREND'] = 0
    wxDict['BAROTRENDTEXT'] = 'Barometric TEST-trend.'
    wxDict['BAROMETER_INHG'] = 29.92
    wxDict['BAROMETER_HPA'] = 1013
    wxDict['INTEMP_F'] = 42
    wxDict['INTEMP_C'] = FtoC(42)
    if negative != 0:
        wxDict['OUTTEMP_F'] = -42
        wxDict['OUTTEMP_C'] = FtoC(-42)
    else:
        wxDict['OUTTEMP_F'] = 42
        wxDict['OUTTEMP_C'] = FtoC(42)
    wxDict['INHUM_P'] = 42
    wxDict['OUTHUM_P'] = 42
    wxDict['AVGWIND10_MPH'] = 42
    wxDict['AVGWIND10_KTS'] = round(36.496992, 1)
    wxDict['AVGWIND10_MSEC'] = round(18.77568, 1)
    wxDict['AVGWIND2_MPH'] = 42
    wxDict['AVGWIND2_KTS'] = round(36.496992, 1)
    wxDict['AVGWIND2_MSEC'] = round(18.77568, 1)
    wxDict['GUST10_MPH'] = 42
    wxDict['GUST10_KTS'] = round(36.496992, 1)
    wxDict['GUST10_MSEC'] = round(18.77568, 1)
    wxDict['GUST10DIR'] = 1
    wxDict['WC_F'] = 42
    wxDict['WC_C'] = FtoC(42)
    wxDict['THSW_F'] = 42
    wxDict['THSW_C'] = FtoC(42)
    wxDict['HINDEX_F'] = 42
    wxDict['HINDEX_C'] = FtoC(42)
    wxDict['RAINFALL15_MM'] = 42
    wxDict['RAINFALL60_MM'] = 42
    wxDict['RAINFALL24H_MM'] = 42
    wxDict['STORMSTART'] = '01.01.2042'
    wxDict['TIMESTAMP'] = 'Timestamp here'
    wxDict['TIMESTAMP_APRS'] = 'APRS timestamp here'
    wxDict['TIMESTAMP_PC'] = 'PC timestamp here'
    wxDict['TIMESTAMP_WX'] = 'WX timestamp here'
    wxDict['COMMISSIONDATE'] = '01.01.1970'
    wxDict['ET_DAY_MM'] = 42
    wxDict['ET_MONTH_MM'] = 42
    wxDict['ET_YEAR_MM'] = 42
    wxDict['WIND_MPH'] = 42
    wxDict['WIND_KTS'] = round(36.496992, 1)
    wxDict['WIND_MSEC'] = round(18.77568, 1)
    wxDict['WIND_CARDINAL'] = 'N'
    wxDict['GUST_CARDINAL'] = 'N'
    wxDict['FREEZE'] = False
    wxDict['CONDENSATION'] = False
    wxDict['WINDDIR'] = '042'
    wxDict['RAINRATE_MMHR'] = 42
    wxDict['STORMRAIN_MM'] = 42
    wxDict['DAYRAIN_MM'] = 42
    wxDict['MONTHRAIN_MM'] = 420
    wxDict['YEARRAIN_MM'] = 4200
    wxDict['UVINDEX'] = 4.2
    wxDict['SOLAR_W'] = 420
    wxDict['BATTERYSTATUS'] = 0
    wxDict['VOLTAGE'] = 4.2
    wxDict['FCICON'] = 2
    wxDict['FCTEXT'] = 'TEST-FORECAST'
    wxDict['SUNRISE_LT'] = '00:42'
    wxDict['SUNSET_LT'] = '00:43'
    wxDict['CRC_PAD'] = 42
    wxDict['CRC_CALC'] = 42
    wxMinMax['DEWPOINT_MIN_TIME'] = '10:42'
    wxMinMax['UVINDEX_MAX_TIME'] = '10:42'
    wxMinMax['WINDSPEED_MONTH_MAX_MSEC'] = 42
    wxMinMax['OUTTEMP_MAX_TIME'] = '10:42'
    wxMinMax['UVINDEX_MAX_MONTH'] = 42
    wxMinMax['BAROMETER_MONTH_MAX_INHG'] = 42
    wxMinMax['SOLAR_MAX_TIME'] = '10:42'
    wxMinMax['WINDSPEED_MONTH_MAX_MPH'] = 42
    wxMinMax['OUTHUM_YEAR_MIN'] = 42
    wxMinMax['RAINRATE_MAX_YEAR_MMHR'] = 42
    wxMinMax['SOLAR_MAX_DAY'] = 42
    wxMinMax['BAROMETER_DAY_MAX_INHG'] = 42
    wxMinMax['WINDSPEED_YEAR_MAX_MSEC'] = 42
    wxMinMax['UVINDEX_MAX_DAY'] = 42
    wxMinMax['DEWPOINT_MAX_TIME'] = '10:42'
    wxMinMax['BAROMETER_YEAR_MAX_INHG'] = 42
    wxMinMax['BAROMETER_MONTH_MIN_HPA'] = 42
    wxMinMax['OUTHUM_YEAR_MAX'] = 42
    wxMinMax['DEWPOINT_MONTH_MIN_C'] = 42
    wxMinMax['BAROMETER_DAY_MAX_HPA'] = 42
    wxMinMax['DEWPOINT_YEAR_MIN_C'] = 42
    wxMinMax['DEWPOINT_MONTH_MIN_F'] = 42
    wxMinMax['DEWPOINT_MONTH_MAX_C'] = 42
    wxMinMax['OUTTEMP_DAY_MIN_F'] = 42
    wxMinMax['BAROMETER_YEAR_MIN_HPA'] = 42
    wxMinMax['OUTTEMP_DAY_MIN_C'] = 42
    wxMinMax['WINDSPEED_DAY_MAX_MSEC'] = 42
    wxMinMax['OUTTEMP_YEAR_MIN_C'] = 42
    wxMinMax['SOLAR_MAX_MONTH'] = 42
    wxMinMax['RAINRATE_MAX_HOUR_MMHR'] = 42
    wxMinMax['OUTTEMP_YEAR_MIN_F'] = 42
    wxMinMax['OUTTEMP_DAY_MAX_F'] = 42
    wxMinMax['WINDSPEED_MAX_TIME'] = '10:42'
    wxMinMax['OUTTEMP_DAY_MAX_C'] = 42
    wxMinMax['BAROMETER_DAY_MIN_INHG'] = 42
    wxMinMax['WINDSPEED_YEAR_MAX_MPH'] = 42
    wxMinMax['WINDSPEED_YEAR_MAX_KTS'] = 42
    wxMinMax['BAROMETER_MONTH_MAX_HPA'] = 42
    wxMinMax['DEWPOINT_YEAR_MIN_F'] = 42
    wxMinMax['DEWPOINT_MONTH_MAX_F'] = 42
    wxMinMax['OUTTEMP_MONTH_MIN_F'] = 42
    wxMinMax['OUTTEMP_YEAR_MAX_C'] = 42
    wxMinMax['OUTTEMP_YEAR_MAX_F'] = 42
    wxMinMax['OUTTEMP_MONTH_MIN_C'] = 42
    wxMinMax['BAROMETER_DAY_MIN_HPA'] = 42
    wxMinMax['RAINRATE_MAX_MONTH_MMHR'] = 42
    wxMinMax['RAINRATE_MAX_TIME'] = '10:42'
    wxMinMax['WINDSPEED_DAY_MAX_MPH'] = 42
    wxMinMax['SOLAR_MAX_YEAR'] = 42
    wxMinMax['OUTHUM_DAY_MIN'] = 42
    wxMinMax['OUTHUM_DAY_MAX'] = 42
    wxMinMax['OUTTEMP_MONTH_MAX_F'] = 42
    wxMinMax['DEWPOINT_DAY_MAX_F'] = 42
    wxMinMax['OUTHUM_MONTH_MIN'] = 42
    wxMinMax['OUTTEMP_MONTH_MAX_C'] = 42
    wxMinMax['UVINDEX_MAX_YEAR'] = 42
    wxMinMax['OUTHUM_MAX_TIME'] = '10:42'
    wxMinMax['OUTHUM_MONTH_MAX'] = 42
    wxMinMax['BAROMETER_MONTH_MIN_INHG'] = 42
    wxMinMax['OUTHUM_MIN_TIME'] = '10:42'
    wxMinMax['RAINRATE_MAX_DAY_MMHR'] = 42
    wxMinMax['DEWPOINT_YEAR_MAX_F'] = 42
    wxMinMax['CRC-CALC'] = 0
    wxMinMax['BAROMETER_YEAR_MIN_INHG'] = 42
    wxMinMax['BAROMETER_MAX_TIME'] = '10:42'
    wxMinMax['DEWPOINT_DAY_MAX_C'] = 42
    wxMinMax['OUTTEMP_MIN_TIME'] = '10:42'
    wxMinMax['TIMESTAMP'] = '2042-03-01 10:42:42.000000'
    wxMinMax['DEWPOINT_YEAR_MAX_C'] = 42
    wxMinMax['DEWPOINT_DAY_MIN_F'] = 42
    wxMinMax['BAROMETER_MIN_TIME'] = '10:42'
    wxMinMax['WINDSPEED_DAY_MAX_KTS'] = 42
    wxMinMax['DEWPOINT_DAY_MIN_C'] = 42
    wxMinMax['WINDSPEED_MONTH_MAX_KTS'] = 42
    wxMinMax['BAROMETER_YEAR_MAX_HPA'] = 42
    wxMinMax['SOCTEMP'] = 42


# -------------------------------------------------------
# added functions
# -------------------------------------------------------

def print_hex_bytes(data, length=20):
    return ' '.join(f'{b:02X}' for b in data[:length])


# Store last successful update time
last_wc_update = None


def should_update_weathercloud():
    """ check if update to weathercloud is possible """
    global last_wc_update
    if last_wc_update is None:
        return True
    elapsed = datetime.datetime.now() - last_wc_update
    return elapsed.total_seconds() > WC_UPDATE_INTERVAL_MIN * 60


def record_wc_update():
    """ save last WC update time """
    global last_wc_update
    last_wc_update = datetime.datetime.now()


def read_response_after_ok(strip_ok=True) -> str:
    """Read from wx after sending a command, and return everything after 'OK'."""
    time.sleep(WXDELAY)
    raw = wx.read(wx.in_waiting)
    decoded = raw.decode('ascii', errors='replace').replace('\n\r', ' ', 5)

    ok_index = decoded.find('OK')
    if ok_index >= 0:
        return decoded[ok_index + 3:].strip() if strip_ok else decoded
    return decoded.strip()  # fallback: return all


def wake_console(max_attempts=3, timeout=1.2):
    """
    Try to wake the Davis console by sending LF and expecting LF CR in response.
    Retries up to max_attempts. Returns True if wakeup successful.
    """
    for attempt in range(1, max_attempts + 1):
        wx.reset_input_buffer()
        wxWrite('\n')

        start_time = time.time()
        buffer = b""

        while time.time() - start_time < timeout:
            if wx.in_waiting:
                buffer += wx.read(wx.in_waiting)
                # Look for LF CR pairs
                if b"\x0A\x0D" in buffer:
                    # Collapse multiple pairs if they exist
                    pairs = buffer.count(b"\x0A\x0D")
                    if DEBUG:
                        print(tStamp() + f"Wakeup successful (attempt {attempt}). "
                                         f"Got: {print_hex_bytes(buffer)} "
                                         f"(pairs={pairs})")
                    return True
            time.sleep(0.01)

        if DEBUG:
            print(tStamp() + f"Wakeup attempt {attempt} failed (got {print_hex_bytes(buffer)})")

    return False


def request_packet(cmd, expected_size, timeout=2, retries=1, check_header=None):
    """
    Requests a packet from the console, checks CRC, and returns the payload.
    Payload starts with 'LOO' (if check_header is provided) and includes the CRC.
    Returns (payload, raw) or (None, None) if timeout, bad header, or CRC error.
    """

    for attempt in range(retries + 1):
        wx.reset_input_buffer()
        wx.reset_output_buffer()
        time.sleep(WXDELAY)

        # Proper wake-up sequence
        if not wake_console():
            print(tStamp() + "Console did not wake up.")
            return None, None

        # Request the packet
        wxWrite(cmd)
        time.sleep(WXDELAY)

        # Wait for enough bytes
        start_time = time.time()
        while wx.in_waiting < expected_size:
            if time.time() - start_time > timeout:
                print(tStamp() + f"Timeout: only {wx.in_waiting} bytes for {cmd}.")
                break
            time.sleep(0.01)

        if wx.in_waiting < expected_size:
            if attempt < retries:
                print(tStamp() + f"Retrying {cmd} (attempt {attempt+1}/{retries})...")
                continue
            return None, None

        raw = wx.read(expected_size)

        # --- Guard against short packets ---
        if len(raw) < expected_size:
            print(tStamp() + f"{cmd} - Short packet: {len(raw)} < {expected_size}")
            return None, None

        # --- Tolerate stray LF/CR before ACK ---
        while raw and raw[0] in (0x0A, 0x0D):
            if DEBUG:
                print(tStamp() + f"Skipping stray LF/CR before ACK: {raw[0]:02X}")
            raw = raw[1:]

        if not raw:
            print(tStamp() + f"{cmd} - No data left after stripping LF/CR.")
            return None, None

        # Verify ACK
        if raw[0] != 0x06:
            if 0x20 <= raw[0] <= 0x7E:  # ASCII instead of ACK
                print(tStamp() + f"{cmd} - Got ASCII instead of ACK ({raw[0]:02X}), discarding and retrying...")
                continue  # retry without failing
            else:
                print(tStamp() + f"{cmd} - Expected ACK 0x06, got {raw[0]:02X}. "
                                 f"Full raw: {print_hex_bytes(raw)}")
            return None, None


        payload = raw[1:]

        if DEBUG:
            r_str = str(print_hex_bytes(raw))
            print(tStamp() + f"DEBUG: ===== {cmd:<8} => raw =========: {r_str:<20}")

        # Check header if required
        if check_header is not None:
            if payload[:len(check_header)] != check_header:
                print(tStamp() + f"{cmd} - Invalid packet start: {payload[:len(check_header)]}")
                return None, None

        # CRC check
        crc_received = int.from_bytes(payload[-2:], 'big')
        crc_calculated = CRC(payload[:-2])
        if crc_calculated != crc_received:
            print(tStamp() + f"{cmd} - CRC error: received {crc_received}, calculated {crc_calculated}")
            return None, None

        print(tStamp() + f"{cmd} packet CRC is verified.")
        return payload, raw

    return None, None



def read_ascii_block(cmd, timeout=2, terminator=b"\n\r"):
    """
    Send an ASCII command (e.g. 'BARDATA') and read the full response
    until the last line ends with <LF><CR>.
    Returns the full decoded string, or None on timeout.
    """
    wxWrite(cmd)
    time.sleep(WXDELAY)

    resp = b''
    start_time = time.time()

    while True:
        if wx.in_waiting:
            resp += wx.read(wx.in_waiting)

            # Heuristic: last line of BARDATA always ends with '\n\r'
            if resp.endswith(terminator):
                break

        if time.time() - start_time > timeout:
            print(tStamp() + f"{cmd} - Timeout while waiting for response.")
            return None

        time.sleep(0.01)

    return resp.decode('ascii', errors='ignore')


# -------------------------------------------------------
# added functions
# -------------------------------------------------------


def readWxData():
    """Populate global dictionary wxDict, returns size of received LOOP packet (should be 100). Also updates PRESENTMONTH."""
    global L1
    global PRESENTMONTH
    global SOLARCF
    global UVCF
    global lastWxYearMonth
    global wx

    if wx == None:
        return

    i = j = 0
    s = t = ''
    wxDict['PROGRAMVERSION'] = PROGRAMVERSION
    wxWrite('VER')
    wxDict['VER'] = read_response_after_ok()

    # Retry if empty
    if not wxDict['VER']:
        wxWrite('VER')
        wxDict['VER'] = read_response_after_ok()

    wxWrite('NVER')
    wxDict['NVER'] = read_response_after_ok()

    payload, raw = request_packet('GETTIME', 9, timeout=2, check_header=None)
    if not payload or len(raw) < 9:
        raise WxError("GETTIME packet too short")

    # payload includes the whole 9 bytes (e.g. data + CRC at the end)
    if CRC(payload[:-2]) != int.from_bytes(payload[-2:], 'big'):
        raise WxError('Invalid CRC in GETTIME packet')

    t = raw  # for unpack_from offsets

    time_secs = str(struct.unpack_from('B', t, 1)[0])
    time_mins = str(struct.unpack_from('B', t, 2)[0])
    time_hrs = str(struct.unpack_from('B', t, 3)[0])
    time_day = str(struct.unpack_from('B', t, 4)[0])
    theMonth = struct.unpack_from('B', t, 5)[0]
    time_month = str(theMonth)
    time_year = str(struct.unpack_from('B', t, 6)[0] + 1900)

    # Format output
    t_str = (
        padText(time_day, 2) + '.' + padText(time_month, 2) + '.' +
        padText(time_year, 4) + ' @ ' + padText(time_hrs, 2) + ':' +
        padText(time_mins, 2) + ':' + padText(time_secs, 2)
    )

    print(tStamp() + 'Current timestamp in weather station is ' + t_str + '.')
    wxDict['TIMESTAMP'] = (
        padText(time_day, 2) + '.' + padText(time_month, 2) + '.' +
        padText(time_year, 4) + ' ' + padText(time_hrs, 2) + ':' +
        padText(time_mins, 2) + ':' + padText(time_secs, 2)
    )

    lastWxYearMonth = padText(time_year, 4) + '-' + padText(time_month, 2)
    PRESENTMONTH = MONTHNAMES[theMonth - 1]
    wxDict['TIMESTAMP_WX'] = 'Received on ' + t_str + ' local time'

    aprsTime = PRESENTMONTH[0:3]
    aprsTime += ' ' + padText(time_day, 2) + ' ' + time_year + ' '
    aprsTime += padText(time_hrs, 2) + ':' + padText(time_mins, 2)
    wxDict['TIMESTAMP_APRS'] = aprsTime

    # read bardata
    wxDict['BARDATA'] = ''
    s = read_ascii_block('BARDATA')
    if s:
        wxDict['BARDATA'] = s

        i = s.find('DEW POINT') + 10
        if i > 9:  # found it
            sub = s[i:]
            j = sub.find('\n\r')
            dew_f = float(sub[:j])
            wxDict['DEWPOINT_F'] = dew_f
            wxDict['DEWPOINT_C'] = round(FtoC(dew_f), 1)

    ###
    #wxWrite('BARDATA')
    #i = wx.in_waiting
    #if i > 0:
    #    s = wx.read(i).decode('ascii')
    #    wxDict['BARDATA'] = s
    #    i = s.find('DEW POINT') + 10
    #    s = s[i:]
    #    i = s.find('\n\r')
    #    s = s[:i]
    #    wxDict['DEWPOINT_F'] = float(s)
    #    j = round(FtoC(float(s)), 1)
    #    wxDict['DEWPOINT_C'] = j

    wxDict['CRC-CALC'] = 1

    payload, q = request_packet('LOOP 1', 100, check_header=b'LOO')

    if not payload:
        print(tStamp() + 'Failed to get valid LOOP packet, aborting.')
        return 1  # or handle error gracefully

    if len(q) < 100:  # expected_size is 100 for LOOP 1
        print(tStamp() + f"Error: LOOP1 raw packet too short ({len(q)} bytes, expected {expected_size}).")
        return None

    crc_calc = wxDict['CRC-CALC']
    loop1Status = 1

    if payload:
        # CRC check (bytes 1..100)
        crc_calc = CRC(q[1:101])
        wxDict['CRC-CALC'] = crc_calc
        wxDict['CRC_PAD'] = struct.unpack_from('<H', q, 95)[0]  # little-endian CRC from packet

        if crc_calc == 0:
            lastUpdateTime = wxDict['TIMESTAMP_PC'] = datetime.datetime.now()
            L1 = q[1:]  # Store the payload without the preamble byte
            writeDump(TMPPATH + 'LOOP1', L1)
            loop1Status = 0
        else:
            print(tStamp() + 'Invalid LOOP packet CRC.')
            return 1

        s = q[3:]  # Skip preamble + packet type + unused byte

        j = wxDict['BAROTREND'] = struct.unpack_from('B', s, 1)[0]
        t = 'Barometric pressure is '
        if j == 0:
            t += 'steady.'
        elif j == 20:
            t += 'rising slowly.'
        elif j == 60:
            t += 'rising rapidly.'
        elif j == 196:
            t += 'falling rapidly.'
        elif j == 236:
            t += 'falling slowly.'
        else:
            t = 'Barometric trend is not available.\n                                 Requires 3 hours of data.'
        wxDict['BAROTRENDTEXT'] = t
        j = wxDict['BAROMETER_INHG'] = round(struct.unpack_from('H', s, 5)[0] / 1000.0, 2)
        wxDict['BAROMETER_HPA'] = round(j * 33.8639, 1)
        j = wxDict['INTEMP_F'] = struct.unpack_from('H', s, 7)[0] / 10.0
        wxDict['INTEMP_C'] = FtoC(j)
        wxDict['INHUM_P'] = struct.unpack_from('B', s, 9)[0]
        j = wxDict['OUTTEMP_F'] = struct.unpack_from('H', s, 10)[0] / 10.0
        wxDict['OUTTEMP_C'] = FtoC(j)
        j = wxDict['AVGWIND10_MPH'] = struct.unpack_from('B', s, 13)[0]
        if j > 300:
            j = 0
            wxDict['AVGWIND10_MPH'] = 0
        wxDict['AVGWIND10_KTS'] = round(j * 0.868976, 1)
        wxDict['AVGWIND10_MSEC'] = round(j * 0.44704, 1)
        wxDict['AVGWIND10_BF'] = getBeaufortIndex(wxDict['AVGWIND10_KTS'])
        j = wxDict['WIND_MPH'] = struct.unpack_from('B', s, 12)[0]
        wxDict['WIND_KTS'] = round(j * 0.868976, 1)
        wxDict['WIND_MSEC'] = round(j * 0.44704, 1)
        wxDict['WIND_BF'] = getBeaufortIndex(wxDict['WIND_KTS'])
        t = str(struct.unpack_from('H', s, 14)[0])
        if t == '0':
            t = '000'
        if len(t) < 3:
            t = '0' + t
        if len(t) < 3:
            t = '0' + t
        wxDict['WINDDIR'] = t
        wxDict['WIND_CARDINAL'] = getCardinalDirection(int(t))
        wxDict['OUTHUM_P'] = struct.unpack_from('B', s, 31)[0]
        if wxDict['OUTHUM_P'] > 100:
            print(tStamp() + 'Value out of range (manually verify console value) : OUTHUM_P = %d.' % wxDict['OUTHUM_P'])
            wxDict['OUTHUM_P'] = -1
            wxDict['DATAERROR'] = True
        if INCHES == False:
            wxDict['RAINRATE_MMHR'] = round(struct.unpack_from('H', s, 39)[0] * 0.2, 1)
            wxDict['DAYRAIN_MM'] = round(struct.unpack_from('H', s, 48)[0] * 0.2, 1)
            wxDict['STORMRAIN_MM'] = round(struct.unpack_from('H', s, 44)[0] * 0.2, 1)
            wxDict['MONTHRAIN_MM'] = round(struct.unpack_from('H', s, 50)[0] * 0.2, 1)
            wxDict['YEARRAIN_MM'] = round(struct.unpack_from('H', s, 52)[0] * 0.2, 1)
        else:
            wxDict['RAINRATE_MMHR'] = round(struct.unpack_from('H', s, 39)[0] * 0.01 * 25.4, 1)
            wxDict['DAYRAIN_MM'] = round(struct.unpack_from('H', s, 48)[0] * 0.01 * 25.4, 1)
            wxDict['STORMRAIN_MM'] = round(struct.unpack_from('H', s, 44)[0] * 0.01 * 25.4, 1)
            wxDict['MONTHRAIN_MM'] = round(struct.unpack_from('H', s, 50)[0] * 0.01 * 25.4, 1)
            wxDict['YEARRAIN_MM'] = round(struct.unpack_from('H', s, 52)[0] * 0.01 * 25.4, 1)
        t = struct.unpack_from('H', s, 46)[0]
        if t == 65535:
            wxDict['STORMSTART'] = '01.01.1970'
        else:
            storm_year = t % 128
            t = t - storm_year
            storm_day = t % 4096
            storm_day = storm_day >> 7
            t = t - storm_day
            t = t >> 12
            storm_month = t
            t = ''
            if storm_day < 10:
                t = '0'
            t += str(storm_day) + '.'
            if storm_month < 10:
                t += '0'
            t += str(storm_month) + '.'
            t += str(2000 + storm_year)
            wxDict['STORMSTART'] = t
        t = 0
        if INCHES == False:
            t = wxDict['ET_DAY_MM'] = round(struct.unpack_from('H', s, 54)[0] * 0.0254, 1)
            wxDict['ET_MONTH_MM'] = round(t + struct.unpack_from('H', s, 56)[0] * 0.254, 1)
            wxDict['ET_YEAR_MM'] = round(t + struct.unpack_from('H', s, 58)[0] * 0.254, 1)
        else:
            t = wxDict['ET_DAY_MM'] = round(struct.unpack_from('H', s, 54)[0] * 0.001 * 25.4, 1)
            wxDict['ET_MONTH_MM'] = round(t + struct.unpack_from('H', s, 56)[0] * 0.01 * 25.4, 1)
            wxDict['ET_YEAR_MM'] = round(t + struct.unpack_from('H', s, 58)[0] * 0.01 * 25.4, 1)
        if UVCF != 0 and (UVCF < 50 or UVCF > 150):
            UVCF = 100
        wxDict['UVINDEX'] = struct.unpack_from('B', s, 41)[0] / 10.0 * (UVCF / 100)
        if wxDict['UVINDEX'] > 16:
            print(tStamp() + 'Value out of range (UVCF too high?) : UVINDEX = %d.' % wxDict['UVINDEX'])
            wxDict['UVINDEX'] = -1
            wxDict['DATAERROR'] = True
        if SOLARCF != 0 and (SOLARCF < 50 or SOLARCF > 100):
            SOLARCF = 100
        wxDict['SOLAR_W'] = int(struct.unpack_from('H', s, 42)[0] * (SOLARCF / 100))
        if wxDict['SOLAR_W'] > 1800:
            print(tStamp() + 'Value out of range (SOLARCF too high?) : SOLAR_W = %d.' % wxDict['SOLAR_W'])
            wxDict['SOLAR_W'] = -1
            wxDict['DATAERROR'] = True
        wxDict['FCICON'] = struct.unpack_from('B', s, 87)[0]
        wxDict['VOLTAGE'] = round(struct.unpack_from('H', s, 85)[0] * 300 / 512 / 100, 2)
        wxDict['BATTERYSTATUS'] = struct.unpack_from('B', s, 84)[0]
        wxDict['FCRULE'] = j = struct.unpack_from('B', s, 88)[0]
        if j == 0:
            t = 'Mostly clear and cooler.'
        elif j == 1:
            t = 'Mostly clear with little temperature change.'
        elif j == 2:
            t = 'Mostly clear for 12 hours with little temperature change.'
        elif j == 3:
            t = 'Mostly clear for 12 to 24 hours and cooler.'
        elif j == 4:
            t = 'Mostly clear with little temperature change.'
        elif j == 5:
            t = 'Partly cloudy and cooler.'
        elif j == 6:
            t = 'Partly cloudy with little temperature change.'
        elif j == 7:
            t = 'Partly cloudy with little temperature change.'
        elif j == 8:
            t = 'Mostly clear and warmer.'
        elif j == 9:
            t = 'Partly cloudy with little temperature change.'
        elif j == 10:
            t = 'Partly cloudy with little temperature change.'
        elif j == 11:
            t = 'Mostly clear with little temperature change.'
        elif j == 12:
            t = 'Increasing clouds and warmer. Precipitation possible within 24 to 48 hours.'
        elif j == 13:
            t = 'Partly cloudy with little temperature change.'
        elif j == 14:
            t = 'Mostly clear with little temperature change.'
        elif j == 15:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 24 hours.'
        elif j == 16:
            t = 'Mostly clear with little temperature change.'
        elif j == 17:
            t = 'Partly cloudy with little temperature change.'
        elif j == 18:
            t = 'Mostly clear with little temperature change.'
        elif j == 19:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 12 hours.'
        elif j == 20:
            t = 'Mostly clear with little temperature change.'
        elif j == 21:
            t = 'Partly cloudy with little temperature change.'
        elif j == 22:
            t = 'Mostly clear with little temperature change.'
        elif j == 23:
            t = 'Increasing clouds and warmer. Precipitation possible within 24 hours.'
        elif j == 24:
            t = 'Mostly clear and warmer. Increasing winds.'
        elif j == 25:
            t = 'Partly cloudy with little temperature change.'
        elif j == 26:
            t = 'Mostly clear with little temperature change.'
        elif j == 27:
            t = 'Increasing clouds and warmer. Precipitation possible within 12 hours. Increasing winds.'
        elif j == 28:
            t = 'Mostly clear and warmer. Increasing winds.'
        elif j == 29:
            t = 'Increasing clouds and warmer.'
        elif j == 30:
            t = 'Partly cloudy with little temperature change.'
        elif j == 31:
            t = 'Mostly clear with little temperature change.'
        elif j == 32:
            t = 'Increasing clouds and warmer. Precipitation possible within 12 hours. Increasing winds.'
        elif j == 33:
            t = 'Mostly clear and warmer. Increasing winds.'
        elif j == 34:
            t = 'Increasing clouds and warmer.'
        elif j == 35:
            t = 'Partly cloudy with little temperature change.'
        elif j == 36:
            t = 'Mostly clear with little temperature change.'
        elif j == 37:
            t = 'Increasing clouds and warmer. Precipitation possible within 12 hours. Increasing winds.'
        elif j == 38:
            t = 'Partly cloudy with little temperature change.'
        elif j == 39:
            t = 'Mostly clear with little temperature change.'
        elif j == 40:
            t = 'Mostly clear and warmer. Precipitation possible within 48 hours.'
        elif j == 41:
            t = 'Mostly clear and warmer.'
        elif j == 42:
            t = 'Partly cloudy with little temperature change.'
        elif j == 43:
            t = 'Mostly clear with little temperature change.'
        elif j == 44:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 24 to 48 hours.'
        elif j == 45:
            t = 'Increasing clouds with little temperature change.'
        elif j == 46:
            t = 'Partly cloudy with little temperature change.'
        elif j == 47:
            t = 'Mostly clear with little temperature change.'
        elif j == 48:
            t = 'Increasing clouds and warmer. Precipitation possible within 12 to 24 hours.'
        elif j == 49:
            t = 'Partly cloudy with little temperature change.'
        elif j == 50:
            t = 'Mostly clear with little temperature change.'
        elif j == 51:
            t = 'Increasing clouds and warmer. Precipitation possible within 12 to 24 hours. Windy.'
        elif j == 52:
            t = 'Partly cloudy with little temperature change.'
        elif j == 53:
            t = 'Mostly clear with little temperature change.'
        elif j == 54:
            t = 'Increasing clouds and warmer. Precipitation possible within 12 to 24 hours. Windy.'
        elif j == 55:
            t = 'Partly cloudy with little temperature change.'
        elif j == 56:
            t = 'Mostly clear with little temperature change.'
        elif j == 57:
            t = 'Increasing clouds and warmer. Precipitation possible within 6 to 12 hours.'
        elif j == 58:
            t = 'Partly cloudy with little temperature change.'
        elif j == 59:
            t = 'Mostly clear with little temperature change.'
        elif j == 60:
            t = 'Increasing clouds and warmer. Precipitation possible within 6 to 12 hours. Windy.'
        elif j == 61:
            t = 'Partly cloudy with little temperature change.'
        elif j == 62:
            t = 'Mostly clear with little temperature change.'
        elif j == 63:
            t = 'Increasing clouds and warmer. Precipitation possible within 12 to 24 hours. Windy.'
        elif j == 64:
            t = 'Partly cloudy with little temperature change.'
        elif j == 65:
            t = 'Mostly clear with little temperature change.'
        elif j == 66:
            t = 'Increasing clouds and warmer. Precipitation possible within 12 hours.'
        elif j == 67:
            t = 'Partly cloudy with little temperature change.'
        elif j == 68:
            t = 'Mostly clear with little temperature change.'
        elif j == 69:
            t = 'Increasing clouds and warmer. Precipitation likley.'
        elif j == 70:
            t = 'Clearing and cooler. Precipitation ending within 6 hours.'
        elif j == 71:
            t = 'Partly cloudy with little temperature change.'
        elif j == 72:
            t = 'Clearing and cooler. Precipitation ending within 6 hours.'
        elif j == 73:
            t = 'Mostly clear with little temperature change.'
        elif j == 74:
            t = 'Clearing and cooler. Precipitation ending within 6 hours.'
        elif j == 75:
            t = 'Partly cloudy and cooler.'
        elif j == 76:
            t = 'Partly cloudy with little temperature change.'
        elif j == 77:
            t = 'Mostly clear and cooler.'
        elif j == 78:
            t = 'Clearing and cooler. Precipitation ending within 6 hours.'
        elif j == 79:
            t = 'Mostly clear with little temperature change.'
        elif j == 80:
            t = 'Clearing and cooler. Precipitation ending within 6 hours.'
        elif j == 81:
            t = 'Mostly clear and cooler.'
        elif j == 82:
            t = 'Partly cloudy with little temperature change.'
        elif j == 83:
            t = 'Mostly clear with little temperature change.'
        elif j == 84:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 24 hours.'
        elif j == 85:
            t = 'Mostly cloudy and cooler. Precipitation continuing.'
        elif j == 86:
            t = 'Partly cloudy with little temperature change.'
        elif j == 87:
            t = 'Mostly clear with little temperature change.'
        elif j == 88:
            t = 'Mostly cloudy and cooler. Precipitation likely.'
        elif j == 89:
            t = 'Mostly cloudy with little temperature change. Precipitation continuing.'
        elif j == 90:
            t = 'Mostly cloudy with little temperature change. Precipitation likely.'
        elif j == 91:
            t = 'Partly cloudy with little temperature change.'
        elif j == 92:
            t = 'Mostly clear with little temperature change.'
        elif j == 93:
            t = 'Increasing clouds and cooler. Precipitation possible and windy within 6 hours.'
        elif j == 94:
            t = 'Increasing clouds with little temperature change. Precipitation possible and windy within 6 hours.'
        elif j == 95:
            t = 'Mostly cloudy and cooler. Precipitation continuing. Increasing winds.'
        elif j == 96:
            t = 'Partly cloudy with little temperature change.'
        elif j == 97:
            t = 'Mostly clear with little temperature change.'
        elif j == 98:
            t = 'Mostly cloudy and cooler. Precipitation likely. Increasing winds.'
        elif j == 99:
            t = 'Mostly cloudy with little temperature change. Precipitation continuing. Increasing winds.'
        elif j == 100:
            t = 'Mostly cloudy with little temperature change. Precipitation likely. Increasing winds.'
        elif j == 101:
            t = 'Partly cloudy with little temperature change.'
        elif j == 102:
            t = 'Mostly clear with little temperature change.'
        elif j == 103:
            t = 'Increasing clouds and cooler. Precipitation possible within 12 to 24 hours possible wind shift to the W, NW, or N.'
        elif j == 104:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 12 to 24 hours possible wind shift to the W, NW, or N.'
        elif j == 105:
            t = 'Partly cloudy with little temperature change.'
        elif j == 106:
            t = 'Mostly clear with little temperature change.'
        elif j == 107:
            t = 'Increasing clouds and cooler. Precipitation possible within 6 hours possible wind shift to the W, NW, or N.'
        elif j == 108:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 6 hours possible wind shift to the W, NW, or N.'
        elif j == 109:
            t = 'Mostly cloudy and cooler. Precipitation ending within 12 hours possible wind shift to the W, NW, or N.'
        elif j == 110:
            t = 'Mostly cloudy and cooler. Possible wind shift to the W, NW, or N.'
        elif j == 111:
            t = 'Mostly cloudy with little temperature change. Precipitation ending within 12 hours possible wind shift to the W, NW, or N.'
        elif j == 112:
            t = 'Mostly cloudy with little temperature change. Possible wind shift to the W, NW, or N.'
        elif j == 113:
            t = 'Mostly cloudy and cooler. Precipitation ending within 12 hours possible wind shift to the W, NW, or N.'
        elif j == 114:
            t = 'Partly cloudy with little temperature change.'
        elif j == 115:
            t = 'Mostly clear with little temperature change.'
        elif j == 116:
            t = 'Mostly cloudy and cooler. Precipitation possible within 24 hours possible wind shift to the W, NW, or N.'
        elif j == 117:
            t = 'Mostly cloudy with little temperature change. Precipitation ending within 12 hours possible wind shift to the W, NW, or N.'
        elif j == 118:
            t = 'Mostly cloudy with little temperature change. Precipitation possible within 24 hours possible wind shift to the W, NW, or N.'
        elif j == 119:
            t = 'Clearing, cooler and windy. Precipitation ending within 6 hours.'
        elif j == 120:
            t = 'Clearing, cooler and windy.'
        elif j == 121:
            t = 'Mostly cloudy and cooler. Precipitation ending within 6 hours. Windy with possible wind shift to the W, NW, or N.'
        elif j == 122:
            t = 'Mostly cloudy and cooler. Windy with possible wind shift to the W, NW, or N.'
        elif j == 123:
            t = 'Clearing, cooler and windy.'
        elif j == 124:
            t = 'Partly cloudy with little temperature change.'
        elif j == 125:
            t = 'Mostly clear with little temperature change.'
        elif j == 126:
            t = 'Mostly cloudy with little temperature change. Precipitation possible within 12 hours. Windy.'
        elif j == 127:
            t = 'Partly cloudy with little temperature change.'
        elif j == 128:
            t = 'Mostly clear with little temperature change.'
        elif j == 129:
            t = 'Increasing clouds and cooler. Precipitation possible within 12 hours, possibly heavy at times. Windy.'
        elif j == 130:
            t = 'Mostly cloudy and cooler. Precipitation ending within 6 hours. Windy.'
        elif j == 131:
            t = 'Partly cloudy with little temperature change.'
        elif j == 132:
            t = 'Mostly clear with little temperature change.'
        elif j == 133:
            t = 'Mostly cloudy and cooler. Precipitation possible within 12 hours. Windy.'
        elif j == 134:
            t = 'Mostly cloudy and cooler. Precipitation ending in 12 to 24 hours.'
        elif j == 135:
            t = 'Mostly cloudy and cooler.'
        elif j == 136:
            t = 'Mostly cloudy and cooler. Precipitation continuing, possible heavy at times. Windy.'
        elif j == 137:
            t = 'Partly cloudy with little temperature change.'
        elif j == 138:
            t = 'Mostly clear with little temperature change.'
        elif j == 139:
            t = 'Mostly cloudy and cooler. Precipitation possible within 6 to 12 hours. Windy.'
        elif j == 140:
            t = 'Mostly cloudy with little temperature change. Precipitation continuing, possibly heavy at times. Windy.'
        elif j == 141:
            t = 'Partly cloudy with little temperature change.'
        elif j == 142:
            t = 'Mostly clear with little temperature change.'
        elif j == 143:
            t = 'Mostly cloudy with little temperature change. Precipitation possible within 6 to 12 hours. Windy.'
        elif j == 144:
            t = 'Partly cloudy with little temperature change.'
        elif j == 145:
            t = 'Mostly clear with little temperature change.'
        elif j == 146:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 12 hours, possibly heavy at times. Windy.'
        elif j == 147:
            t = 'Mostly cloudy and cooler. Windy.'
        elif j == 148:
            t = 'Mostly cloudy and cooler. Precipitation continuing, possibly heavy at times. Windy.'
        elif j == 149:
            t = 'Partly cloudy with little temperature change.'
        elif j == 150:
            t = 'Mostly clear with little temperature change.'
        elif j == 151:
            t = 'Mostly cloudy and cooler. Precipitation likely, possibly heavy at times. Windy.'
        elif j == 152:
            t = 'Mostly cloudy with little temperature change. Precipitation continuing, possibly heavy at times. Windy.'
        elif j == 153:
            t = 'Mostly cloudy with little temperature change. Precipitation likely, possibly heavy at times. Windy.'
        elif j == 154:
            t = 'Partly cloudy with little temperature change.'
        elif j == 155:
            t = 'Mostly clear with little temperature change.'
        elif j == 156:
            t = 'Increasing clouds and cooler. Precipitation possible within 6 hours. Windy.'
        elif j == 157:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 6 hours. Windy'
        elif j == 158:
            t = 'Increasing clouds and cooler. Precipitation continuing. Windy with possible wind shift to the W, NW, or N.'
        elif j == 159:
            t = 'Partly cloudy with little temperature change.'
        elif j == 160:
            t = 'Mostly clear with little temperature change.'
        elif j == 161:
            t = 'Mostly cloudy and cooler. Precipitation likely. Windy with possible wind shift to the W, NW, or N.'
        elif j == 162:
            t = 'Mostly cloudy with little temperature change. Precipitation continuing. Windy with possible wind shift to the W, NW, or N.'
        elif j == 163:
            t = 'Mostly cloudy with little temperature change. Precipitation likely. Windy with possible wind shift to the W, NW, or N.'
        elif j == 164:
            t = 'Increasing clouds and cooler. Precipitation possible within 6 hours. Windy with possible wind shift to the W, NW, or N.'
        elif j == 165:
            t = 'Partly cloudy with little temperature change.'
        elif j == 166:
            t = 'Mostly clear with little temperature change.'
        elif j == 167:
            t = 'Increasing clouds and cooler. Precipitation possible within 6 hours possible wind shift to the W, NW, or N.'
        elif j == 168:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 6 hours. Windy with possible wind shift to the W, NW, or N.'
        elif j == 169:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 6 hours possible wind shift to the W, NW, or N.'
        elif j == 170:
            t = 'Partly cloudy with little temperature change.'
        elif j == 171:
            t = 'Mostly clear with little temperature change.'
        elif j == 172:
            t = 'Increasing clouds and cooler. Precipitation possible within 6 hours. Windy with possible wind shift to the W, NW, or N.'
        elif j == 173:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 6 hours. Windy with possible wind shift to the W, NW, or N.'
        elif j == 174:
            t = 'Partly cloudy with little temperature change.'
        elif j == 175:
            t = 'Mostly clear with little temperature change.'
        elif j == 176:
            t = 'Increasing clouds and cooler. Precipitation possible within 12 to 24 hours. Windy with possible wind shift to the W, NW, or N.'
        elif j == 177:
            t = 'Increasing clouds with little temperature change. Precipitation possible within 12 to 24 hours. Windy with possible wind shift to the W, NW, or N.'
        elif j == 178:
            t = 'Mostly cloudy and cooler. Precipitation possibly heavy at times and ending within 12 hours. Windy with possible wind shift to the W, NW, or N.'
        elif j == 179:
            t = 'Partly cloudy with little temperature change.'
        elif j == 180:
            t = 'Mostly clear with little temperature change.'
        elif j == 181:
            t = 'Mostly cloudy and cooler. Precipitation possible within 6 to 12 hours, possibly heavy at times. Windy with possible wind shift to the W, NW, or N.'
        elif j == 182:
            t = 'Mostly cloudy with little temperature change. Precipitation ending within 12 hours. Windy with possible wind shift to the W, NW, or N.'
        elif j == 183:
            t = 'Mostly cloudy with little temperature change. Precipitation possible within 6 to 12 hours, possibly heavy at times. Windy with possible wind shift to the W, NW, or N.'
        elif j == 184:
            t = 'Mostly cloudy and cooler. Precipitation continuing.'
        elif j == 185:
            t = 'Partly cloudy with little temperature change.'
        elif j == 186:
            t = 'Mostly clear with little temperature change.'
        elif j == 187:
            t = 'Mostly cloudy and cooler. Precipitation likely. Windy with possible wind shift to the W, NW, or N.'
        elif j == 188:
            t = 'Mostly cloudy with little temperature change. Precipitation continuing.'
        elif j == 189:
            t = 'Mostly cloudy with little temperature change. Precipitation likely.'
        elif j == 190:
            t = 'Partly cloudy with little temperature change.'
        elif j == 191:
            t = 'Mostly clear with little temperature change.'
        elif j == 192:
            t = 'Mostly cloudy and cooler. Precipitation possible within 12 hours, possibly heavy at times. Windy.'
        elif j == 193:
            t = 'Forecast requires 3 hours of recent data.'
        elif j == 194:
            t = 'Mostly clear and cooler.'
        elif j == 195:
            t = 'Mostly clear and cooler.'
        elif j == 196:
            t = 'Mostly clear and cooler.'
        else:
            t = 'Forecast not available.'
        wxDict['FCTEXT'] = t
        wxDict['SUNRISE_LT'] = unpackTime(s, 89)
        wxDict['SUNSET_LT'] = unpackTime(s, 91)
        loop2Status = 0
        if LPS:
            loop2Status = readLoop2()

        wxWrite('RXCHECK')
        time.sleep(WXDELAY)
        rxcheckBytes = wx.in_waiting
        print(tStamp() + '%d bytes received in RXCHECK response.' % rxcheckBytes)
        if rxcheckBytes > 0:
            raw_rx = wx.read(rxcheckBytes).decode('ascii', errors='replace')

            # Normalize whitespace, strip out 'OK'
            rx_text = ' '.join(raw_rx.split()).replace('OK', '').strip()
            wxDict['RXCHECK'] = rx_text
            print(tStamp() + 'RXCHECK: ' + wxDict['RXCHECK'])
        else:
            wxDict['RXCHECK'] = 'Not available.'

        if DEBUG:
            print(tStamp() + f'DEBUG: loop2Status = {loop2Status}, loop1Status = {loop1Status}')

        result = 0
        if loop2Status == 0 and loop1Status == 0:
            result = 100
        elif loop1Status != 0:
            result = loop1Status
        else:
            result = loop2Status

        return result


def readLoop2():
    """Reads LOOP2 packet, inserting additional keys to wxDict."""
    global L2

    payload, q = request_packet('LPS 2 1', 100, retries=1, check_header=b'LOO')

    if not payload:
        print(tStamp() + 'Failed to get valid LOOP2 packet, aborting.')
        return 1  # or handle error gracefully

    if payload:
        L2 = payload  # Save the verified payload
        writeDump(TMPPATH + 'LOOP2', L2)

        s = payload[2:]
        j = struct.unpack_from('H', s, 16)[0] / 10.0
        if j > 300:
            j = 0
        wxDict['AVGWIND10_MPH'] = j
        wxDict['AVGWIND10_KTS'] = round(j * 0.868976, 1)
        wxDict['AVGWIND10_MSEC'] = round(j * 0.44704, 1)
        wxDict['AVGWIND10_BF'] = getBeaufortIndex(wxDict['AVGWIND10_KTS'])

        j = struct.unpack_from('H', s, 18)[0] / 10.0
        if j > 300:
            j = 0
        wxDict['AVGWIND2_MPH'] = j
        wxDict['AVGWIND2_KTS'] = round(j * 0.868976, 1)
        wxDict['AVGWIND2_MSEC'] = round(j * 0.44704, 1)
        wxDict['AVGWIND2_BF'] = getBeaufortIndex(wxDict['AVGWIND2_KTS'])
        j = wxDict['GUST10_MPH'] = struct.unpack_from('H', s, 20)[0]
        wxDict['GUST10_KTS'] = round(j * 0.868976, 1)
        wxDict['GUST10_MSEC'] = round(j * 0.44704, 1)
        wxDict['GUST10_BF'] = getBeaufortIndex(wxDict['GUST10_KTS'])
        t = str(struct.unpack_from('H', s, 22)[0])
        if t == '0':
            t = '000'
        if len(t) < 3:
            t = '0' + t
        if len(t) < 3:
            t = '0' + t
        wxDict['GUST10DIR'] = t
        wxDict['GUST_CARDINAL'] = getCardinalDirection(int(t))
        if INCHES == False:
            wxDict['RAINFALL15_MM'] = round(struct.unpack_from('H', s, 50)[0] * 0.2, 1)
            wxDict['RAINFALL60_MM'] = round(struct.unpack_from('H', s, 52)[0] * 0.2, 1)
            wxDict['RAINFALL24H_MM'] = round(struct.unpack_from('H', s, 56)[0] * 0.2, 1)
        else:
            wxDict['RAINFALL15_MM'] = inToMm(struct.unpack_from('H', s, 50)[0] * 0.01)
            wxDict['RAINFALL60_MM'] = inToMm(struct.unpack_from('H', s, 52)[0] * 0.01)
            wxDict['RAINFALL24H_MM'] = inToMm(struct.unpack_from('H', s, 56)[0] * 0.01)
        j = wxDict['WC_F'] = struct.unpack_from('H', s, 35)[0] / 1.0
        wxDict['WC_C'] = FtoC(j)
        if wxDict['WC_F'] > wxDict['OUTTEMP_F']:
            wxDict['WC_F'] = wxDict['OUTTEMP_F']
            wxDict['WC_C'] = wxDict['OUTTEMP_C']
        j = wxDict['DEWPOINT_F'] = struct.unpack_from('H', s, 28)[0] / 1.0
        wxDict['DEWPOINT_C'] = FtoC(j)
        if wxDict['DEWPOINT_C'] > 100:
            print(tStamp() + 'Value out of range (manually verify console value) : DEWPOINT_C = %d.' % wxDict['DEWPOINT_C'])
            wxDict['DEWPOINT_C'] = -1
            wxDict['DEWPOINT_F'] = -1
            wxDict['DATAERROR'] = True
        j = wxDict['THSW_F'] = struct.unpack_from('H', s, 37)[0] / 1.0
        wxDict['THSW_C'] = FtoC(j)
        j = wxDict['HINDEX_F'] = struct.unpack_from('H', s, 33)[0] / 1.0
        wxDict['HINDEX_C'] = FtoC(j)

    else:
        print(tStamp() + f'CRC error: received {crc_received}, calculated {crc_calculated}')
        return 1

    return 0


def CRC(inputData):
    """CCITT-16 CRC implementation, function should return 0."""
    crcTab = (0, 4129, 8258, 12387, 16516, 20645, 24774, 28903, 33032, 37161, 41290,
              45419, 49548, 53677, 57806, 61935, 4657, 528, 12915, 8786, 21173, 17044,
              29431, 25302, 37689, 33560, 45947, 41818, 54205, 50076, 62463, 58334,
              9314, 13379, 1056, 5121, 25830, 29895, 17572, 21637, 42346, 46411,
              34088, 38153, 58862, 62927, 50604, 54669, 13907, 9842, 5649, 1584,
              30423, 26358, 22165, 18100, 46939, 42874, 38681, 34616, 63455, 59390,
              55197, 51132, 18628, 22757, 26758, 30887, 2112, 6241, 10242, 14371,
              51660, 55789, 59790, 63919, 35144, 39273, 43274, 47403, 23285, 19156,
              31415, 27286, 6769, 2640, 14899, 10770, 56317, 52188, 64447, 60318,
              39801, 35672, 47931, 43802, 27814, 31879, 19684, 23749, 11298, 15363,
              3168, 7233, 60846, 64911, 52716, 56781, 44330, 48395, 36200, 40265,
              32407, 28342, 24277, 20212, 15891, 11826, 7761, 3696, 65439, 61374,
              57309, 53244, 48923, 44858, 40793, 36728, 37256, 33193, 45514, 41451,
              53516, 49453, 61774, 57711, 4224, 161, 12482, 8419, 20484, 16421, 28742,
              24679, 33721, 37784, 41979, 46042, 49981, 54044, 58239, 62302, 689,
              4752, 8947, 13010, 16949, 21012, 25207, 29270, 46570, 42443, 38312,
              34185, 62830, 58703, 54572, 50445, 13538, 9411, 5280, 1153, 29798,
              25671, 21540, 17413, 42971, 47098, 34713, 38840, 59231, 63358, 50973,
              55100, 9939, 14066, 1681, 5808, 26199, 30326, 17941, 22068, 55628,
              51565, 63758, 59695, 39368, 35305, 47498, 43435, 22596, 18533, 30726,
              26663, 6336, 2273, 14466, 10403, 52093, 56156, 60223, 64286, 35833,
              39896, 43963, 48026, 19061, 23124, 27191, 31254, 2801, 6864, 10931,
              14994, 64814, 60687, 56684, 52557, 48554, 44427, 40424, 36297, 31782,
              27655, 23652, 19525, 15522, 11395, 7392, 3265, 61215, 65342, 53085,
              57212, 44955, 49082, 36825, 40952, 28183, 32310, 20053, 24180, 11923,
              16050, 3793, 7920)
    crcAcc = 0
    for byte in inputData:
        ushort = (crcAcc << 8) & 0xFF00
        crcAcc = ushort ^ crcTab[((crcAcc >> 8) ^ byte) & 0xFF]

    return crcAcc


def padText(inText, minLength, padChar='0'):
    """Left-pad inText with padChar until achieving minLength."""
    while len(inText) < minLength:
        inText = padChar + inText

    return inText


def padTextRight(inText, minLength, padChar='0'):
    """Right-pad inText with padChar until achieving minLength."""
    while len(inText) < minLength:
        inText = inText + padChar

    return inText


def centerText(inText, lineLength):
    """Pad inText with BLANKS until inText is centered on line of lineLength."""
    PADS = lineLength // 2 - len(inText) // 2
    inText = str(' ' * PADS) + inText
    return inText


def unpackTime(theString, offset):
    """Returns time (HH:MM) from theString at offset."""
    theTime = ''
    j = struct.unpack_from('H', theString, offset)[0]
    if j == 65535:
        return '00:00'
    hr = j // 100
    mn = j % 100
    z = str(hr)
    if len(z) < 2:
        z = '0' + z
    theTime = z + ':'
    z = str(mn)
    if len(z) < 2:
        z = '0' + z
    theTime = theTime + z
    return theTime


def hiLows():
    """Read HILOWS packet from the console, populate global wxMinMax dictionary."""
    global HL

    # Flush stale data from previous commands
    wx.reset_input_buffer()

    # Send VER just to keep the console happy (discard its output)
    wxWrite('VER')
    time.sleep(WXDELAY)
    if wx.in_waiting:
        wx.read(wx.in_waiting)

    # Try to get the HILOWS packet with up to 2 attempts
    payload = None
    for attempt in range(2):
        try:
            payload, t = request_packet('HILOWS', 439, timeout=3)  # optionally pass timeout if you want longer wait
            if payload:
                # CRC check
                crc_val = CRC(t[1:439])
                wxMinMax['CRC-CALC'] = crc_val
                if crc_val == 0:
                    HL = payload
                    # Store the main body
                    writeDump(TMPPATH + 'HILOWS', HL)
                    break
                else:
                    raise WxError('Invalid CRC in HILOWS data packet')

        except Exception as e:
            print(tStamp() + f'HILOWS attempt {attempt+1} failed: {e}')
        time.sleep(1.0)

    if not payload:
        raise WxError('Failed to get valid HILOWS data packet after 2 attempts.')
        return

    packet_size = len(t)
    print(tStamp() + f'Read HILOWS packet from console, received {packet_size} bytes. CRC OK.')

    wxMinMax['BAROMETER_DAY_MIN_INHG'] = round(struct.unpack_from('H', t, 1)[0] / 1000.0, 2)
    wxMinMax['BAROMETER_DAY_MAX_INHG'] = round(struct.unpack_from('H', t, 3)[0] / 1000.0, 2)
    wxMinMax['BAROMETER_DAY_MIN_HPA'] = round(wxMinMax['BAROMETER_DAY_MIN_INHG'] * 33.8639, 1)
    wxMinMax['BAROMETER_DAY_MAX_HPA'] = round(wxMinMax['BAROMETER_DAY_MAX_INHG'] * 33.8639, 1)
    wxMinMax['BAROMETER_MONTH_MIN_INHG'] = round(struct.unpack_from('H', t, 5)[0] / 1000.0, 2)
    wxMinMax['BAROMETER_MONTH_MAX_INHG'] = round(struct.unpack_from('H', t, 7)[0] / 1000.0, 2)
    wxMinMax['BAROMETER_MONTH_MIN_HPA'] = round(wxMinMax['BAROMETER_MONTH_MIN_INHG'] * 33.8639, 1)
    wxMinMax['BAROMETER_MONTH_MAX_HPA'] = round(wxMinMax['BAROMETER_MONTH_MAX_INHG'] * 33.8639, 1)
    wxMinMax['BAROMETER_YEAR_MIN_INHG'] = round(struct.unpack_from('H', t, 9)[0] / 1000.0, 2)
    wxMinMax['BAROMETER_YEAR_MAX_INHG'] = round(struct.unpack_from('H', t, 11)[0] / 1000.0, 2)
    wxMinMax['BAROMETER_YEAR_MIN_HPA'] = round(wxMinMax['BAROMETER_YEAR_MIN_INHG'] * 33.8639, 1)
    wxMinMax['BAROMETER_YEAR_MAX_HPA'] = round(wxMinMax['BAROMETER_YEAR_MAX_INHG'] * 33.8639, 1)
    wxMinMax['BAROMETER_MIN_TIME'] = unpackTime(t, 13)
    wxMinMax['BAROMETER_MAX_TIME'] = unpackTime(t, 15)
    wxMinMax['WINDSPEED_DAY_MAX_MPH'] = struct.unpack_from('B', t, 17)[0]
    wxMinMax['WINDSPEED_DAY_MAX_KTS'] = round(wxMinMax['WINDSPEED_DAY_MAX_MPH'] * 0.868976, 1)
    wxMinMax['WINDSPEED_DAY_MAX_MSEC'] = round(wxMinMax['WINDSPEED_DAY_MAX_MPH'] * 0.44704, 1)
    wxMinMax['WINDSPEED_MONTH_MAX_MPH'] = struct.unpack_from('B', t, 20)[0]
    wxMinMax['WINDSPEED_MONTH_MAX_KTS'] = round(wxMinMax['WINDSPEED_MONTH_MAX_MPH'] * 0.868976, 1)
    wxMinMax['WINDSPEED_MONTH_MAX_MSEC'] = round(wxMinMax['WINDSPEED_MONTH_MAX_MPH'] * 0.44704, 1)
    wxMinMax['WINDSPEED_YEAR_MAX_MPH'] = struct.unpack_from('B', t, 21)[0]
    wxMinMax['WINDSPEED_YEAR_MAX_KTS'] = round(wxMinMax['WINDSPEED_YEAR_MAX_MPH'] * 0.868976, 1)
    wxMinMax['WINDSPEED_YEAR_MAX_MSEC'] = round(wxMinMax['WINDSPEED_YEAR_MAX_MPH'] * 0.44704, 1)
    wxMinMax['WINDSPEED_MAX_TIME'] = unpackTime(t, 18)
    j = wxMinMax['OUTTEMP_DAY_MIN_F'] = struct.unpack_from('H', t, 48)[0] / 10.0
    wxMinMax['OUTTEMP_DAY_MIN_C'] = FtoC(j)
    j = wxMinMax['OUTTEMP_DAY_MAX_F'] = struct.unpack_from('H', t, 50)[0] / 10.0
    wxMinMax['OUTTEMP_DAY_MAX_C'] = FtoC(j)
    j = wxMinMax['OUTTEMP_MONTH_MIN_F'] = struct.unpack_from('H', t, 58)[0] / 10.0
    wxMinMax['OUTTEMP_MONTH_MIN_C'] = FtoC(j)
    j = wxMinMax['OUTTEMP_MONTH_MAX_F'] = struct.unpack_from('H', t, 56)[0] / 10.0
    wxMinMax['OUTTEMP_MONTH_MAX_C'] = FtoC(j)
    j = wxMinMax['OUTTEMP_YEAR_MIN_F'] = struct.unpack_from('H', t, 62)[0] / 10.0
    wxMinMax['OUTTEMP_YEAR_MIN_C'] = FtoC(j)
    j = wxMinMax['OUTTEMP_YEAR_MAX_F'] = struct.unpack_from('H', t, 60)[0] / 10.0
    wxMinMax['OUTTEMP_YEAR_MAX_C'] = FtoC(j)
    wxMinMax['OUTTEMP_MAX_TIME'] = unpackTime(t, 54)
    wxMinMax['OUTTEMP_MIN_TIME'] = unpackTime(t, 52)
    j = wxMinMax['DEWPOINT_DAY_MIN_F'] = struct.unpack_from('H', t, 64)[0] / 1.0
    wxMinMax['DEWPOINT_DAY_MIN_C'] = FtoC(j)
    j = wxMinMax['DEWPOINT_DAY_MAX_F'] = struct.unpack_from('H', t, 66)[0] / 1.0
    wxMinMax['DEWPOINT_DAY_MAX_C'] = FtoC(j)
    j = wxMinMax['DEWPOINT_MONTH_MIN_F'] = struct.unpack_from('H', t, 74)[0] / 1.0
    wxMinMax['DEWPOINT_MONTH_MIN_C'] = FtoC(j)
    j = wxMinMax['DEWPOINT_MONTH_MAX_F'] = struct.unpack_from('H', t, 72)[0] / 1.0
    wxMinMax['DEWPOINT_MONTH_MAX_C'] = FtoC(j)
    j = wxMinMax['DEWPOINT_YEAR_MIN_F'] = struct.unpack_from('H', t, 78)[0] / 1.0
    wxMinMax['DEWPOINT_YEAR_MIN_C'] = FtoC(j)
    j = wxMinMax['DEWPOINT_YEAR_MAX_F'] = struct.unpack_from('H', t, 76)[0] / 1.0
    wxMinMax['DEWPOINT_YEAR_MAX_C'] = FtoC(j)
    wxMinMax['DEWPOINT_MIN_TIME'] = unpackTime(t, 68)
    wxMinMax['DEWPOINT_MAX_TIME'] = unpackTime(t, 70)
    wxMinMax['OUTHUM_DAY_MIN'] = struct.unpack_from('B', t, 277)[0]
    wxMinMax['OUTHUM_DAY_MAX'] = struct.unpack_from('B', t, 285)[0]
    wxMinMax['OUTHUM_MONTH_MIN'] = struct.unpack_from('B', t, 333)[0]
    wxMinMax['OUTHUM_MONTH_MAX'] = struct.unpack_from('B', t, 325)[0]
    wxMinMax['OUTHUM_YEAR_MIN'] = struct.unpack_from('B', t, 349)[0]
    wxMinMax['OUTHUM_YEAR_MAX'] = struct.unpack_from('B', t, 341)[0]
    wxMinMax['OUTHUM_MIN_TIME'] = unpackTime(t, 293)
    wxMinMax['OUTHUM_MAX_TIME'] = unpackTime(t, 309)
    wxMinMax['SOLAR_MAX_DAY'] = struct.unpack_from('H', t, 104)[0]
    wxMinMax['SOLAR_MAX_MONTH'] = struct.unpack_from('H', t, 108)[0]
    wxMinMax['SOLAR_MAX_YEAR'] = struct.unpack_from('H', t, 110)[0]
    j = struct.unpack_from('H', t, 106)[0]
    if j == 65535:
        wxMinMax['SOLAR_MAX_TIME'] = '00:00'
    else:
        wxMinMax['SOLAR_MAX_TIME'] = unpackTime(t, 106)
    wxMinMax['UVINDEX_MAX_DAY'] = struct.unpack_from('B', t, 112)[0] / 10.0
    wxMinMax['UVINDEX_MAX_MONTH'] = struct.unpack_from('B', t, 115)[0] / 10.0
    wxMinMax['UVINDEX_MAX_YEAR'] = struct.unpack_from('B', t, 116)[0] / 10.0
    j = struct.unpack_from('H', t, 113)[0]
    if j == 65535:
        wxMinMax['UVINDEX_MAX_TIME'] = '00:00'
    else:
        wxMinMax['UVINDEX_MAX_TIME'] = unpackTime(t, 113)
    if INCHES == False:
        wxMinMax['RAINRATE_MAX_HOUR_MMHR'] = round(struct.unpack_from('H', t, 121)[0] * 0.2, 1)
        wxMinMax['RAINRATE_MAX_DAY_MMHR'] = round(struct.unpack_from('H', t, 117)[0] * 0.2, 1)
        wxMinMax['RAINRATE_MAX_MONTH_MMHR'] = round(struct.unpack_from('H', t, 123)[0] * 0.2, 1)
        wxMinMax['RAINRATE_MAX_YEAR_MMHR'] = round(struct.unpack_from('H', t, 125)[0] * 0.2, 1)
    else:
        wxMinMax['RAINRATE_MAX_HOUR_MMHR'] = inToMm(round(struct.unpack_from('H', t, 121)[0] * 0.01, 1))
        wxMinMax['RAINRATE_MAX_DAY_MMHR'] = inToMm(round(struct.unpack_from('H', t, 117)[0] * 0.01, 1))
        wxMinMax['RAINRATE_MAX_MONTH_MMHR'] = inToMm(round(struct.unpack_from('H', t, 123)[0] * 0.01, 1))
        wxMinMax['RAINRATE_MAX_YEAR_MMHR'] = inToMm(round(struct.unpack_from('H', t, 125)[0] * 0.01, 1))
    j = struct.unpack_from('H', t, 119)[0]
    if j == 65535:
        wxMinMax['RAINRATE_MAX_TIME'] = '00:00'
    else:
        wxMinMax['RAINRATE_MAX_TIME'] = unpackTime(t, 119)
    if wxMinMax['OUTTEMP_DAY_MAX_C'] < -1.0:
        wxDict['FREEZE'] = True
    else:
        wxDict['FREEZE'] = False
    print(tStamp() + 'Setting FREEZE flag: ' + str(wxDict['FREEZE']))
    wxDict['CONDENSATION'] = False
    if wxDict['OUTTEMP_C'] < 5 and wxMinMax['OUTTEMP_DAY_MAX_C'] > -0.5 and wxDict['FREEZE'] == False:
        if wxDict['DAYRAIN_MM'] < 0.3 and wxDict['DAYRAIN_MM'] > 0.0 and wxDict['OUTHUM_P'] > 85:
            wxDict['CONDENSATION'] = True
    print(tStamp() + 'Setting CONDENSATION flag: ' + str(wxDict['CONDENSATION']))
    print(tStamp() + 'HILOWS packet CRC is verified.')
    wxMinMax['TIMESTAMP'] = datetime.datetime.now()


def writeBatteryLog(fileName='/var/tmp/battery.log'):
    """Writes timestamp and battery status to battery log file in fileName."""
    f = open(fileName, 'a')
    f.write(tStamp() + ' ISS battery should be replaced now.\n')
    f.close()


def writeVersion():
    """Writes program version to file: version.txt."""
    f = open('version.txt', 'w')
    f.write('\n%s\n\n' % PROGRAMNAME)
    f.close()


def writeDump(fileName, outData):
    """Writes outData to fileName."""
    f = open(fileName, 'wb')
    f.write(outData)
    f.close()


def writeWxMinMaxAsText(fileName='minmax.txt'):
    """Write essential data from wxMinMax to fileName."""
    global uptime
    midRow = 43
    timeDelta = datetime.datetime.now() - upSince
    deltaDays = timeDelta.days // 1
    deltaMins = timeDelta.seconds // 60
    deltaHrs = timeDelta.seconds // 3600
    deltaMins -= deltaHrs * 60
    deltaSecs = timeDelta.seconds - deltaMins * 60 - deltaHrs * 3600
    deltaStr = '%d day(s), %d hour(s), %d minute(s), %d second(s)' % (deltaDays, deltaHrs, deltaMins, deltaSecs)
    uptime = 'Running since ' + upSince.ctime() + ' LT.\n                         ' + deltaStr + '.\n Cycle ............... : %d\n' % cnt
    f = open(fileName, 'w')
    f.write('-' * LL)
    f.write('\n')
    f.write('<b>' + centerText(REPORTTITLE, LL) + '\n')
    f.write(centerText(wxDict['TIMESTAMP_WX'], LL) + '\n')
    s = centerText('LOCATION: ' + MYLOCATION + ' (' + MYPOSITION + ')', LL)
    s = s.replace('*', '&deg;')
    f.write(s + '</b>\n')
    f.write('-' * LL)
    f.write('\n')
    f.write('\n')
    s = "<b>TEMPERATURE</b>  (Today's MIN @ %s LT, MAX @ %s LT)\n" % (wxMinMax['OUTTEMP_MIN_TIME'], wxMinMax['OUTTEMP_MAX_TIME'])
    f.write(s)
    s = ' Today       '
    s += 'MIN %5.1f*C / %.1f*F' % (wxMinMax['OUTTEMP_DAY_MIN_C'], wxMinMax['OUTTEMP_DAY_MIN_F'])
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %5.1f*C / %.1f*F' % (wxMinMax['OUTTEMP_DAY_MAX_C'], wxMinMax['OUTTEMP_DAY_MAX_F'])
    s += '\n'
    s = s.replace('*', '&deg;')
    f.write(s)
    s = padTextRight(' ' + PRESENTMONTH, 13, ' ')
    s += 'MIN %5.1f*C / %.1f*F' % (wxMinMax['OUTTEMP_MONTH_MIN_C'], wxMinMax['OUTTEMP_MONTH_MIN_F'])
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %5.1f*C / %.1f*F' % (wxMinMax['OUTTEMP_MONTH_MAX_C'], wxMinMax['OUTTEMP_MONTH_MAX_F'])
    s += '\n'
    s = s.replace('*', '&deg;')
    f.write(s)
    s = ' This Year   '
    s += 'MIN %5.1f*C / %.1f*F' % (wxMinMax['OUTTEMP_YEAR_MIN_C'], wxMinMax['OUTTEMP_YEAR_MIN_F'])
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %5.1f*C / %.1f*F' % (wxMinMax['OUTTEMP_YEAR_MAX_C'], wxMinMax['OUTTEMP_YEAR_MAX_F'])
    s += '\n\n'
    s = s.replace('*', '&deg;')
    f.write(s)
    s = "<b>DEW POINT</b>    (Today's MIN @ %s LT, MAX @ %s LT)\n" % (wxMinMax['DEWPOINT_MIN_TIME'], wxMinMax['DEWPOINT_MAX_TIME'])
    f.write(s)
    s = ' Today       '
    s += 'MIN %5.1f*C / %.0f*F' % (wxMinMax['DEWPOINT_DAY_MIN_C'], wxMinMax['DEWPOINT_DAY_MIN_F'])
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %5.1f*C / %.0f*F' % (wxMinMax['DEWPOINT_DAY_MAX_C'], wxMinMax['DEWPOINT_DAY_MAX_F'])
    s += '\n'
    s = s.replace('*', '&deg;')
    f.write(s)
    s = padTextRight(' ' + PRESENTMONTH, 13, ' ')
    s += 'MIN %5.1f*C / %.0f*F' % (wxMinMax['DEWPOINT_MONTH_MIN_C'], wxMinMax['DEWPOINT_MONTH_MIN_F'])
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %5.1f*C / %.0f*F' % (wxMinMax['DEWPOINT_MONTH_MAX_C'], wxMinMax['DEWPOINT_MONTH_MAX_F'])
    s += '\n'
    s = s.replace('*', '&deg;')
    f.write(s)
    s = ' This Year   '
    s += 'MIN %5.1f*C / %.0f*F' % (wxMinMax['DEWPOINT_YEAR_MIN_C'], wxMinMax['DEWPOINT_YEAR_MIN_F'])
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %5.1f*C / %.0f*F' % (wxMinMax['DEWPOINT_YEAR_MAX_C'], wxMinMax['DEWPOINT_YEAR_MAX_F'])
    s += '\n\n'
    s = s.replace('*', '&deg;')
    f.write(s)
    s = "<b>HUMIDITY</b>     (Today's MIN @ %s LT, MAX @ %s LT)\n" % (wxMinMax['OUTHUM_MIN_TIME'], wxMinMax['OUTHUM_MAX_TIME'])
    f.write(s)
    s = ' Today       '
    s += 'MIN %d %%' % wxMinMax['OUTHUM_DAY_MIN']
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %d %%' % wxMinMax['OUTHUM_DAY_MAX']
    s += '\n'
    f.write(s)
    s = padTextRight(' ' + PRESENTMONTH, 13, ' ')
    s += 'MIN %d %%' % wxMinMax['OUTHUM_MONTH_MIN']
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %d %%' % wxMinMax['OUTHUM_MONTH_MAX']
    s += '\n'
    f.write(s)
    s = ' This Year   '
    s += 'MIN %d %%' % wxMinMax['OUTHUM_YEAR_MIN']
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %d %%' % wxMinMax['OUTHUM_YEAR_MAX']
    s += '\n\n'
    f.write(s)
    s = "<b>BAROMETER</b>    (Today's MIN @ %s LT, MAX @ %s LT)\n" % (wxMinMax['BAROMETER_MIN_TIME'], wxMinMax['BAROMETER_MAX_TIME'])
    f.write(s)
    s = ' Today       '
    s += 'MIN %6.1f hPa / %.2f inHg' % (wxMinMax['BAROMETER_DAY_MIN_HPA'], wxMinMax['BAROMETER_DAY_MIN_INHG'])
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %6.1f hPa / %.2f inHg' % (wxMinMax['BAROMETER_DAY_MAX_HPA'], wxMinMax['BAROMETER_DAY_MAX_INHG'])
    s += '\n'
    f.write(s)
    s = padTextRight(' ' + PRESENTMONTH, 13, ' ')
    s += 'MIN %6.1f hPa / %.2f inHg' % (wxMinMax['BAROMETER_MONTH_MIN_HPA'], wxMinMax['BAROMETER_MONTH_MIN_INHG'])
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %6.1f hPa / %.2f inHg' % (wxMinMax['BAROMETER_MONTH_MAX_HPA'], wxMinMax['BAROMETER_MONTH_MAX_INHG'])
    s += '\n'
    f.write(s)
    s = ' This Year   '
    s += 'MIN %6.1f hPa / %.2f inHg' % (wxMinMax['BAROMETER_YEAR_MIN_HPA'], wxMinMax['BAROMETER_YEAR_MIN_INHG'])
    s = padTextRight(s, midRow, ' ')
    s += 'MAX %6.1f hPa / %.2f inHg' % (wxMinMax['BAROMETER_YEAR_MAX_HPA'], wxMinMax['BAROMETER_YEAR_MAX_INHG'])
    s += '\n\n'
    f.write(s)
    s = '<b>WIND SPEED</b>' + "   (Today's MAX @ %s LT)\n" % wxMinMax['WINDSPEED_MAX_TIME']
    f.write(s)
    s = ' Today       '
    s += 'MAX %4.1f kts / %4.1f mph / %4.1f m/sec. / %s' % (wxMinMax['WINDSPEED_DAY_MAX_KTS'], wxMinMax['WINDSPEED_DAY_MAX_MPH'], wxMinMax['WINDSPEED_DAY_MAX_MSEC'], getBeaufort(wxMinMax['WINDSPEED_DAY_MAX_KTS']))
    s += '\n'
    f.write(s)
    s = padTextRight(' ' + PRESENTMONTH, 13, ' ')
    s += 'MAX %4.1f kts / %4.1f mph / %4.1f m/sec. / %s' % (wxMinMax['WINDSPEED_MONTH_MAX_KTS'], wxMinMax['WINDSPEED_MONTH_MAX_MPH'], wxMinMax['WINDSPEED_MONTH_MAX_MSEC'], getBeaufort(wxMinMax['WINDSPEED_MONTH_MAX_KTS']))
    s += '\n'
    f.write(s)
    s = ' This Year   '
    s += 'MAX %4.1f kts / %4.1f mph / %4.1f m/sec. / %s' % (wxMinMax['WINDSPEED_YEAR_MAX_KTS'], wxMinMax['WINDSPEED_YEAR_MAX_MPH'], wxMinMax['WINDSPEED_YEAR_MAX_MSEC'], getBeaufort(wxMinMax['WINDSPEED_YEAR_MAX_KTS']))
    s += '\n\n'
    f.write(s)
    if SOLARCF != 0 and UVCF != 0:
        s = '<b>UV INDEX and SOLAR RADIATION</b>\n'
        f.write(s)
        if wxMinMax['UVINDEX_MAX_DAY'] >= 0.1 and wxMinMax['SOLAR_MAX_DAY'] != 0:
            s = ' Today       '
            s += 'MAX UV Index %4.1f @ %s LT' % (wxMinMax['UVINDEX_MAX_DAY'], wxMinMax['UVINDEX_MAX_TIME'])
            s = padTextRight(s, midRow + 4, ' ')
            s += 'MAX SR %4d W/m<sup>2</sup> @ %s LT' % (wxMinMax['SOLAR_MAX_DAY'], wxMinMax['SOLAR_MAX_TIME'])
            s += '\n'
            f.write(s)
        s = padTextRight(' ' + PRESENTMONTH, 13, ' ')
        s += 'MAX UV Index %4.1f' % wxMinMax['UVINDEX_MAX_MONTH']
        s = padTextRight(s, midRow + 4, ' ')
        s += 'MAX SR %4d W/m<sup>2</sup>' % wxMinMax['SOLAR_MAX_MONTH']
        s += '\n'
        f.write(s)
        s = ' This Year   '
        s += 'MAX UV Index %4.1f' % wxMinMax['UVINDEX_MAX_YEAR']
        s = padTextRight(s, midRow + 4, ' ')
        s += 'MAX SR %4d W/m<sup>2</sup>' % wxMinMax['SOLAR_MAX_YEAR']
        s += '\n\n'
        f.write(s)
    s = '<b>RAINFALL RATE</b>\n'
    f.write(s)
    s = ''
    if wxMinMax['RAINRATE_MAX_HOUR_MMHR'] >= 0.1:
        s += ' Last Hour   MAX %5.1f mm/hour  / %4.2f in/hour\n' % (wxMinMax['RAINRATE_MAX_HOUR_MMHR'], mmToIn(wxMinMax['RAINRATE_MAX_HOUR_MMHR']))
    if wxMinMax['RAINRATE_MAX_DAY_MMHR'] >= 0.1:
        s += ' Today       MAX %5.1f mm/hour  / %4.2f in/hour at %s LT\n' % (wxMinMax['RAINRATE_MAX_DAY_MMHR'], mmToIn(wxMinMax['RAINRATE_MAX_DAY_MMHR']), wxMinMax['RAINRATE_MAX_TIME'])
    f.write(s)
    s = padTextRight(' ' + PRESENTMONTH, 13, ' ')
    s += 'MAX %5.1f mm/hour  / %4.2f in/hour\n' % (wxMinMax['RAINRATE_MAX_MONTH_MMHR'], mmToIn(wxMinMax['RAINRATE_MAX_MONTH_MMHR']))
    s += ' This Year   MAX %5.1f mm/hour  / %4.2f in/hour\n' % (wxMinMax['RAINRATE_MAX_YEAR_MMHR'], mmToIn(wxMinMax['RAINRATE_MAX_YEAR_MMHR']))
    s += '\n'
    s += ' NOTE: The rainfall <b>rate</b> does <b>not</b> indicate long-lasting rainfall at the\n'
    s += '       recorded rate.\n'
    f.write(s)
    f.write('-' * LL)
    f.write('\n')
    f.write('<b>CONSOLE and SYSTEM STATUS INFORMATION</b>\n')
    if wxDict['VER'].strip() != '':
        f.write(' Firmware Date ....... : %s\n' % wxDict['VER'].strip())
    if wxDict['NVER'].strip() != '':
        f.write(' Firmware Version .... : %s\n' % wxDict['NVER'].strip())
    if wxDict['BATTERYSTATUS'] == 0:
        f.write(' ISS Battery Status .. : OK (%d)\n' % wxDict['BATTERYSTATUS'])
    else:
        f.write(' ISS Battery Status .. : REPLACE (%d)\n' % wxDict['BATTERYSTATUS'])
    f.write(' Console Model ....... : %s\n' % wxDict['STATIONMODEL'])
    f.write(' Console Voltage ..... : %3.1f\n' % wxDict['VOLTAGE'])
    f.write(' Console Temperature . : %.1f&deg;C / %.1f &deg;F   RH: %d %% \n' % (wxDict['INTEMP_C'], wxDict['INTEMP_F'], wxDict['INHUM_P']))
    f.write(' Console RXCHECK ..... : %s \n' % decodeRXCHECK(wxDict['RXCHECK']))
    f.write(' Software Version .... : %s\n' % PROGRAMVERSION)
    f.write(' System Uptime ....... : %s' % uptime)
    if TEMPERATURECOMMAND != '':
        f.write(' RPi SoC Temperature . : %s&deg;C\n' % wxMinMax['SOCTEMP'])
    if LPS:
        f.write(' Data Packet Format .. : LOOP + LOOP2\n')
    else:
        f.write(' Data Packet Format .. : LOOP\n')
    f.write('-' * LL)
    f.write('\n')
    f.write(BRAGLINE)
    f.write('\n')
    f.close()
    fileInfo = os.stat(fileName)
    print(tStamp() + 'Wrote "' + fileName + '" to local disk, filesize = %d bytes.' % fileInfo.st_size)


def decodeRXCHECK(s):
    """Decodes RXCHECK string s, returning a more meaningful text string."""
    if s == 'Not available.':
        return s
    else:
        s = s.split()
        if len(s) != 5:
            return s
        return 'TOT:%s, LST:%s, RESYNC:%s, CONT:%s, CRC:%s' % (s[0], s[1], s[2], s[3], s[4])


def writeWxDataAsText(fileName='wxdata.txt'):
    """Write essential data from wxDict to fileName."""
    f = open(fileName, 'w')
    f.write('-' * LL)
    f.write('\n')
    f.write('<b>' + centerText(REPORTTITLE, LL) + '\n')
    f.write(centerText(wxDict['TIMESTAMP_WX'], LL) + '\n')
    s = centerText('LOCATION: ' + MYLOCATION + ' (' + MYPOSITION + ')', LL)
    s = s.replace('*', '&deg;')
    f.write(s + '\n')
    s = centerText('SUNRISE and SUNSET occur at ' + wxDict['SUNRISE_LT'] + ' & ' + wxDict['SUNSET_LT'] + ' LOCAL TIME', LL) + '</b>\n'
    s = s.replace('&', '&amp;')
    f.write(s)
    f.write('-' * LL)
    f.write('\n')
    f.write('\n')
    f.write('<b>TEMPERATURE and HUMIDITY</b>\n')
    f.write(' Outside Air Temperature ..... : %4.1f&deg;C  /  %4.1f&deg;F\n' % (wxDict['OUTTEMP_C'], wxDict['OUTTEMP_F']))
    if LPS:
        if wxDict['OUTTEMP_C'] <= WC_CUTOFF_C and wxDict['OUTTEMP_C'] != wxDict['WC_C']:
            f.write(' Wind Chill Temperature ...... : %4.1f&deg;C  /  %4.1f&deg;F\n' % (wxDict['WC_C'], wxDict['WC_F']))
        elif wxDict['THSW_C'] > 0 and wxDict['THSW_F'] < 255 and wxDict['THSW_C'] > wxDict['OUTTEMP_C']:
            f.write(' THSW Index .................. : %4.1f&deg;C  /  %4.1f&deg;F\n' % (wxDict['THSW_C'], wxDict['THSW_F']))
        elif wxDict['HINDEX_C'] > 0 and wxDict['HINDEX_F'] < 255 and wxDict['HINDEX_C'] > wxDict['OUTTEMP_C']:
            f.write(' Heat Index .................. : %4.1f&deg;C  /  %4.1f&deg;F\n' % (wxDict['HINDEX_C'], wxDict['HINDEX_F']))
    f.write(' Dew Point Temperature ....... : %4.1f&deg;C  /  %4.1f&deg;F\n' % (wxDict['DEWPOINT_C'], wxDict['DEWPOINT_F']))
    f.write(' Relative Humidity ........... : %d %%\n' % wxDict['OUTHUM_P'])
    f.write('\n')
    f.write('<b>BAROMETER</b>\n')
    f.write(' Barometric Pressure (QNH) ... : ' + str(wxDict['BAROMETER_HPA']) + ' hPa  /  ' + str(wxDict['BAROMETER_INHG']) + ' inHg\n')
    f.write(' Barometric Trend ............ : ' + wxDict['BAROTRENDTEXT'] + '\n')
    f.write('\n')
    txtWind = getBeaufort(wxDict['WIND_KTS'])
    txtGust = getBeaufort(wxDict.get('GUST10_KTS', wxDict['WIND_KTS']))
    if txtWind != txtGust:
        f.write('<b>WIND (present: %s from %s, gust: %s from %s)</b>\n' % (txtWind.lower(), wxDict['WIND_CARDINAL'], txtGust.lower(), wxDict['GUST_CARDINAL']))
    elif LPS:
        f.write('<b>WIND (present and gust: %s from %s)</b>\n' % (txtWind.lower(), wxDict['WIND_CARDINAL']))
    else:
        f.write('<b>WIND (present: %s from %s)</b>\n' % (txtWind.lower(), wxDict['WIND_CARDINAL']))
    f.write(' Present Wind Velocity ....... : ' + wxDict['WINDDIR'] + '&deg; at ' + str(wxDict['WIND_KTS']) + ' kts  /  ' + str(wxDict['WIND_MSEC']) + ' m/sec.  /  ' + str(wxDict['WIND_MPH']) + ' mph \n')
    if LPS:
        f.write(' 10-Minute Wind Gust ......... : ' + wxDict['GUST10DIR'] + '&deg; at ' + str(wxDict['GUST10_KTS']) + ' kts  /  ' + str(wxDict['GUST10_MSEC']) + ' m/sec.  /  ' + str(wxDict['GUST10_MPH']) + ' mph \n')
        f.write(' Average  2-Minute Wind Speed  : ' + str(wxDict['AVGWIND2_KTS']) + ' kts  /  ' + str(wxDict['AVGWIND2_MSEC']) + ' m/sec.  /  ' + str(wxDict['AVGWIND2_MPH']) + ' mph \n')
    f.write(' Average 10-Minute Wind Speed  : ' + str(wxDict['AVGWIND10_KTS']) + ' kts  /  ' + str(wxDict['AVGWIND10_MSEC']) + ' m/sec.  /  ' + str(wxDict['AVGWIND10_MPH']) + ' mph \n')
    f.write('\n')
    if SOLARCF != 0 and UVCF != 0:
        f.write('<b>UV INDEX and SOLAR RADIATION</b>\n')
        if wxDict['UVINDEX'] == -1:
            f.write(' UV Index .................... : Not available/sensor error.\n')
        else:
            f.write(' UV Index .................... : ' + str(wxDict['UVINDEX']) + '\n')
        if wxDict['SOLAR_W'] == -1:
            f.write(' Solar Radiation ............. : Not available/sensor error.\n')
        else:
            f.write(' Solar Radiation ............. : %d watts/m<sup>2</sup>\n' % wxDict['SOLAR_W'])
        f.write('\n')
    f.write('<b>RAINFALL</b>\n')
    if wxDict['FREEZE'] == False:
        f.write(' Present Rainfall Rate ....... : ' + padText(str(wxDict['RAINRATE_MMHR']), 6, ' ') + ' mm  /  %4.2f in per hour\n' % mmToIn(wxDict['RAINRATE_MMHR']))
        if LPS:
            if wxDict['RAINFALL15_MM'] > 0:
                f.write(' Rainfall Last 15 Minutes .... : ' + padText(str(wxDict['RAINFALL15_MM']), 6, ' ') + ' mm  /  %4.2f in\n' % mmToIn(wxDict['RAINFALL15_MM']))
            if wxDict['RAINFALL60_MM'] > 0:
                f.write(' Rainfall Last 60 Minutes .... : ' + padText(str(wxDict['RAINFALL60_MM']), 6, ' ') + ' mm  /  %4.2f in\n' % +mmToIn(wxDict['RAINFALL60_MM']))
            f.write(' Rainfall Last 24 Hours ...... : ' + padText(str(wxDict['RAINFALL24H_MM']), 6, ' ') + ' mm  /  %4.2f in\n' % mmToIn(wxDict['RAINFALL24H_MM']))
        f.write(' Rainfall Since Midnight ..... : ' + padText(str(wxDict['DAYRAIN_MM']), 6, ' ') + ' mm  /  %4.2f in\n' % mmToIn(wxDict['DAYRAIN_MM']))
        if wxDict['STORMSTART'] != '01.01.1970':
            f.write(' Rainfall Last Rainstorm ..... : ' + padText(str(wxDict['STORMRAIN_MM']), 6, ' ') + ' mm  /  %4.2f in (from %s)\n' % (mmToIn(wxDict['STORMRAIN_MM']), wxDict['STORMSTART']))
        if wxDict['CONDENSATION'] == True:
            f.write(' NOTE: Rainfall last 24 hrs may be over-reading due to condensation.\n')
    else:
        f.write(" Temperature < -1&deg;C, today's rainfall data not available.\n")
    if wxMinMax['OUTTEMP_MONTH_MAX_C'] > -1.0:
        f.write(padTextRight(' Rainfall ' + PRESENTMONTH + ' ', 30, '.') + ' : ' + padText(str(wxDict['MONTHRAIN_MM']), 6, ' ') + ' mm  /  %4.2f in\n' % mmToIn(wxDict['MONTHRAIN_MM']))
    if wxMinMax['OUTTEMP_YEAR_MAX_C'] > -1.0:
        f.write(' Rainfall This Year .......... : ' + padText(str(wxDict['YEARRAIN_MM']), 6, ' ') + ' mm  /  %4.2f in\n' % mmToIn(wxDict['YEARRAIN_MM']))
    f.write('\n')
    f.write('<b>EVAPOTRANSPIRATION</b>\n')
    if wxDict['ET_DAY_MM'] >= 0.1:
        f.write(' Since Midnight .............. : ' + padText(str(wxDict['ET_DAY_MM']), 6, ' ') + ' mm  /  %5.2f in\n' % mmToIn(wxDict['ET_DAY_MM']))
    f.write(padTextRight(' ' + PRESENTMONTH + ' ', 30, '.') + ' : ' + padText(str(wxDict['ET_MONTH_MM']), 6, ' ') + ' mm  /  %5.2f in\n' % mmToIn(wxDict['ET_MONTH_MM']))
    f.write(' This Year ................... : ' + padText(str(wxDict['ET_YEAR_MM']), 6, ' ') + ' mm  /  %5.2f in\n' % mmToIn(wxDict['ET_YEAR_MM']))
    f.write('\n')
    f.write('<b>GENERAL FORECAST</b>\n')
    f.write(' ' + wxDict['FCTEXT'].replace('.', '.\n', 5))
    f.write('\n')
    f.write('-' * LL)
    f.write('\n')
    f.write(' NOTE: Reported rainfall of 0.2 mm / 0.01" may be caused by condensation\n')
    f.write('       in the rain collector.\n')
    f.write('-' * LL)
    f.write('\n')
    f.write(BRAGLINE)
    f.write('\n')
    f.close()
    fileInfo = os.stat(fileName)
    print(tStamp() + 'Wrote "' + fileName + '" to local disk, filesize = %d bytes.' % fileInfo.st_size)


def writeWxDataAsCSV(fileName='wxdata.csv', SEP=','):
    """Write/append essential data from wxDict to the specified CSV file, using SEP as field separator."""
    global flashWrite
    f = open(fileName, 'a')
    oldSolar = wxDict['SOLAR_W']
    oldUV = wxDict['UVINDEX']
    if wxDict['SOLAR_W'] < 0:
        wxDict['SOLAR_W'] = 0
    if wxDict['UVINDEX'] < 0:
        wxDict['UVINDEX'] = 0
    s = ''
    s = wxDict['TIMESTAMP'] + SEP + str(wxDict['OUTTEMP_C']) + SEP + str(wxDict['OUTHUM_P']) + SEP
    s += str(wxDict['DEWPOINT_C']) + SEP + str(wxDict['BAROMETER_HPA']) + SEP + str(wxDict['WINDDIR']) + SEP
    s += str(wxDict['WIND_KTS']) + SEP + str(wxDict['UVINDEX']) + SEP + str(wxDict['SOLAR_W']) + SEP
    s += str(wxDict['RAINRATE_MMHR']) + SEP + str(wxDict['DAYRAIN_MM']) + SEP + str(wxDict['ET_DAY_MM']) + SEP
    s += str(wxDict['ET_MONTH_MM']) + SEP + str(wxDict['AVGWIND10_KTS'])
    wxDict['SOLAR_W'] = oldSolar
    wxDict['UVINDEX'] = oldUV
    if LPS:
        s += SEP + str(wxDict['AVGWIND2_KTS']) + SEP
        s += str(wxDict['GUST10_KTS']) + SEP + str(wxDict['GUST10DIR'])
    s += '\n'
    f.write(s)
    f.close()
    print(tStamp() + 'Logged values in CSV file: %s' % fileName)
    flashWrite += 1


def writeUIViewFile(fileName='uiview.txt'):
    """Write weather data to UIView-32 weather file for later APRS transmission."""
    if LPS == False:
        return
    f = open(fileName, 'w')
    s = wxDict['TIMESTAMP_APRS'] + '\n'
    s += wxDict['WINDDIR'] + '/' + padText(str(wxDict['WIND_MPH']), 3) + 'g' + padText(str(wxDict['GUST10_MPH']), 3)
    b = '%g' % round(wxDict['OUTTEMP_F'], 0)
    s += 't' + padText(b, 3)
    b = '%g' % round(wxDict['RAINFALL60_MM'] * 0.0393701 * 100, 0)
    s += 'r' + padText(b, 3)
    b = '%g' % round(wxDict['RAINFALL24H_MM'] * 0.0393701 * 100, 0)
    s += 'p' + padText(b, 3)
    b = '%g' % round(wxDict['DAYRAIN_MM'] * 0.0393701 * 100, 0)
    s += 'P' + padText(b, 3)
    if wxDict['OUTHUM_P'] != 100:
        s += 'h' + padText(str(wxDict['OUTHUM_P']), 2)
    else:
        s += 'h00'
    s += 'b%g' % (wxDict['BAROMETER_HPA'] * 10)
    f.write(s + '\n')
    print(tStamp() + 'Logged values in UIView-32/APRS weather file: %s' % fileName)
    f.close()


def getRawData(packet, offset, dataSize):
    """Returns "raw data" from the LOOP1, LOOP2 or HILOWS packets last read from the console."""
    thePacket = ''
    if packet == 1:
        thePacket = L1
    elif packet == 2:
        thePacket = L2
    elif packet == 3:
        thePacket = HL
    else:
        return
    if len(thePacket) < 99:
        return
    else:
        return struct.unpack_from(dataSize, thePacket, offset)[0]


def serializeXML(dictionary):
    """Simple XML serialization of dictionary."""
    xml = ''
    for key in list(dictionary.keys()):
        if isinstance(dictionary[key], dict):
            xml = '%s<%s>\n%s</%s>\n' % (xml, key.lower(), serializeXML(dictionary[key]), key.lower())
        elif isinstance(dictionary[key], list):
            xml = '%s<%s>' % (xml, key.lower())
            for item in dictionary[key]:
                xml = '%s%s' % (xml, serializeXML(item))

            xml = '%s</%s>' % (xml, key.lower())
        else:
            value = dictionary[key]
            xml = '%s<%s>%s</%s>\n' % (xml, key.lower(), value, key.lower())

    return xml


def writeXML(fileName='wxdata.xml'):
    """Writes wxDict as XML-like data to fileName."""
    s = serializeXML(wxDict)
    f = open(fileName, 'w')
    f.write('<?xml version="1.0"?>\n')
    f.write('<wxdata>\n')
    f.write(s)
    f.write('<wind_beaufort>\n')
    f.write(getBeaufort(wxDict['WIND_KTS']) + '\n')
    f.write('</wind_beaufort>\n')
    if LPS:
        f.write('<gust10_beaufort>\n')
        f.write(getBeaufort(wxDict['GUST10_KTS']) + '\n')
        f.write('</gust10_beaufort>\n')
        f.write('<avg2_beaufort>\n')
        f.write(getBeaufort(wxDict['AVGWIND2_KTS']) + '\n')
        f.write('</avg2_beaufort>\n')
        f.write('<avg10_beaufort>\n')
        f.write(getBeaufort(wxDict['AVGWIND10_KTS']) + '\n')
        f.write('</avg10_beaufort>\n')
    f.write('</wxdata>\n')
    f.close()
    fileInfo = os.stat(fileName)
    print(tStamp() + 'Wrote "' + fileName + '" to local disk, filesize = %d bytes.' % fileInfo.st_size)


def readFile(fileName):
    """Returns the contents of fileName. Not suitable for large files."""
    try:
        f = open(fileName, 'r')
        lines = f.readlines()
        f.close()
    except IOError as e:
        lines = []

    return lines


def updateRainFile(fileName, rainEntries):
    """Rewrites fileName with rainEntries --- used to update the MONTHLY RAIN file (yyyy-mm.rain)."""
    rainEntries.sort()
    f = open(fileName, 'w')
    f.writelines(rainEntries)
    f.close()


def storeRainAsCSV():
    """Compares, and if required: updates the monthly rainfall data file (yyyy-mm.rain)."""
    global flashWrite
    monthFile = CSVPATH + datetime.datetime.now().strftime('%Y-%m') + '.rain'
    rainEntries = readFile(monthFile)
    currentEntry = datetime.datetime.now().strftime('%d.%m.%Y') + ', ' + str(wxDict['DAYRAIN_MM']) + ', ' + str(wxDict['MONTHRAIN_MM']) + ', ' + str(wxDict['YEARRAIN_MM']) + '\n'
    if len(rainEntries) == 0:
        rainEntries.append(currentEntry)
        updateRainFile(monthFile, rainEntries)
        print(tStamp() + 'NEW rainfall entry added to NEW rainfall history file %s' % monthFile)
        flashWrite += 1
    else:
        lastEntry = rainEntries[len(rainEntries) - 1]
        if lastEntry != currentEntry:
            if lastEntry[0:9] == currentEntry[0:9]:
                rainEntries[len(rainEntries) - 1] = currentEntry
                updateRainFile(monthFile, rainEntries)
                print(tStamp() + 'Rainfall data UPDATED in rainfall history file %s' % monthFile)
                flashWrite += 1
            else:
                rainEntries.append(currentEntry)
                updateRainFile(monthFile, rainEntries)
                print(tStamp() + 'NEW rainfall entry APPENDED to rainfall history file %s' % monthFile)
                flashWrite += 1


def writeWxIconFile(fileName='wxIcon.html'):
    """Writes IMG SRC = weather ICON to fileName, including ALT text."""
    fc = wxDict['FCICON']
    ft = 'N/A'
    if fc == 2:
        ft = 'Mostly cloudy'
    elif fc == 3:
        ft = 'Mostly cloudy, rain within 12 hours'
    elif fc == 6:
        ft = 'Partially cloudy'
    elif fc == 7:
        ft = 'Partially cloudy, rain within 12 hours'
    elif fc == 8:
        ft = 'Mostly clear'
    elif fc == 18:
        ft = 'Mostly cloudy, snow/slush wossible within 12 hours'
    elif fc == 19:
        ft = 'Mostly cloudy, rain or snow within 12 hours'
    elif fc == 22:
        ft = 'Partially cloudy, snow/slush possible within 12 hours'
    elif fc == 23:
        ft = 'Partially cloudy, rain or snow within 12 hours'
    else:
        fc = 99
    f = open(fileName, 'w')
    s = '<div class="forecastIcon">\n'
    s += '<a href="./index.shtml">\n'
    s += '<img src="./images/wxIcon_%d.png" alt="%s"/>\n' % (fc, ft)
    s += '</a>\n'
    s += '</div>\n'
    f.write(s)
    f.close()


def setWxTime():
    """Get local/system time, sets console time accordingly."""
    if wx == None:
        return
    else:
        ts = s = ''
        t = time.localtime()
        ts = struct.pack('<BBBBBB', t.tm_sec, t.tm_min, t.tm_hour, t.tm_mday, t.tm_mon, t.tm_year - 1900)
        ts = ts + struct.pack('>H', CRC(ts))
        wx.reset_input_buffer()
        wx.reset_output_buffer()
        wxWrite('SETTIME')
        time.sleep(WXDELAY * 3)
        i = wx.in_waiting
        if i != 1:
            wx.reset_input_buffer()
            wx.reset_output_buffer()
            time.sleep(WXDELAY)
            wxWrite('SETTIME')
            time.sleep(WXDELAY * 3)
            i = wx.in_waiting
        s = wx.read(i)
        if len(s) > 0 and s[0] == 0x06:
            print(tStamp() + 'Console SETTIME, first ACK received.')
        else:
            print(tStamp() + f'Console SETTIME, first ACK NOT RECEIVED. Got: {s}')
        wxWrite(ts)
        time.sleep(WXDELAY * 3)
        i = wx.in_waiting
        s = wx.read(i)
        if len(s) > 0 and s[0] == 0x06:
            print(tStamp() + 'Console SETTIME, second ACK received. Console time set OK.')
        else:
            print(tStamp() + f'Console SETTIME, second ACK NOT RECEIVED. Console time NOT SET. Got: {s}')
        return


def needPreviousMonth(thisDay, thisMonth, thisYear):
    """GNUPLOT SUPPORT."""
    if thisDay != 1:
        return ''
    if thisMonth != 1:
        if thisMonth - 1 < 10:
            return str(thisYear) + '-0' + str(thisMonth - 1)
        else:
            return str(thisYear) + '-' + str(thisMonth - 1)

    return str(thisYear - 1) + '-12'


def getPreviousRainMonth(thisMonth, thisYear):
    """GNUPLOT SUPPORT."""
    if thisMonth != 1:
        if thisMonth - 1 < 10:
            return str(thisYear) + '-0' + str(thisMonth - 1)
        else:
            return str(thisYear) + '-' + str(thisMonth - 1)

    return str(thisYear - 1) + '-12'


def prepareData(thisDay, thisMonth, thisYear):
    """GNUPLOT SUPPORT."""
    d = needPreviousMonth(thisDay, thisMonth, thisYear)
    nowFile = CSVPATH + str(thisYear) + '-'
    if thisMonth < 10:
        nowFile += '0'
    nowFile += str(thisMonth) + '-' + CSVFILESUFFIX
    s = ''
    if d == '':
        s = CSVPATH + str(thisYear) + '-'
        if thisMonth < 10:
            s += '0'
        s += str(thisMonth)
        s += '-' + CSVFILESUFFIX
        s = 'cp ' + s + ' ' + TMPPATH + 'plotdata.tmp'
    else:
        s = 'tail -n 144 ' + CSVPATH + d + '-' + CSVFILESUFFIX + ' > ' + TMPPATH + 'prevdata.tmp; cat ' + TMPPATH + 'prevdata.tmp ' + nowFile + ' > ' + TMPPATH + 'plotdata.tmp; rm ' + TMPPATH + 'prevdata.tmp'
    os.system(s)


def prepareRainData(thisDay, thisMonth, thisYear):
    """GNUPLOT SUPPORT."""
    d = getPreviousRainMonth(thisMonth, thisYear)
    nowFile = CSVPATH + str(thisYear) + '-'
    if thisMonth < 10:
        nowFile += '0'
    nowFile += str(thisMonth) + '.rain'
    s = ''
    if d == '':
        s = CSVPATH + str(thisYear) + '-'
        if thisMonth < 10:
            s += '0'
        s += str(thisMonth)
        s += '.rain'
        s = 'cp ' + s + ' ' + TMPPATH + 'plotraindata.tmp'
    else:
        s = 'tail -n 32 ' + CSVPATH + d + '.rain > ' + TMPPATH + 'prevraindata.tmp 2> /dev/null; cat ' + TMPPATH + 'prevraindata.tmp ' + nowFile + ' > ' + TMPPATH + 'plotraindata.tmp; rm ' + TMPPATH + 'prevraindata.tmp'
    os.system(s)


def prepareTemperatureData(fromMonth, fromYear, toMonth, toYear):
    """GNUPLOT SUPPORT."""
    theRange = []
    d1 = datetime.date(fromYear, fromMonth, 1)
    d2 = datetime.date(toYear, toMonth, 1) + relativedelta(day=31)
    theDate = d1
    while theDate < d2:
        theRange.append(theDate.strftime('%Y-%m'))
        theDate = theDate + datetime.timedelta(days=31)
        theDate = theDate.replace(day=1)

    theRange.sort()
    maxValue = {}
    minValue = {}
    iFile = None
    for d in theRange:
        try:
            iFile = open(CSVPATH + d + '-wxdata.csv', 'r')
            csvData = iFile.readlines()
            for dataLine in csvData:
                dataDate = dataLine.split(',')[0][0:10]
                evalValue = float(dataLine.split(',')[1])
                if dataDate not in list(maxValue.keys()):
                    maxValue[dataDate] = evalValue
                elif evalValue > maxValue[dataDate]:
                    maxValue[dataDate] = evalValue
                if dataDate not in list(minValue.keys()):
                    minValue[dataDate] = evalValue
                elif evalValue < minValue[dataDate]:
                    minValue[dataDate] = evalValue

            iFile.close()
        except Exception as e:
            pass

    theData = []
    for date in list(minValue.keys()):
        oLine = date[6:10] + '.' + date[3:5] + '.' + date[0:2] + ', ' + str(minValue[date]) + ', ' + str(maxValue[date]) + '\n'
        theData.append(oLine)

    maxValue = {}
    minValue = {}
    theData.sort()
    oFile = open(TMPPATH + 'plotminmax.tmp', 'w')
    oFile.writelines(theData[-365:])
    oFile.close()
    return


def prepareTemperatureAndSolarData(fromMonth, fromYear, toMonth, toYear):
    """GNUPLOT SUPPORT."""
    theRange = []
    d1 = datetime.date(fromYear, fromMonth, 1)
    d2 = datetime.date(toYear, toMonth, 1) + relativedelta(day=31)
    theDate = d1
    while theDate < d2:
        theRange.append(theDate.strftime('%Y-%m'))
        theDate = theDate + datetime.timedelta(days=31)
        theDate = theDate.replace(day=1)

    theRange.sort()
    maxSolar = {}
    maxTemp = {}
    iFile = None
    for d in theRange:
        try:
            iFile = open(CSVPATH + d + '-wxdata.csv', 'r')
            csvData = iFile.readlines()
            for dataLine in csvData:
                dataDate = dataLine.split(',')[0][0:10]
                evalTemp = float(dataLine.split(',')[1])
                evalSolar = float(dataLine.split(',')[8])
                if dataDate not in list(maxSolar.keys()):
                    maxSolar[dataDate] = evalSolar
                elif evalSolar > maxSolar[dataDate]:
                    maxSolar[dataDate] = evalSolar
                if dataDate not in list(maxTemp.keys()):
                    maxTemp[dataDate] = evalTemp
                elif evalTemp > maxTemp[dataDate]:
                    maxTemp[dataDate] = evalTemp

            iFile.close()
        except Exception as e:
            pass

    theData = []
    for date in list(maxSolar.keys()):
        oLine = date[6:10] + '.' + date[3:5] + '.' + date[0:2] + ', ' + str(maxTemp[date]) + ', ' + str(maxSolar[date]) + '\n'
        theData.append(oLine)

    maxTemp = {}
    maxSolar = {}
    theData.sort()
    oFile = open(TMPPATH + 'plottempsolar.tmp', 'w')
    oFile.writelines(theData[-365:])
    oFile.close()
    return


def prepareSolarData(fromMonth, fromYear, toMonth, toYear):
    """GNUPLOT SUPPORT."""
    theRange = []
    d1 = datetime.date(fromYear, fromMonth, 1)
    d2 = datetime.date(toYear, toMonth, 1) + relativedelta(day=31)
    theDate = d1
    while theDate < d2:
        theRange.append(theDate.strftime('%Y-%m'))
        theDate = theDate + datetime.timedelta(days=31)
        theDate = theDate.replace(day=1)

    theRange.sort()
    maxSolar = {}
    maxUV = {}
    iFile = None
    for d in theRange:
        try:
            iFile = open(CSVPATH + d + '-wxdata.csv', 'r')
            csvData = iFile.readlines()
            for dataLine in csvData:
                dataDate = dataLine.split(',')[0][0:10]
                evalUV = float(dataLine.split(',')[7])
                evalSolar = float(dataLine.split(',')[8])
                if dataDate not in list(maxSolar.keys()):
                    maxSolar[dataDate] = evalSolar
                elif evalSolar > maxSolar[dataDate]:
                    maxSolar[dataDate] = evalSolar
                if dataDate not in list(maxUV.keys()):
                    maxUV[dataDate] = evalUV
                elif evalUV > maxUV[dataDate]:
                    maxUV[dataDate] = evalUV

            iFile.close()
        except Exception as e:
            pass

    theData = []
    for date in list(maxSolar.keys()):
        oLine = date[6:10] + '.' + date[3:5] + '.' + date[0:2] + ', ' + str(maxUV[date]) + ', ' + str(maxSolar[date]) + '\n'
        theData.append(oLine)

    maxUV = {}
    maxSolar = {}
    theData.sort()
    oFile = open(TMPPATH + 'plotsolar.tmp', 'w')
    oFile.writelines(theData[-365:])
    oFile.close()
    return


def prepareAnnualWindData(fromMonth, fromYear, toMonth, toYear):
    """PYTHON-MATLIBPLOT SUPPORT."""
    theRange = []
    d1 = datetime.date(fromYear, fromMonth, 1)
    d2 = datetime.date(toYear, toMonth, 1) + relativedelta(day=31)
    theDate = d1
    while theDate < d2:
        theRange.append(theDate.strftime('%Y-%m'))
        theDate = theDate + datetime.timedelta(days=31)
        theDate = theDate.replace(day=1)

    theRange.sort()
    windData = {}
    iFile = None
    for d in theRange:
        try:
            iFile = open(CSVPATH + d + '-wxdata.csv', 'r')
            csvData = iFile.readlines()
            for dataLine in csvData:
                dataDateTime = dataLine.split(',')[0][0:19]
                windDir = float(dataLine.split(',')[5])
                windSpd = float(dataLine.split(',')[6])
                windData[dataDateTime] = [
                 windDir, windSpd]

            iFile.close()
        except Exception as e:
            pass

    theData = []
    for dateTime in list(windData.keys()):
        oLine = dateTime[6:10] + '.' + dateTime[3:5] + '.' + dateTime[0:2] + ' ' + dateTime[11:20] + ', ' + str(windData[dateTime][0]) + ', ' + str(windData[dateTime][1]) + '\n'
        theData.append(oLine)

    windData = {}
    theData.sort()
    oFile = open(TMPPATH + 'plotannualwind.tmp', 'w')
    oFile.writelines(theData[-365:])
    oFile.close()
    return


def prepareBaroData(fromDay, fromMonth, fromYear, toDay, toMonth, toYear):
    """GNUPLOT SUPPORT."""
    theRange = []
    d1 = datetime.datetime(fromYear, fromMonth, fromDay, 0, 0, 0)
    d2 = datetime.datetime(toYear, toMonth, toDay, 23, 59, 59)
    theDate = d1
    while theDate < d2:
        theRange.append(theDate.strftime('%Y-%m-%d'))
        theDate = theDate + datetime.timedelta(days=1)

    theRange.sort()
    baroData = {}
    iFile = None
    for d in theRange:
        try:
            iFile = open(CSVPATH + d[0:7] + '-wxdata.csv', 'r')
            csvData = iFile.readlines()
            for dataLine in csvData:
                dataDateTime = dataLine.split(',')[0][0:19]
                if dataDateTime[0:10] == d[8:10] + '.' + d[5:7] + '.' + d[0:4]:
                    baroData[dataDateTime] = float(dataLine.split(',')[4])

            iFile.close()
        except Exception as e:
            pass

    theData = []
    for dateTime in list(baroData.keys()):
        oLine = dateTime[6:10] + '.' + dateTime[3:5] + '.' + dateTime[0:2] + ' ' + dateTime[11:20] + ', ' + str(baroData[dateTime]) + '\n'
        theData.append(oLine)

    baroData = {}
    theData.sort()
    oFile = open(TMPPATH + 'barodata.tmp', 'w')
    oFile.writelines(theData)
    oFile.close()
    return


def runGnuplot(GPC, TMP, unlink_tmp=True):
    """ run gnuplot """

    linlen = 76
    gpc_file = Path(GPC)
    tmp_file = Path(TMP)

    try:
        result = subprocess.run(
            ["gnuplot", str(gpc_file)],
            check=True,
            stdout=subprocess.PIPE,   # capture normal output
            stderr=subprocess.PIPE,   # capture errors if they happen
            text=True
        )

        #if DEBUG and result.stdout:
        #    print("-" * linlen)
        #    print(tStamp() + "gnuplot stdout:\n", result.stdout)
        #    print("-" * linlen)

    except subprocess.CalledProcessError as e:
        print(tStamp() + 'ERROR gnuplot %s failed!' % GPC)
        if e.stderr:
            print("-" * linlen)
            print("stderr output:\n", e.stderr)
            print("-" * linlen)
    except FileNotFoundError:
        print(tStamp() + "Error: gnuplot not found. Is it installed?")

    # Always attempt cleanup
    gpc_file.unlink(missing_ok=True)
    if unlink_tmp:
        tmp_file.unlink(missing_ok=True)


def plotMinMaxTemp():
    """GNUPLOT SUPPORT."""
    prepareGPC('', toTime(), PLOTMINMAXTITLE, HOMEPATH + 'plotMinMaxTemp.input', TMPPATH + 'plotMinMaxTemp.gpc', COMMISSIONDATE)
    runGnuplot(TMPPATH + 'plotMinMaxTemp.gpc', TMPPATH + 'plotminmax.tmp')


def plotSolar():
    """GNUPLOT SUPPORT."""
    prepareGPC('', toTime(), PLOTSOLARTITLE, HOMEPATH + 'plotSolar.input', TMPPATH + 'plotSolar.gpc', COMMISSIONDATE)
    runGnuplot(TMPPATH + 'plotSolar.gpc', TMPPATH + 'plotsolar.tmp')


def plotTempSolar():
    """GNUPLOT SUPPORT."""
    prepareGPC('', toTime(), PLOTTEMPSOLARTITLE, HOMEPATH + 'plotTempSolar.input', TMPPATH + 'plotTempSolar.gpc', COMMISSIONDATE)
    runGnuplot(TMPPATH + 'plotTempSolar.gpc', TMPPATH + 'plottempsolar.tmp')


def plotAnnualWind():
    """PYTHON-MATLIBPLOT SUPPORT."""
    prepareGPC('', toTime(), PLOTANNUALWINDTITLE, HOMEPATH + 'plotAnnualWind.input', TMPPATH + 'plotAnnualWind.gpc', COMMISSIONDATE)
    runGnuplot(TMPPATH + 'plotAnnualWind.gpc', TMPPATH + 'plotannualwind.tmp')


def plotBaroWeek():
    """GNUPLOT SUPPORT."""
    prepareGPC('', toTime(), PLOTBAROWEEKTITLE, HOMEPATH + 'plotBaroWeek.input', TMPPATH + 'plotBaroWeek.gpc', COMMISSIONDATE)
    runGnuplot(TMPPATH + 'plotBaroWeek.gpc', TMPPATH + 'barodata.tmp')


def sunTimes():
    """GNUPLOT SUPPORT."""
    try:
        f = open(TMPPATH + 'sunrise.tmp', 'r')
        old_sunrise = f.readline().strip()
        f.close()
    except IOError as e:
        old_sunrise = '01.01.2011 08:01:02'

    old_sunrise = datetime.datetime.strptime(old_sunrise, '%d.%m.%Y %H:%M:%S')
    console_sunrise = datetime.datetime.now().strftime('%d.%m.%Y ') + wxDict['SUNRISE_LT'] + ':00'
    console_sunrise = datetime.datetime.strptime(console_sunrise, '%d.%m.%Y %H:%M:%S')
    if datetime.datetime.now() < console_sunrise:
        console_sunrise = console_sunrise - datetime.timedelta(days=1)
    console_sunrise = console_sunrise.strftime('%d.%m.%Y %H:%M:%S')
    old_sunrise = old_sunrise.strftime('%d.%m.%Y %H:%M:%S')
    if console_sunrise != old_sunrise:
        f = open(TMPPATH + 'sunrise.tmp', 'w')
        f.write(console_sunrise + '\n')
        f.close()
    try:
        f = open(TMPPATH + 'sunset.tmp', 'r')
        old_sunset = f.readline().strip()
        f.close()
    except IOError as e:
        old_sunset = '01.01.2011 22:01:02'

    old_sunset = datetime.datetime.strptime(old_sunset, '%d.%m.%Y %H:%M:%S')
    console_sunset = datetime.datetime.now().strftime('%d.%m.%Y ') + wxDict['SUNSET_LT'] + ':00'
    console_sunset = datetime.datetime.strptime(console_sunset, '%d.%m.%Y %H:%M:%S')
    if datetime.datetime.now() < console_sunset:
        console_sunset = console_sunset - datetime.timedelta(days=1)
    console_sunset = console_sunset.strftime('%d.%m.%Y %H:%M:%S')
    old_sunset = old_sunset.strftime('%d.%m.%Y %H:%M:%S')
    if console_sunset != old_sunset:
        f = open(TMPPATH + 'sunset.tmp', 'w')
        f.write(console_sunset + '\n')
        f.close()


def prepareGPC(fromTime, toTime, plotTitle, inFile, outFile, commissionDate=''):
    """GNUPLOT SUPPORT."""
    f = open(inFile, 'r')
    s = f.read()
    f.close()
    if commissionDate == '':
        s = s.replace('COMMISSIONDATE', '01.01.1970')
    else:
        s = s.replace('COMMISSIONDATE', commissionDate)
    s = s.replace('FROMTIME', fromTime)
    s = s.replace('TOTIME', toTime)
    s = s.replace('TIMESTAMP', 'Updated: ' + toTime + ' LT')
    s = s.replace('PLOTTITLE', plotTitle)
    s = s.replace('RAINTHRESHOLDTEXT', RAINTHRESHOLDTEXT)
    s = s.replace('RAINTHRESHOLD_MM', str(RAINTHRESHOLD_MM))
    f = open(outFile, 'w')
    f.write(s)
    f.close()


def findRainPerMonth():
    """Support function to extract a series of rain data from 01.01.[PRESENT_YEAR-1] until NOW,"""
    maxYear = datetime.datetime.now().year
    maxMonth = datetime.datetime.now().month
    minYear = maxYear - 1
    minMonth = 1
    monthRange = []
    monthlyRain = {}
    for month in range(minMonth, 13):
        monthRange.append('%d-%02d' % (minYear, month))

    for month in range(minMonth, maxMonth + 1):
        monthRange.append('%d-%02d' % (maxYear, month))

    for rainFilePrefix in monthRange:
        rainDays = 0
        monthRain = 0
        rainFileName = CSVPATH + rainFilePrefix + '.rain'
        try:
            rainFile = open(rainFileName, 'r')
            rainLines = rainFile.readlines()
            rainFile.close()
            for rainLine in rainLines:
                dayRain = float(rainLine.split(',')[1])
                if dayRain > RAINTHRESHOLD_MM:
                    rainDays += 1

            rainLines = rainLines[len(rainLines) - 1]
            monthRain = rainLines.split(',')[2]
            if float(monthRain) > RAINTHRESHOLD_MM:
                monthlyRain[rainFilePrefix] = [
                 float(monthRain), rainDays]
            else:
                monthlyRain[rainFilePrefix] = [
                 0, rainDays]
        except Exception as e:
            monthlyRain[rainFilePrefix] = [
             -1, -1]

    rainData = []
    for month in monthlyRain:
        rainData.append('%s, %0.2f, %d\n' % (month, monthlyRain[month][0], monthlyRain[month][1]))

    rainData.sort()
    f = open(TMPPATH + 'monthlyRain.tmp', 'w')
    f.writelines(rainData)
    f.close()


def fromTime():
    """GNUPLOT SUPPORT."""
    d = datetime.datetime.now()
    d = d + datetime.timedelta(hours=-24)
    return d.strftime('%d.%m.%Y %H:%M:%S')


def toTime():
    """GNUPLOT SUPPORT."""
    return datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')


def fromDate(numDays, option=0):
    """GNUPLOT SUPPORT."""
    d = datetime.datetime.now()
    d = d + datetime.timedelta(days=numDays)
    if option == 0:
        return d.strftime('%d.%m.%Y')
    else:
        return d.strftime('%Y.%m.%d')


def todayDate(option=0):
    """GNUPLOT SUPPORT."""
    if option == 0:
        return datetime.datetime.now().strftime('%d.%m.%Y')
    else:
        return datetime.datetime.now().strftime('%Y.%m.%d')


def plotData():
    """GNUPLOT SUPPORT."""
    prepareData(datetime.datetime.now().day, datetime.datetime.now().month, datetime.datetime.now().year)
    prepareGPC(fromTime(), toTime(), PLOT24TITLE, HOMEPATH + 'plot24.input', TMPPATH + 'plot24.gpc')
    if LPS:
        prepareGPC(fromTime(), toTime(), PLOT24WINDTITLE, HOMEPATH + 'plot24windL2.input', TMPPATH + 'plot24wind.gpc')
    else:
        prepareGPC(fromTime(), toTime(), PLOT24WINDTITLE, HOMEPATH + 'plot24windL1.input', TMPPATH + 'plot24wind.gpc')
    prepareRainData(datetime.datetime.now().day, datetime.datetime.now().month, datetime.datetime.now().year)
    prepareGPC(fromDate(-31), toTime(), PLOTRAINMONTHTITLE, HOMEPATH + 'plotRainMonth.input', TMPPATH + 'plotRainMonth.gpc', COMMISSIONDATE)
    findRainPerMonth()
    prepareGPC('', toTime(), PLOTRAINDAYSPERMONTHTITLE, HOMEPATH + 'plotRainDaysPerMonth.input', TMPPATH + 'plotRainDaysPerMonth.gpc', COMMISSIONDATE)
    prepareGPC('', toTime(), PLOTRAINPERMONTHTITLE, HOMEPATH + 'plotRainPerMonth.input', TMPPATH + 'plotRainPerMonth.gpc', COMMISSIONDATE)

    runGnuplot(TMPPATH + 'plot24.gpc', TMPPATH + 'plotdata.tmp', False)
    runGnuplot(TMPPATH + 'plot24wind.gpc', TMPPATH + 'plotdata.tmp')
    runGnuplot(TMPPATH + 'plotRainMonth.gpc', TMPPATH + 'plotraindata.tmp', False)
    runGnuplot(TMPPATH + 'plotRainDaysPerMonth.gpc', TMPPATH + 'dummy.tmp', False)
    runGnuplot(TMPPATH + 'plotRainPerMonth.gpc', TMPPATH + 'dummy.tmp')


def getBeaufortIndex(windSpeedKTS):
    """Helper function for the getBeaufort function. Returns dictionary index [0,12] for windSpeedKTS."""
    w = windSpeedKTS
    if w <= 0:
        return 0
    if w <= 3:
        return 1
    if w <= 6:
        return 2
    if w <= 10:
        return 3
    if w <= 16:
        return 4
    if w <= 21:
        return 5
    if w <= 27:
        return 6
    if w <= 33:
        return 7
    if w <= 40:
        return 8
    if w <= 47:
        return 9
    if w <= 55:
        return 10
    if w <= 63:
        return 11
    if w > 63:
        return 12


def getBeaufort(windSpeedKTS):
    """Given wind speed in knots, returns textual description from the Beaufort scale."""
    return beaufortText[getBeaufortIndex(windSpeedKTS)]


def getCardinalDirection(direction):
    """Returns cardinal wind direction."""
    s = '-'
    if direction >= 0 and direction < 11.25:
        s = 'N'
    elif direction >= 11.25 and direction < 33.75:
        s = 'NNE'
    elif direction >= 33.75 and direction < 56.25:
        s = 'NE'
    elif direction >= 56.25 and direction < 78.75:
        s = 'ENE'
    elif direction >= 78.75 and direction < 101.25:
        s = 'E'
    elif direction >= 101.25 and direction < 123.75:
        s = 'ESE'
    elif direction >= 123.75 and direction < 146.25:
        s = 'SE'
    elif direction >= 146.25 and direction < 168.75:
        s = 'SSE'
    elif direction >= 168.75 and direction < 191.25:
        s = 'S'
    elif direction >= 191.25 and direction < 213.75:
        s = 'SSW'
    elif direction >= 213.75 and direction < 236.25:
        s = 'SW'
    elif direction >= 236.25 and direction < 258.75:
        s = 'WSW'
    elif direction >= 258.75 and direction < 281.25:
        s = 'W'
    elif direction >= 281.25 and direction < 303.75:
        s = 'WNW'
    elif direction >= 303.75 and direction < 326.25:
        s = 'NW'
    elif direction >= 326.25 and direction < 348.75:
        s = 'NNW'
    elif direction >= 348.75 and direction <= 360:
        s = 'N'
    return s


def getDavisType(stationType):
    """Returns textual description of Davis console model number as provided in numeric value stationType."""
    s = stationType
    u = ''
    if s == 17:
        u = 'Vantage Vue'
    elif s == 16:
        u = 'Vantage Pro/Vantage Pro2'
    elif s == 6:
        u = 'Health Enviromonitor'
    elif s == 5:
        u = 'Energy Enviromonitor'
    elif s == 4:
        u = 'GroWeather'
    elif s == 3:
        u = 'Perception'
    elif s == 2:
        u = 'Monitor'
    elif s == 1:
        u = 'Wizard II'
    elif s == 0:
        u = 'Wizard III'
    else:
        u = 'Unknown'
    return u + ' (%d)' % stationType


def updateWUnderground():
    """Submit data to Weather Underground. Requires LOOP + LOOP2 packets."""
    if WU_USER == '' or WU_PASS == '' or LPS == False:
        return 'WU_USER / WU_PASS not set or LOOP2 data packet unavailable.'
    dataError = wxDict.get('DATAERROR', False)
    if dataError == True:
        return 'Erroneous weather data will not be uploaded to Weather Underground.'

    base_url = 'https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php'
    params = {
        'action': 'updateraw',
        'ID': WU_USER,
        'PASSWORD': WU_PASS,
        'dateutc': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'winddir': wxDict['WINDDIR'],
        'windspeedmph': wxDict['WIND_MPH'],
        'windspdmph_avg2m': wxDict['AVGWIND2_MPH'],
        'windgustmph_10m': wxDict['GUST10_MPH'],
        'windgustdir_10m': wxDict['GUST10DIR'],
        'windgustmph': wxDict['GUST10_MPH'],
        'windgustdir': wxDict['GUST10DIR'],
        'humidity': wxDict['OUTHUM_P'],
        'dewptf': wxDict['DEWPOINT_F'],
        'tempf': wxDict['OUTTEMP_F'],
        'rainin': wxDict['RAINFALL60_MM'] * 0.0393701,
        'dailyrainin': wxDict['DAYRAIN_MM'] * 0.0393701,
        'baromin': wxDict['BAROMETER_INHG'],
        'softwaretype': PROGRAMNAME
    }

    if SOLARCF != 0:
        params['solarradiation'] = wxDict['SOLAR_W']
    if UVCF != 0:
        params['UV'] = wxDict['UVINDEX']

    query = urllib.parse.urlencode(params)
    url = f"{base_url}?{query}"

    try:
        if DEBUG:
            debugWrite('WeatherUnderground.debug.txt', url)
        z = urllib.request.urlopen(url)
        s = z.readline().decode('utf-8')
        z.close()
    except Exception as e:
        sys.exc_info()
        print(tStamp() + 'HTTP GET/WeatherUnderground.com: making a second attempt.')
        z = urllib.request.urlopen(url)
        s = z.readline().decode('utf-8')
        z.close()

    return s


def updateWindFinder():
    """Submit data to WindFinder.com. Requires LOOP + LOOP2 packets."""
    if WF_StationID == '' or WF_Password == '' or LPS == False:
        return 'WF_StationID / WF_Password not set or LOOP2 data packet unavailable.'
    dataError = wxDict.get('DATAERROR', False)
    if dataError == True:
        return 'Erroneous weather data not being uploaded to WindFinder.com.'

    base_url = 'https://www.windfinder.com/wind-cgi/httpload.pl?'

    params = {
        'sender_id': WF_StationID,
        'password': WF_Password,
        'date': datetime.datetime.now().strftime('%d.%m.%Y'),
        'time': datetime.datetime.now().strftime('%H:%M'),
        'airtemp': wxDict['OUTTEMP_C'],
        'windspeed': wxDict['WIND_KTS'],
        'gust': wxDict['GUST10_KTS'],
        'winddir': wxDict['WINDDIR'],
        'pressure': wxDict['BAROMETER_HPA'],
        'rain': wxDict['RAINFALL60_MM']
    }

    query = urllib.parse.urlencode(params)
    url = base_url + query

    try:
        if DEBUG:
            debugWrite('WindFinder.debug.txt', url)
        z = urllib.request.urlopen(url)
        s = z.read().decode('utf-8')
        z.close()
    except Exception as e:
        sys.exc_info()
        print(tStamp() + 'HTTP GET/WindFinder.com: making a second attempt.')
        z = urllib.request.urlopen(url)
        s = z.read().decode('utf-8')
        z.close()

    return s


def updateWindGURU():
    """Submit data to WindGURU.cz. Requires LOOP + LOOP2 packets."""
    if WG_UID == '' or LPS == False:
        return 'WG_UID not set or LOOP2 data packet unavailable.'
    dataError = wxDict.get('DATAERROR', False)
    if dataError == True:
        return 'Erroneous weather data not being uploaded to WindGURU.cz.'

    base_url = 'https://www.windguru.cz/upload/api.php?'

    params = {
        'stationtype': 'wospi',
        'uid': WG_UID,
        'interval': 300,
        'wind_avg': wxDict['AVGWIND10_KTS'],
        'wind_max': wxDict['GUST10_KTS'],
        'wind_min': wxDict['AVGWIND10_KTS'] / 5,
        'wind_direction': wxDict['WINDDIR'],
        'temperature': wxDict['OUTTEMP_C'],
        'rh': wxDict['OUTHUM_P'],
        'mslp': wxDict['BAROMETER_HPA'],
        'precip': wxDict['RAINFALL15_MM'],
        'precip_interval': 900
    }

    query = urllib.parse.urlencode(params)
    url = base_url + query

    try:
        if DEBUG:
            debugWrite('WindGURU.debug.txt', url)
        z = urllib.request.urlopen(url)
        s = z.read().decode('utf-8')
        z.close()
    except Exception as e:
        sys.exc_info()
        print(tStamp() + 'HTTP GET/WindGURU.cz: making a second attempt.')
        z = urllib.request.urlopen(url)
        s = z.read().decode('utf-8')
        z.close()

    return s


def updateWeatherCloud():
    """Submit data to weathercloud.net. Requires LOOP + LOOP2 packets."""
    if WC_ID == '' or WC_KEY == '' or not LPS:
        return 'WC_ID/WC_KEY not set or LOOP2 data packet unavailable.'

    if wxDict.get('DATAERROR', False):
        return 'Erroneous weather data not being uploaded to weathercloud.net.'

    base_url = 'https://api.weathercloud.net/v01/set?'

    def clean(val):
        return str(val).replace('.', '')

    params = {
        'wid': WC_ID,
        'key': WC_KEY,
        'temp': clean(wxDict['OUTTEMP_C']),
        'hum': wxDict['OUTHUM_P'],
        'wspdavg': clean(wxDict['AVGWIND10_MSEC']),
        'wspd': clean(wxDict['WIND_MSEC']),
        'wspdhi': clean(wxDict['GUST10_MSEC']),
        'wdir': wxDict['WINDDIR'],
        'bar': clean(wxDict['BAROMETER_HPA']),
        'bartrend': wxDict['BAROTREND'],
        'rain': clean(wxDict['DAYRAIN_MM']),
        'rainrate': clean(wxDict['RAINRATE_MMHR']),
        'forecasticon': wxDict['FCICON'],
        'forecast': wxDict['FCRULE'],
        'date': datetime.datetime.now().strftime('%Y%m%d'),
        'time': datetime.datetime.now().strftime('%H%M'),
        'type': 981,
        'version': PROGRAMVERSION,
    }

    # Optional fields with validity checks
    if -40 <= wxDict['DEWPOINT_C'] <= 60:
        params['dew'] = clean(wxDict['DEWPOINT_C'])
    if -40 <= wxDict['WC_C'] <= 60:
        params['chill'] = clean(wxDict['WC_C'])
    if -40 <= wxDict['HINDEX_C'] <= 60:
        params['heat'] = clean(wxDict['HINDEX_C'])
    if -40 <= wxDict['THSW_C'] <= 60:
        params['thw'] = clean(wxDict['THSW_C'])
    if 0 <= wxDict['ET_DAY_MM'] <= 100:
        params['et'] = clean(wxDict['ET_DAY_MM'])
    if 0 <= wxDict['SOLAR_W'] <= 2000:
        params['solarrad'] = str(int(wxDict['SOLAR_W'] * 10))
    if 0 <= wxDict['UVINDEX'] <= 16:
        params['uvi'] = clean(wxDict['UVINDEX'])

    query = urllib.parse.urlencode(params)
    url = base_url + query

    for attempt in range(2):  # try at most twice
        try:
            if DEBUG:
                debugWrite('WeatherCloud.debug.txt', f"Attempt {attempt+1}: {url}")

            with urllib.request.urlopen(url, timeout=10) as z:
                s = z.read().decode('utf-8')
            return s

        except urllib.error.HTTPError as e:
            # Server responded, but with an error code (don’t retry)
            msg = f"HTTPError: {e.code} {e.reason}"
            print(tStamp() + msg)              # log the error
            return str(e.code)

        except urllib.error.URLError as e:
            # Connection issue (retry once)
            print(tStamp() + f"URLError: {e.reason}")
            if attempt == 0:
                print(tStamp() + 'HTTP GET/weathercloud.net: retrying after delay.')
                time.sleep(WXDELAY*10)
                continue
            return "URLERROR"

        except socket.timeout:
            # Explicit timeout handling
            print(tStamp() + "Timeout contacting weathercloud.net")
            if attempt == 0:
                print(tStamp() + "Retrying after delay...")
                time.sleep(WXDELAY * 10)
                continue
            return "TIMEOUT"

        except Exception as e:
            # Unexpected error (don’t retry)
            print(tStamp() + f"Unexpected error: {e}")
            return "EXCEPTION"

    return "FAILED"


if __name__ == '__main__':
    writeVersion()
    socket.setdefaulttimeout(10)
    print('==============================================================================')
    print('STARTING ' + PROGRAMNAME + ' by Torkel M. Jodalen <tmj@bitwrap.no>')
    if LPS:
        print('Using LOOP + LOOP2 packets for WX data (requires console FW version >= 1.90)')
        if APRS == True:
            print('APRS weather reports will be generated')
        if WU_USER != '':
            print('Weather Underground account : ' + WU_USER)
        if WF_StationID != '':
            print('WindFinder.com StationID .. : ' + WF_StationID)
        if WG_UID != '':
            print('WindGURU.cz UID ........... : ' + WG_UID)
        if WC_ID != '':
            print('weathercloud.net ID ....... : ' + WC_ID)
    else:
        print('Using LOOP packets only for WX data')
        print('APRS & Weather Underground output inhibited')
    print('==============================================================================')
    if FORCENTP:
        print('Getting current date and time from NTP server ... ')
        os.system(NTPCOMMAND)
    flashWrite = 0
    errMsg = ''
    upSince = lastError = datetime.datetime.now()
    cnt = 0
    intervalCSV = datetime.timedelta(minutes=CSVINTERVAL)
    prevCSV = datetime.datetime.now() - intervalCSV
    wx = openWxComm()
    try:
        wxWrite('ID')
        time.sleep(WXDELAY)
        idStr = wxRead().strip()
        if not idStr:
            idStr = 'Not available'
        wrdStr = 'WRD' + chr(18) + chr(77)
        wxWrite(wrdStr)
        time.sleep(WXDELAY)
        wrdBytes = wx.in_waiting
        wrdResponse = b''
        if wrdBytes >= 2:
            wrdResponse = wx.read(2)
            if wrdResponse[0] == 0x06:
                stationType = wrdResponse[1]
                wxDict['STATIONMODEL'] = getDavisType(stationType) + ' ID: ' + idStr
                print(tStamp() + 'Console model is %s.' % wxDict['STATIONMODEL'])
            else:
                print(tStamp() + 'No ACK received in response to WRD command.')
                wxDict['STATIONMODEL'] = 'Unknown.'
        else:
            print(tStamp() + 'Ignoring %d WRD bytes received from the console.' % wrdBytes)
            wxDict['STATIONMODEL'] = 'Unknown.'
        setWxTime()
    except Exception as e:
        if hasattr(e, 'value'):
            errMsg = str(sys.exc_info()[0]) + ' / ' + str(e.value)
        else:
            errMsg = str(sys.exc_info()[0])
        sys.exc_info()
        print(tStamp() + 'Unexpected SETTIME error: %s.' % errMsg)

    wxDict['CONDENSATION'] = None
    wxDict['FREEZE'] = None
    import wxshared
    while True:
        try:
            wxDict['DATAERROR'] = False
            wxDict['COMMISSIONDATE'] = COMMISSIONDATE
            dataSize = readWxData()
            if dataSize == 100 and wxDict['CRC-CALC'] == 0:
                blinkOnce()
                cnt += 1
                wxshared.wxDict = wxDict
                if wxDict['BATTERYSTATUS'] != 0:
                    print(tStamp() + 'THE ISS BATTERY SHOULD BE REPLACED NOW !')
                    writeBatteryLog(BATTERYLOGFILE)
                if cnt % 2880 == 0:
                    setWxTime()
                if datetime.datetime.now() - prevCSV >= intervalCSV and wxDict['DATAERROR'] == False:
                    prevCSV = datetime.datetime.now()
                    writeWxDataAsCSV(CSVPATH + lastWxYearMonth + '-' + CSVFILESUFFIX)
                    storeRainAsCSV()
                    wxMinMax['SOCTEMP'] = ''
                    if TEMPERATURECOMMAND != '':
                        os.system(TEMPERATURECOMMAND)
                        f = open(TEMPERATUREFILE, 'r')
                        wxMinMax['SOCTEMP'] = f.readline().strip()
                        print(tStamp() + 'SoC Temperature is %s deg. C.' % wxMinMax['SOCTEMP'])
                        f.close()
                    if APRS == True and LPS == True:
                        writeUIViewFile(UIFILE)
                    hiLows()
                    writeWxMinMaxAsText(MINMAXFILE)
                    wxshared.wxMinMax = wxMinMax
                    writeWxIconFile(ICONFILE)
                    print(tStamp() + 'Initiating SCP file transfer of ' + MINMAXFILE + '...')
                    os.system(SCPCOMMAND_MINMAX)
                    print(tStamp() + 'Initiating SCP file transfer of ' + ICONFILE + '...')
                    os.system(SCPCOMMAND_ICON)
                    if APRS == True and LPS == True:
                        print(tStamp() + 'Initiating SCP file transfer of ' + UIFILE + '...')
                        os.system(SCPCOMMAND_UIFILE)
                    sunTimes()
                    plotData()
                    print(tStamp() + 'Initiating SCP file transfer of ' + PLOT24FILE + '...')
                    os.system(SCPCOMMAND_PLOT24FILE)
                    os.system('rm ' + PLOT24FILE)
                    print(tStamp() + 'Initiating SCP file transfer of ' + PLOT24WIND + '...')
                    os.system(SCPCOMMAND_PLOT24WIND)
                    os.system('rm ' + PLOT24WIND)
                    print(tStamp() + 'Initiating SCP file transfer of ' + PLOTRAINMONTH + '...')
                    os.system(SCPCOMMAND_PLOTRAINMONTH)
                    os.system('rm ' + PLOTRAINMONTH)
                    print(tStamp() + 'Initiating SCP file transfer of ' + PLOTRAINDMONTH + '...')
                    os.system(SCPCOMMAND_PLOTRAINDMONTH)
                    os.system('rm ' + PLOTRAINDMONTH)
                    print(tStamp() + 'Initiating SCP file transfer of ' + PLOTRAINPERMONTH + '...')
                    os.system(SCPCOMMAND_PLOTRAINPERMONTH)
                    os.system('rm ' + PLOTRAINPERMONTH)
                    if WU_USER != '':
                        print(tStamp() + 'HTTP GET request to Weather Underground...')
                        WUresponse = updateWUnderground()
                        if WUresponse.strip() != 'success':
                            print(tStamp() + 'Weather Underground ERROR: ' + WUresponse)
                        else:
                            print(tStamp() + 'Weather Underground account "' + WU_USER + '" updated.')
                    if WF_StationID != '':
                        print(tStamp() + 'HTTP GET request to WindFinder.com...')
                        WFresponse = updateWindFinder()
                        if WFresponse.find('\nOK\n') >= 0:
                            print(tStamp() + 'WindFinder.com account "' + WF_StationID + '" updated.')
                        else:
                            print(tStamp() + 'WindFinder.com ERROR: ' + WFresponse)
                    if WC_ID != '':
                        # only run updateWeatherCloud if intervall passed
                        if should_update_weathercloud():
                            print(tStamp() + 'HTTP GET request to weathercloud.net...')
                            WCresponse = updateWeatherCloud()
                            if WCresponse.find('200') >= 0:
                                print(tStamp() + 'weathercloud.net account "' + WC_ID + '" updated.')
                                record_wc_update()  # remember the time of this successful update
                            elif WCresponse.find('429') >= 0:
                                print(tStamp() + 'weathercloud.net ERROR: too many requests (' + WCresponse + ').')
                            elif WCresponse.find('401') >= 0:
                                print(tStamp() + 'weathercloud.net ERROR: wrong WID and/or Key (' + WCresponse + ').')
                            elif WCresponse.find('400') >= 0:
                                print(tStamp() + 'weathercloud.net ERROR: bad request (' + WCresponse + ').')
                            else:
                                print(tStamp() + 'weathercloud.net ERROR: other (' + WCresponse + ').')
                        else:
                            print(tStamp() + 'Weathercloud.net update skipped (interval not reached).')
                    try:
                        runNotSoOften()
                    except Exception as e:
                        print(tStamp() + 'Exception occured in user-defined function runNotSoOften. Check your code.')

                writeWxDataAsText(OUTFILE)
                writeXML(XMLFILE)
                print(tStamp() + 'Initiating SCP file transfer of ' + OUTFILE + '...')
                os.system(SCPCOMMAND_WX)
                print(tStamp() + 'Initiating SCP file transfer of ' + XMLFILE + '...')
                os.system(SCPCOMMAND_XML)
                if cnt == 1 or cnt % 10 == 0:
                    if WG_UID != '':
                        print(tStamp() + 'HTTP GET request to WindGURU.cz...')
                        WGresponse = updateWindGURU()
                        if WGresponse.find('OK') >= 0:
                            print(tStamp() + 'WindGURU.cz account "' + WG_UID + '" updated.')
                        else:
                            print(tStamp() + 'WindGURU.cz ERROR: ' + WGresponse)
                try:
                    runOften()
                except Exception as e:
                    print(tStamp() + 'Exception occured in user-defined function runOften. Check your code.')

                print(tStamp() + 'FLASH memory write count since program start: %d. ' % flashWrite)
                print(tStamp() + 'Waiting...')
            elif dataSize == 0 or dataSize == None:
                print(tStamp() + 'Waiting...')
            else:
                print(tStamp() + 'Invalid LOOP1 or LOOP2 packet or CRC error. dataSize = %s' % dataSize)
                print(tStamp() + 'Invalid LOOP packet or CRC error. wxDict["CRC-CALC"] = %s' % wxDict['CRC-CALC'])
                print(tStamp() + 'Waiting...')
        except KeyError as e:
            errMsg = str(e.args[0])
            print(tStamp() + 'Dictionary KeyError: ' + errMsg)
            lastError = datetime.datetime.now()
            cnt += 1
            sys.exc_info()
            print(tStamp() + 'Waiting...')
        except IOError as e:
            errMsg = f"IOError: {type(e).__name__} {e}"
            print(tStamp() + errMsg)
            lastError = datetime.datetime.now()
            cnt += 1
            sys.exc_info()
            print(tStamp() + 'Waiting...')
        except Exception as e:
            if hasattr(e, 'value'):
                errMsg = str(sys.exc_info()[0]) + ' / ' + str(e.value)
            else:
                errMsg = str(sys.exc_info()[0])
            sys.exc_info()
            print(tStamp() + 'Unexpected error: ' + errMsg)
            print(tStamp() + 'Resetting COM, waiting...')
            lastError = datetime.datetime.now()
            cnt += 1
            if wx != None:
                wx.close()
            time.sleep(0.3)
            wx = None
            time.sleep(0.3)

        time.sleep(30)
        os.system('clear')
        timeDelta = datetime.datetime.now() - upSince
        deltaDays = timeDelta.days // 1
        deltaMins = timeDelta.seconds // 60
        deltaHrs = timeDelta.seconds // 3600
        deltaMins -= deltaHrs * 60
        deltaSecs = timeDelta.seconds - deltaMins * 60 - deltaHrs * 3600
        deltaStr = '%d days, %d hours, %d minutes, %d seconds' % (deltaDays, deltaHrs, deltaMins, deltaSecs)
        print(tStamp() + 'Running since ' + upSince.ctime() + ' LT (' + deltaStr + '). Cycle = %d.' % cnt)
        uptime = 'Running since ' + upSince.ctime() + ' LT (' + deltaStr + '). Cycle = %d.' % cnt
        if upSince != lastError:
            print(tStamp() + 'Last error occured on ' + lastError.ctime() + ' LT (' + errMsg + ').')
        if cnt >= REBOOTINTERVAL:
            print(tStamp() + 'Now rebooting.')
            cnt = 0
            wx.close()
            os.system(REBOOTCOMMAND)
        if wx == None:
            wx = openWxComm()
            try:
                setWxTime()
            except Exception as e:
                print(tStamp() + 'This message should never be displayed.')

    wx.close()
