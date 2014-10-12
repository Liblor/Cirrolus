import os
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
import bytesSupport as bs


def genKey(password, salt, keySize=32, iterations=12000):
    try:
        password = password.encode()
    except AttributeError:
        pass
    try:
        salt = salt.encode()
    except (AttributeError, UnicodeDecodeError):
        pass
    return PBKDF2(password, salt, keySize, iterations)


class AESCipher(object):
    def __init__(self, key):
        self.blockSize = 32
        assert len(key) >= 32
        self.key = key[:32]

    def encrypt(self, raw):
        raw = self._pad(raw)
        iv = os.urandom(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return iv + cipher.encrypt(raw)

    def decrypt(self, enc):
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[AES.block_size:]))

    def _pad(self, s):
        return s + (self.blockSize - len(s) % self.blockSize) \
            * bs.int2byte(self.blockSize - len(s) % self.blockSize)

    def _unpad(self, s):
        return s[:-bs.byte2int(s[len(s)-1:])]
