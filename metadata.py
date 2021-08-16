import libtorrent


class MetadataService:
    def torrent_info(self, path):
        raise NotImplementedError("not implemented")


class LibtorrentMetadataService(MetadataService):
    def torrent_info(self, path):
        return libtorrent.torrent_info(path)
