from geomet import wkt
from vectorformats.Feature import Feature
from vectorformats.Formats.Format import Format


class WKT(Format):
    """Converts a single chunk of WKT to a list of 1 feature."""

    def from_wkt(self, geom):
        return from_wkt(geom)

    def decode(self, data):
        features = [
            Feature(1, self.from_wkt(data))
        ]

        return features


def from_wkt(geom):
    """wkt helper: converts from WKT to a GeoJSON-like geometry."""

    return wkt.loads(geom)


def to_wkt(geom):
    """Converts a GeoJSON-like geometry to WKT."""

    return wkt.dumps(geom)
