#!/usr/bin/env python
#
# Author: Loris Reiff
# Maturaarbeit
#
from __future__ import print_function
import sys
import time
import hashlib
import logging
import binascii
import glob
from functools import partial
from py2_3 import *
from CirrolusPeer import *
from CirrolusFiles import *
try:
    from readyAES import *
    AESSUPPORT = True
except ImportError:
    AESSUPPORT = False


# go to path of the file
os.chdir(os.path.dirname(os.path.realpath(__file__)))

logging.basicConfig(
        filename="Cirrolus-Connection.log",
        filemode="w",
        format="%(name)s %(asctime)s %(message)s",
        level=logging.INFO)
logger = logging.getLogger("CirrolusPeer")


USAGE = """Usage: {} USERNAME [port]""".format(sys.argv[0])
HELPTEXT = {
         "download": "download FILE",
         "getuser":  "getuser",
         "join":     "join IP [PORT]",
         "leave":    "leave",
         "list":     "list",
         "search":   "search [FILENAME]",
         "setuser":  "setuser NAME",
         "upload":   "upload FILE [p]",
}


def parse(peerObject, user, opt):
    action, values = opt.split()[0], opt.split()[1:]
    action = action.lower()
    if action == 'setuser':
        try:
            newname = values[0]
            setUser(newname)
        except IndexError:
            print(HELPTEXT[action])
    elif action == 'getuser':
        print(user)
    elif action == 'join':
        peer = parseJoin(values)
        try:
            peerObject.joinNet0(peer)
            print("Joined")
            print(peerObject.peers)
        except ConnectionRefusedError:
            print("Connection refused")
        except:
            print("Didn't connect")
            print(HELPTEXT[action])
    elif action == 'upload':
        try:
            private = bool(values[1])
        except IndexError:
            private = False
        try:
            filename = values[0]
            if private and AESSUPPORT:
                password = input("Password: ")
                filename = encryptFile(filename, password)
            elif private and not AESSUPPORT:
                raise RuntimeError("PyCrypto not installed!")
            s = upload(peerObject, filename, user, private)
            if s >= 4:
                print("Successful: {} fragments uploaded".format(s))
            else:
                print("Not successful, to few peers")
        except IndexError:
            print(HELPTEXT[action])
        except FileNotFoundError:
            print("File not found!")
        except RuntimeError as e:
            print(str(e))
    elif action == 'search':
        try:
            filename = values[0]
        except IndexError:
            filename = None
        result = search(peerObject, filename, user)
        try:
            result = result[user]
            printSearch(result, user)
        except KeyError:
            print("Nothing found")
    elif action == 'list':
        print(peerObject.peers)
    elif action == 'leave':
        leave(peerObject)
    elif action == 'download':
        try:
            filename = values[0]
        except IndexError:
            print(HELPTEXT[action])
        download(peerObject, filename, user)
    elif action == 'help':
        printHelpText()
    else:
        print("Unknown command")


def printHelpText():
    global HELPTEXT
    text = "Follwing commands exist:\n\t"
    text += "\n\t".join(HELPTEXT.values())
    print(text)


def encryptFile(filename, password):
    encryptedFile = "./cache/" + os.path.split(filename)[-1]
    assert encryptedFile != filename
    data = b''
    with open(filename, 'rb') as f:
        for b in iter(partial(f.read, 512), b''):
            data = b''.join((data, b))
    salt = hashlib.sha256(filename.encode()).digest()
    key = genKey(password, salt)
    cipher = AESCipher(key)
    data = cipher.encrypt(data)
    with open(encryptedFile, 'wb') as f:
        f.write(data)
    return encryptedFile


def setUser(newname):
    global user
    user = newname


def parseJoin(values):
    try:
        if len(values) == 1:
            ip = values[0]
            port = 50666
        elif len(values) >= 2:
            ip = values[0]
            port = int(values[1])
        else:
            return None
        return (ip, port)
    except ValueError:
        return None


def calculateAmountFragments(peerObject):
    """
    returns how many fragments should be created
    0 if there aren't enough
    """
    if len(peerObject.peers) >= 20:
        return int(len(peerObject.peers)*0.8)
    elif len(peerObject.peers) < 4:
        return 0
    else:
        return len(peerObject.peers)


def upload(peerObject, filename, user, private):
    """
    Uploads file 'filename'
    returns number of successful uploads
    """
    n = calculateAmountFragments(peerObject)
    if not n:
        return 0
    files = createFragments(filename, n, uploader=user, private=private)
    failed = []
    peers = peerObject.getRandomPeers(len(peerObject.peers))
    for i in range(n):
        try:
            data = b''
            with open(files[i], 'rb') as f:
                for b in iter(partial(f.read, 512), b''):
                    data = b''.join((data, b))
            if not peerObject.uploadFragment0(peers[i], data):
                failed.append(files[i])
        except IOError:
            failed.append(files[i])
        except IndexError:
            break
    return n - len(failed)


def search(peerObject, filename, user):
    if filename is not None:
        hash = hashlib.sha256(filename.encode()).digest()
    else:
        hash = 32 * b'\x00'
    peerObject.searchRequest0(hash, user)
    result = peerObject.latestSearchResults.copy()
    peerObject.latestSearchResults = {}
    return result


def leave(peerObject):
    peerObject.leaveNet0()
    p.running = False


def download(peerObject, filename, user):
    result = search(peerObject, filename, user)
    try:
        result = result[user]
    except IndexError:
        print("No such file found")
        return -1
    if len(result) > 1:
        printSearch(result, user)
        while True:
            try:
                toDownload = int(input("\tThere are more files with the \
same name, choose one:")) - 1
                if toDownload < 0:
                    continue
                toDownload = list(result.keys())[toDownload].encode()
                break
            except (ValueError, IndexError):
                continue
    elif len(result) < 1:
        print("No such file found")
        return -1
    else:
        toDownload = list(result.keys())[0].encode()
    hash = binascii.unhexlify(toDownload)
    toDownload = "./cache/save/{}/*".format(toDownload.decode())
    for i in peerObject.peers:
        peerObject.requestFragment0(i, hash, user.encode())
        if len(glob.glob(toDownload)) >= 4:
            break
    fragments = glob.glob(toDownload)
    if len(fragments) >= 4:
        print("Fragments downloaded")
        print("Starts combining")
        data, private = combineFragments(fragments)
        if private:
            password = input("Password: ")
            salt = hashlib.sha256(filename.encode()).digest()
            key = genKey(password, salt)
            cipher = AESCipher(key)
            data = cipher.decrypt(data)
        dir = "./download"
        makeDir(dir)
        with open("{}/{}".format(dir, filename), 'wb') as f:
            f.write(data)
        print("Finished")
    else:
        print("Not enough fragments!")


def printSearch(result, user):
    print(80*"-")
    k = 1
    for key, value in result.items():
        print(k, ".)", sep='')
        print("{} : {}".format(key, value))
        k += 1
    print(80*"-")


def stabilize(peerObject, interval=60):
    """
    Checks all 'interval' seconds if all peers are available
    """
    while peerObject.running:
        for i in peerObject.peers:
            peerObject.checkPeer0(i)
        for i in range(interval):   # sleep interval and stop
            time.sleep(1)           # thread if peerObject stopped running
            if not peerObject.running:
                break


try:
    user = sys.argv[1]
    if user.lower() == "-h":
        raise RuntimeError("print Help")
except IndexError:
    user = input("Username: ")
except:
    print(USAGE)
    sys.exit(-1)
try:
    port = int(sys.argv[2])
except IndexError:
    port = 50666

p = CirrolusPeerV1("127.0.0.1", port, logger=logger)
t = threading.Thread(target=p.run)
t1 = threading.Thread(target=stabilize, args=(p,))
t.start()
time.sleep(0.2)
t1.start()
printHelpText()

while p.running:
    userInput = input("> ").strip()
    if userInput:
        parse(p, user, userInput)
