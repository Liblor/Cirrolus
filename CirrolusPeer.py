#
# Author: Loris Reiff
# Maturaarbeit
#
from __future__ import print_function
import logging
import socket
import select
import struct
import random
import threading
import time
import binascii
import json
import bytesSupport as bs
import CirrolusFiles as cf
from py2_3 import *


class CirrolusPeerCore(object):
    def __init__(self, host, port=50666, logger=None):
        self.host = host
        self.port = port
        self.peers = []
        self.running = False
        self.lock = threading.Lock()
        self.version = None
        # versionHandlers
        # the key is the version, the value a handler-dictionary
        # that includes all the different message IDs and their function
        self.versionHandlers = {}
        self.buffersize = 4096
        self.fileManager = cf.FragmentManager()
        self.logger = logger or logging.getLogger(__name__)

    def _startserver(self):
        """Starts a server that is listening on self.host:self.port"""
        self.logger.info("Start server: {}:{}".format(self.host, self.port))
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        self.logger.info("Server started")

    def _handlePeer(self, connection):
        """
        Handles the event if a peer connects to the server
        """
        self.logger.info("Process started: {}".format(threading.current_thread().name))
        self.logger.info("Connected: {}".format(connection.getpeername()))

        message = self.receive(connection)
        self.handleAccordingly(connection, message)
        connection.close()

    def handleAccordingly(self, connection, message, expectedId=None):
        """
        If the message is a Cirrolus message and the expected ID is confirmed,
        the matching handler function is called and True returned. Therefore
        an item in versionHandlers has to match to the message's Version.
        Futhermore the value of versionHandlers has to contain an item with
        the message ID of the message. If expectedId is not None it also has
        to match to expectedId. Otherwise it returns False.
        """
        handlerFound = False
        if self.isCirrolus(message):
            version, messageId, payload = self.unpackMessage(message)
            self.logger.debug("""
                Version: {}
                ID: {}
                Payload: {}""".format(version, messageId, payload))
            try:
                if messageId == expectedId or expectedId is None:
                    self.versionHandlers[version][messageId](connection, payload)
                    handlerFound = True
            except KeyError:
                pass
        return handlerFound

    def addPeer(self, peer):
        """
        Locks self.peers and adds a new peer
        """
        if peer not in self.peers and \
           peer != (self.host, self.port):
            self.logger.info("add {} to {}".format(peer, self.peers))
            with self.lock:
                self.peers.append(peer)

    def removePeer(self, peer):
        """
        Locks self.peers and removes a peer
        """
        if peer in self.peers:
            self.logger.info("remove {} from {}".format(peer, self.peers))
            with self.lock:
                del self.peers[self.peers.index(peer)]

    def isCirrolus(self, message):
        try:
            prefix = struct.unpack("!2s", message[:2])[0].decode()
        except struct.error:
            return False
        if len(message) > 3 and prefix == "CL":
            return True
        else:
            return False

    def packMessage(self, version, messageId, payload=b''):
        message = b''.join((b'CL', bs.int2byte(version), bs.int2byte(messageId), payload))
        return message

    def unpackMessage(self, message):
        version = bs.byte2int(message, 2)
        messageId = bs.byte2int(message, 3)
        payload = message[4:]
        return version, messageId, payload

    def connectToServer(self, peer):
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        connection.connect(peer)
        return connection

    def send(self, connection, messageId, payload):
        """
        Sends a Cirrolus message to the peer that is connected to connection.
        """
        msg = self.packMessage(self.version, messageId, payload)
        try:
            connection.sendall(msg)
            self.logger.info("Send something")
            self.logger.debug("Send {} to {}".format(msg, connection.getpeername()))
        except BrokenPipeError:
            self.logger.info("Sendig failed")

    def receive(self, connection, timeout=4):
        """
        Waits timeout seconds for a message from the peer connected to
        connection and returns the data. If message is sent during timeout
        an empty byte is returned (b'').
        """
        connection.setblocking(0)  # make sure that recv never blocks for ever
        ready = select.select([connection], [], [], timeout)
        data = b''
        if ready[0]:
            data = connection.recv(self.buffersize)
            if len(data) > 1024:    # this means it isn't a small msg
                if self.isCirrolus(data):
                    version, messageId, payload = self.unpackMessage(data)
                    # only those messages have the size at this position
                    if messageId in (3, 6, 8):
                        size = struct.unpack("!I", payload[:4])[0]
                        # len(data) - 8 because: prefix + 4 bytes for size = 8
                        while size > (len(data) - 8):
                            try:
                                data += connection.recv(self.buffersize)
                            except socket.error:    # OS X may raise Error
                                pass
                        data = data[:size + 8]
        connection.setblocking(1)  # go back to blocking mode
        return data

    def getRandomPeers(self, n):
        if n > len(self.peers):
            n = len(self.peers)
        return random.sample(self.peers, n)

    def run(self):
        """
        self.run() will start a server and will listen on the address of
        the object.
        It will run as long as self.running is True. If a client connects,
        a new thread that handles the peer starts -> self._handlePeer
        """
        self._startserver()
        self.running = True
        self.server.settimeout(2)
        while self.running:
            try:
                connection, clientaddress = self.server.accept()
                thread = threading.Thread(target=self._handlePeer, args=(connection,))
                thread.start()
            except socket.timeout:
                pass
            except Exception:
                self.logger.error("Unknown error", exc_info=True)

        self.server.close()
        self.logger.info("Stopped listening")


class CirrolusPeerV1(CirrolusPeerCore):
    def __init__(self, host, port=50666, logger=None):
        CirrolusPeerCore.__init__(self, host, port, logger)
        self.version = 0
        self.latestSearchResults = {}
        self.handlersV1 = {
            0: self._handlejoinNet0,
            1: self._handleLeaveNet0,
            2: self._handleRequestPeerList0,
            3: self._handleUploadFragment0,
            4: self._handleUploadReport0,
            5: self._handlerequestFragment0,
            6: self._handleSendFragment0,
            7: self._handleSearchRequest0,
            8: self._handleSearchResults0,
            255: self._handleCheckPeer0,
        }
        self.versionHandlers[self.version] = self.handlersV1

    def packPeers(self, peers):
        """
        All known peers are packed according to the pattern for sharing peers.
        |n| [n x | IP | Port |]
        1B          n x 6B
        """
        n = bs.int2byte(len(peers))
        return n + b''.join(map(lambda x: socket.inet_aton(x[0])
            + struct.pack("!H", x[1]), peers))

    def unpackPeers(self, payload):
        """
        Unpacks peers who are received from an other peer.
        """
        n = bs.byte2int(payload, 0)
        peers = [None]*n
        for i in range(0, n):
            ip = socket.inet_ntoa(payload[(6*i+1):(6*i+5)])
            port = struct.unpack("!H", payload[(6*i+5):(6*i+7)])[0]
            peers[i] = (ip, port)
        return peers

    def _handlejoinNet0(self, connection, payload):
        """
        Handles a version 0 join request and replies if the peer list is
        demanded.
        """
        port = struct.unpack("!H", payload[:2])[0]
        try:
            reply = bs.byte2int(payload, 2)
        except IndexError:
            reply = False
        if reply:
            self.sharePeers0(connection)
        address = (connection.getpeername()[0], port)
        self.addPeer(address)

    def _handleLeaveNet0(self, connection, payload):
        """
        Handles the version 0 leave message from another peer. Speak, the peer
        is removed from the list.
        """
        port = struct.unpack("!H", payload)[0]
        peer = (connection.getpeername()[0], port)
        self.removePeer(peer)

    def _handleRequestPeerList0(self, connection, payload):
        """
        Acts accordingly to the version 0 protocol if a peer list has to be
        handled. A join message is sent to every new peer in the list.
        """
        newPeers = self.unpackPeers(payload)
        self.logger.info("List of received peers: {}".format(newPeers))
        for i in newPeers:
            if i not in self.peers:
                self.joinNet0(i, getPeers=False)

    def _handleUploadFragment0(self, connection, payload):
        """
        Saves the received fragment if possible and replies with a upload
        report.
        """
        n = struct.unpack("!I", payload[:4])[0]
        successful = False
        if n <= len(payload[4:]):
            successful = self.fileManager.saveFragment(payload[4:4+n])
            self.logger.info("Saving file: " + str(successful))
        self.uploadReport0(connection, successful=successful)

    def _handleUploadReport0(self, connection, payload):
        """
        Handles the received upload report, if the report contains a error
        a IOError is thrown.
        """
        successful = False
        try:
            successful = bs.byte2int(payload, 0)
        except IndexError:
            pass
        if not successful:
            raise IOError("Sending fragment failed")

    def _handlerequestFragment0(self, connection, payload):
        hashfile = binascii.hexlify(payload[:32]).decode()
        n = bs.byte2int(payload, 33)
        if n:
            name = payload[33:33+n].decode()
            self.logger.info("Handle request fragment")
            self.logger.debug("request: {} | {}".format(hashfile, name))
            try:
                fragment = self.fileManager.getFragment(name, hashfile)
                self.sendFragment0(connection, fragment)
            except FileNotFoundError:
                self.sendFragment0(connection)
        else:
            self.sendFragment0(connection)

    def _handleSendFragment0(self, connection, payload):
        self.logger.info("Handle send fragment")
        if len(payload) >= 4:
            n = struct.unpack("!I", payload[:4])[0]
        else: n = 0
        if n == 0:
            raise FileNotFoundError
        elif n <= len(payload[4:]):
            self.fileManager.saveFragment(payload[4:4+n], cached=True)
        else:
            raise FileNotFoundError

    def _handleSearchRequest0(self, connection, payload):
        if payload[:32] != bs.int2bytes(0, 32):
            hashfilename = binascii.hexlify(payload[:32]).decode()
        else:
            hashfilename = None
        n = bs.byte2int(payload, 33)
        if n:
            username = payload[33:33+n].decode()
            self.searchResults0(connection, hashfilename, username)

    def _handleSearchResults0(self, connection, payload):
        try:
            n = struct.unpack("!I", payload[:4])[0]
        except IndexError:
            return None, {}
        data = json.loads(payload[4:4+n].decode())
        user = data["username"]
        if user not in self.latestSearchResults:
            self.latestSearchResults[user] = {}
        self.latestSearchResults[user].update(data["files"])

    def _handleCheckPeer0(self, connection, payload):
        """
        MessageID 255
        Sends CheckPeer Message back
        """
        self.send(connection, 255, b'')

    def joinNet0(self, peer, getPeers=True):
        """
        Sends a join message to 'peer'. If getPeers is set, it will be
        waiting for a reply (timeout).
        """
        try:
            connection = self.connectToServer(peer)
            port = struct.pack("!H", self.port)
            reply = b'\xff' if getPeers else b''
            payload = b''.join((port, reply))
            self.send(connection, 0, payload)
            if getPeers:
                reply = self.receive(connection)
                self.handleAccordingly(connection, reply, 2)
            if peer not in self.peers:
                self.addPeer(peer)
        finally:
            try:
                connection.close()
            except:
                pass

    def leaveNet0(self):
        """
        A leave message is sent to every peer known.
        """
        for peer in self.peers:
            try:
                connection = self.connectToServer(peer)
            except ConnectionRefusedError:
                continue
            try:
                payload = struct.pack("!H", self.port)
                self.send(connection, 1, payload)
            finally:
                connection.close()

    def sharePeers0(self, connection):
        """
        Shares all known peers to connected peer.
        """
        peers = self.packPeers(self.peers)
        self.send(connection, 2, peers)

    def uploadFragment0(self, peer, fragment):
        try:
            connection = self.connectToServer(peer)
        except ConnectionRefusedError:
            self.removePeer(peer)
            self.logger.info("Could not upload fragment")
            return False
        try:
            n = struct.pack("!I", len(fragment))
            payload = b''.join((n, fragment))
            self.send(connection, 3, payload)
            reply = self.receive(connection, 10)
            return self.handleAccordingly(connection, reply, 4)
        finally:
            connection.close()

    def uploadReport0(self, connection, successful=True):
        payload = b'\xff' if successful else b'\x00'
        self.send(connection, 4, payload)

    def requestFragment0(self, peer, filehash, username):
        """
        shaFilename and username have to be a byte-object (Py3)
        [str in py2]
        Returns True if successful
        """
        n = bs.int2byte(len(username))
        payload = b''.join((filehash, n, username))
        try:
            connection = self.connectToServer(peer)
        except ConnectionRefusedError:
            self.removePeer(peer)
            self.logger.info("Could not request fragment")
            return False
        try:
            self.send(connection, 5, payload)
            reply = self.receive(connection)
            self.logger.debug("Requested fragment: {}".format(reply))
            return self.handleAccordingly(connection, reply, 6)
        except FileNotFoundError:
            return False
        finally:
            connection.close()

    def sendFragment0(self, connection, data=b''):
        """
        Sends a fragment to the connection. If a fragment is not available
        a message with payload 0 will be sent.
        """
        self.logger.info("Send fragment")
        if data and len(data) > 20:
            n = struct.pack("!I", len(data))
            payload = b''.join((n, data))
            self.send(connection, 6, payload)
        else:
            self.send(connection, 6, b'\x00')

    def searchRequest0(self, hashfilename, username):
        n = bs.int2byte(len(username))
        try:
            username = username.encode()
        except AttributeError:
            pass
        payload = b''.join((hashfilename, n, username))
        toRemove = []
        for i in self.peers:
            try:
                connection = self.connectToServer(i)
            except ConnectionRefusedError:
                toRemove.append(i)
                continue
            try:
                self.send(connection, 7, payload)
                reply = self.receive(connection)
                self.handleAccordingly(connection, reply, 8)
            finally:
                connection.close()
        for i in toRemove:
            self.removePeer(i)

    def searchResults0(self, connection, hashfilename, username):
        try:
            files = self.fileManager.getFragmentDict(username, hashfilename)
            results = json.dumps({"username": username,
                                  "files": files}).encode()
            payload = struct.pack("!I", len(results)) + results
            self.send(connection, 8, payload)
        except (FileNotFoundError, OSError):
            pass

    def checkPeer0(self, peer):
        """
        Checks if peer is still online and answers.
        """
        try:
            connection = self.connectToServer(peer)
            try:
                self.send(connection, 255, b'')
                reply = self.isCirrolus(self.receive(connection, 10))
                if not reply:
                    self.removePeer(peer)
            finally:
                connection.close()
        except ConnectionRefusedError:
            self.removePeer(peer)


# For testing purpose
if __name__ == '__main__':
    import sys
    import hashlib
    from functools import partial
    if sys.version < '3':
        input = raw_input
        range = xrange

    def check(peerObject, interval=60):
        time.sleep(2)    # Wait until peerObject runs
        while peerObject.running:
            for i in peerObject.peers:
                peerObject.checkPeer0(i)
            time.sleep(interval)

    def parse(peerObject, string):
        action, values = string.split()[0], string.split()[1:]
        action = action.lower()
        if action == 'join':
            if len(values) == 1:
                ip = "127.0.0.1"
                port = int(values[0])
            elif len(values) == 2:
                ip = values[0]
                port = int(values[1])
            try:
                peerObject.joinNet0((ip, port))
            except:
                print("Didn't connect")
        elif action == 'send':
            ip = "127.0.0.1"
            try:
                port = int(values[0])
                if peerObject.peers:
                    data = b''
                    with open(values[1], 'rb') as f:
                        for b in iter(partial(f.read, 512), b''):
                            data = b''.join((data, b))
                    try:
                        if peerObject.uploadFragment0((ip, port), data):
                            print("success")
                        else:
                            raise IOError
                    except IOError:
                        print("sending failed")
                else:
                    print("Not connected")
            except (IndexError, ValueError):
                print("send [port] message")

        elif action == 'request':
            try:
                port = int(values[0])
                ip = "127.0.0.1"
                if peerObject.peers:
                    name = values[1].encode()
                    hash = binascii.unhexlify(values[2].encode())
                    peerObject.requestFragment0((ip, port), hash, name)
                else:
                    print("Not connected")
            except IndexError:
                print("request [port] name hash")

        elif action == 'search':
            try:
                hash = hashlib.sha256(values[1].encode()).digest()
            except IndexError:
                hash = bs.int2bytes(0, 32)
            try:
                if peerObject.peers:
                    name = values[0]
                    peerObject.searchRequest0(hash, name)
                    print(peerObject.latestSearchResults)
                else:
                    print("Not connected")
            except IndexError:
                print("search name file")
        elif action == 'list':
            print(peerObject.peers)
        elif action == 'leave':
            peerObject.leaveNet0()
            p.running = False
        else:
            print("Unknown command")

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    try:
        port = int(sys.argv[1])
    except:
        print("""Usage: {} PORT\n
Commands:
        join PORT
        send PORT data
        request [port] name hash
        leave""".format(sys.argv[0]))
        sys.exit(0)
    p = CirrolusPeerV1("127.0.0.1", port, logger=logger)
    t = threading.Thread(target=p.run)
    t1 = threading.Thread(target=check, args=(p,))
    t.start()
    t1.start()

    time.sleep(0.5)

    while p.running:
        userInput = input("> ").strip()
        if userInput:
            parse(p, userInput)
