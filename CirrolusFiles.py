#
# Author: Loris Reiff
# Maturaarbeit
#

from functools import partial
import hashlib
import os
import json
import random
import glob
from SimplePolynomial import SimplePolynomial
from py2_3 import *
import bytesSupport as bs


class FragmentManager(object):
    def __init__(self):
        self.prefixes = (b"#CL\x00", )

    def isFragment(self, data):
        """returns True if it's a Cirrolus fragment"""
        return data[:4] in self.prefixes

    def getMeta(self, data):
        """
        returns the meta dictionary
        """
        metaSize = bs.bytes2int(data[4:8])
        meta = json.loads(data[8:(8+metaSize)].decode())
        return meta

    def saveFile(self, name, data):
        with open(name, 'wb') as f:
            f.write(data)

    def saveFragment(self, data, cached=False):
        """
        If data is a Cirrolus fragment, it will be saved in a folder
        named after the uploader and true will be returned. If cached is set,
        the fragment will be stored in the cache folder. If it isn't a fragment
        false will be returned.
        """
        if self.isFragment(data):
            meta = self.getMeta(data)
            if cached:
                dir = "./cache/save/{}/".format(meta["hash"])
                filename = str(meta["x"])
            else:
                dir = "./{}/".format(meta["uploader"])
                filename = "".join((meta["hash"], meta["filename"]))
            makeDir(dir)
            self.saveFile(dir + filename, data)
            return True
        else:
            return False

    def getFragment(self, username, hashOfFile):
        """
        Returns the data of the fragment in the folder username that begins
        with 'hashOfFile'.
        """
        data = b''
        files = glob.glob("{}/{}?*".format(username, hashOfFile))
        if len(files) != 1:
            raise FileNotFoundError
        with open(files[0], 'rb') as f:
            for b in iter(partial(f.read, 1024), b''):
                data += b
        return data

    def getFragmentDict(self, username, hashfilename=None):
        """
        returns a dictionary of the fragments from 'username'. The key is
        the hash of the file, the value the hashfilename
        """
        files = [i for i in os.listdir(username) if len(i) == 128]
        if hashfilename:
            files = [i for i in files if i[64:] == hashfilename]
        out = {}
        for i in files:
            out[i[:64]] = i[64:]
        return out


def makeDir(dir):
    """
    Make dir if it doesn't exist.
    """
    if not os.path.exists(dir):
        os.makedirs(dir)


def lagrange(coordinates, moduloPrime):
    """
    Lagrange Interpolation modulo 'moduloPrime'
    """
    sum_ = 0
    for i in coordinates:
        temp = i[1]
        for j in coordinates:
            if i != j:
                # inverse according to fermats little theorem
                temp *= SimplePolynomial([-j[0], 1]) * \
                     pow(i[0] - j[0], moduloPrime - 2, moduloPrime)
        sum_ += temp
        sum_ %= moduloPrime
    return sum_


def calcBytesToAdd(filename, chunksize=128):
    """
    returns how many bytes have to be added, that the file 'filename' is
    a multiple of 'chunksize'
    """
    size = os.path.getsize(filename)
    toAdd = chunksize - (size % chunksize)
    return toAdd


def checksumSha256(filename):
    """
    returns the hex SHA256 of the file filename
    """
    hash = hashlib.sha256()
    with open(filename, 'rb') as f:
        for b in iter(partial(f.read, 2 ** 10), b''):
            hash.update(b)
    return hash.hexdigest()


def allEqual(L):
    """
    Checks whether all elements of L are equal
    """
    return L.count(L[0]) == len(L)


def createPolynomials(file_, toAdd, chunksize=128, blocksize=32):
    """
    Creates a list of polynomes out of a file_
    """
    randomJunk = os.urandom(toAdd)
    polynomes = []
    coeff = []
    with open(file_, 'rb') as f:
        for b in iter(partial(f.read, chunksize), b''):
            if len(b) < 128:
                b += randomJunk
            for i in range(0, chunksize, blocksize):
                coeff.append(bs.bytes2int(b[i:i+blocksize], 'big'))
            polynomes.append(SimplePolynomial(coeff))
            coeff = []
    return polynomes


def readFragment(file_, piecesize=33):
    """
    Reads the fragment file_ and returns the meta dictionary and a list of the y values
    """
    with open(file_, 'rb') as f:
        if f.read(4) == b"#CL\x00":
            metaSize = bs.bytes2int(f.read(4))
            meta = json.loads(f.read(metaSize).decode())
            y = []
            for b in iter(partial(f.read, piecesize), b''):
                y.append(bs.bytes2int(b))
        else:
            raise RuntimeError("{} is not a Cirrolus fragment".format(file_))
    return (meta, y)


def readListOfFragments(fragmentFilenames):
    """
    Reads a list of fragments and returns the metas and the lists of the pieces
    """
    metas = []
    pieceLists = []
    for i in fragmentFilenames:
        meta, piece = readFragment(i)
        metas.append(meta)
        pieceLists.append(piece)
    return metas, pieceLists


def createFragments(file_, amount, directory="cache/upload",
                    prime=2 ** 261 - 261, chunksize=128, version=0,
                    **meta):
    """
    Creates Fragments and returns a list of storage location

    meta:
    -----
    filename - SHA256 of filename
    uploader - Username of uploader
    private
    """
    assert amount >= 4
    makeDir(directory)
    files = []
    header = b"#CL" + bs.int2byte(version)
    bytesToAdd = calcBytesToAdd(file_)
    if "filename" not in meta:
        filename = os.path.split(file_)[-1].encode()
        meta["filename"] = hashlib.sha256(filename).hexdigest()
    meta["added_bytes"] = bytesToAdd
    meta["hash"] = checksumSha256(file_)
    polynomes = createPolynomials(file_, bytesToAdd)
    xValues = random.sample(range(1, 1000000000000000000), amount)
    for x in xValues:
        currentMeta = meta.copy()
        currentMeta["x"] = x
        currentMeta = json.dumps(currentMeta).encode()
        currentMeta = b''.join((bs.int2bytes(len(currentMeta), 4), currentMeta))
        pieces = b''
        for i in range(len(polynomes)):
            pieces += bs.int2bytes(polynomes[i](x, prime), 33)
        tempFragmentName = "{}/{}".format(directory,
                                          meta["filename"][:14] + str(x))
        files.append(tempFragmentName)
        with open(tempFragmentName, 'wb') as f:
            f.write(b''.join((header, currentMeta, pieces)))
    return files


def combineFragments(fragmentFilenames, prime=2 ** 261 - 261):
    """
    Combines all fragments given to the file they represent.
    returns file and a boolean if it's a private/encrypted file
    """
    assert len(fragmentFilenames) >= 4
    metas, yLists = readListOfFragments(fragmentFilenames)
    if not allEqual([i["hash"] for i in metas]):
        raise RuntimeError("Fragments don't belong together - unequal hashes")
    n = len(yLists[0])
    out = []
    for i in range(n):
        coordinates = [(metas[j]["x"], yLists[j][i]) for j in range(len(yLists))]
        polynom = lagrange(coordinates, prime)
        out.extend(polynom.coefficients)
    out = [bs.int2bytes(i, 32) for i in out]
    out = b''.join(out)
    try:
        private = metas[0]["private"]
    except KeyError:
        private = False
    return (out[:-metas[0]["added_bytes"]], private)


if __name__ == '__main__':
    import sys
    import time

    usage = """Usage: {} [OPTION] ...

Split File:
    -s FILE
Restore:
    -c OUTPUT F1 F2 F3 F4
""".format(sys.argv[0])

    try:
        if sys.argv[1].lower() == '-s' and len(sys.argv) == 3:
            createFragments(sys.argv[2], 4, uploader="test")
        elif sys.argv[1].lower() == '-c' and len(sys.argv) == 7:
            start = time.time()
            data, private = combineFragments(sys.argv[3:])
            print("Time: ", time.time() - start)
            with open(sys.argv[2], 'wb') as f:
                f.write(data)
        else:
            print(usage)
    except IndexError:
        print(usage)
    except FileNotFoundError:
        print("File(s) not found!")
        sys.exit(-1)
