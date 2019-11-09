import sys
import rtorrent_xmlrpc

torrent_path = sys.argv[1]

socket_path = "scgi:///home/amoe/.rtorrent.sock"

server = rtorrent_xmlrpc.SCGIServerProxy(socket_path, verbose=True)

start_function = getattr(server, 'load.start')
start_function('', torrent_path)
