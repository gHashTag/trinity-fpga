import serial, time

ser = serial.Serial('/dev/cu.usbserial-2140', 115200, timeout=1)
time.sleep(0.5)
ser.write(b'aaaa\r\n')
time.sleep(0.5)
data = ser.read(100)
ser.close()

print('UART RX:', repr(data))
