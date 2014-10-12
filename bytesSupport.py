#
# Author: Loris Reiff
# Maturaarbeit
# Python 2 ByteSupport

import sys

if sys.version > '3':
    def int2byte(n):
        return bytes((n,))

    def byte2int(source, index=0):
        return source[index]

#    def minByteSize(x):
#        i = 0
#        while x:
#            i += 1
#            x //= 256
#        return i

    def int2bytes(n, size, endian='big'):
        return n.to_bytes(size, endian)

    def bytes2int(b, endian='big'):
        return int.from_bytes(b, endian)

else:
    def int2byte(n):
        return chr(n)

    def byte2int(source, index=0):
        return ord(source[index])

    def int2bytes(n, size=0, endian='big'):
        out = b''
        while n > 0:
            n, byte = divmod(n, 256)
            out = b''.join((out, chr(byte)))
        if len(out) < size:
            times = size - len(out)
            out = b''.join((out, times * '\x00'))
        if endian == 'big':
            out = out[::-1]
        return out

    def bytes2int(b, endian='big'):
        x = 0
        if endian == 'big':
            b = b[::-1]
        for i in range(len(b)):
            x += ord(b[i]) * 256 ** i
        return x
