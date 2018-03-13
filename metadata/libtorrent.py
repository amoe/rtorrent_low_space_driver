import libtorrent
import metadata

class LibtorrentMetadataService(metadata.MetadataService):
    def torrent_info(path):
        return libtorrent.torrent_info(path)

