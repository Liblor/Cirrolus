import sys
import socket

if sys.version > '3':
    integer_types = (int, )
else:
    integer_types = (int, long)
    range = xrange
    input = raw_input
    FileNotFoundError = IOError
    BlockingIOError = socket.error
    ConnectionRefusedError = socket.error
