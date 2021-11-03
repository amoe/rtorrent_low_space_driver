import libtorrent


class MetadataService:
    """Abstract Class: Interface to a torrent metadata library."""
    def torrent_info(self, path):
        """Extract metadata from torrent file.

        Args:
            path: Path to file, string.
        """
        raise NotImplementedError("not implemented")


class LibtorrentMetadataService(MetadataService):
    """libtorrent-rasterbar torrent metadata."""
    def torrent_info(self, path):
        """See base class."""
        return libtorrent.torrent_info(path)
