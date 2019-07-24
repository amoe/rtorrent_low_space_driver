import libtorrent
import metadata

class LibtorrentMetadataService(metadata.MetadataService):
    def torrent_info(self, path):
        return libtorrent.torrent_info(path)

