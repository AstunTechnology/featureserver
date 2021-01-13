from vectorformats.Feature import Feature
from vectorformats.Formats.Format import Format

import re

class KML(Format):
    """KML Writer"""

    url = "/"
    layername = "layer"
    title_property = None
    def encode(self, features, **kwargs):
        url = "%s/%s/%s-data.kml" % (self.url, self.layername, self.layername)
        results = ["""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://earth.google.com/kml/2.0" xmlns:fs="http://featureserver.com/ns" xmlns:atom="http://www.w3.org/2005/Atom">
<Document>
<atom:link rel="self" href="%s" type="application/vnd.google-earth.kml+xml" /> 
<Style id="allstyle">
    <LineStyle>
        <width>5</width>
        <color>ff0099ee</color>
    </LineStyle>
    <PolyStyle>
        <color>900099ee</color>
    </PolyStyle>
</Style>
        """ % url]
        for feature in features:
            results.append( self.encode_feature(feature))
        results.append("""</Document>
        </kml>""")
        return "\n".join(results)        
    
    def encode_feature(self, feature):
        "Take a feature, and return an XML string for that feature."
        name = ""
        if self.title_property and self.title_property in feature.properties:
            name = feature.properties[self.title_property]        
        elif "title" in feature.properties:
            name = feature.properties['title']
        description = ""
        if "description" in feature.properties:
            description = "<![CDATA[%s]]>" % feature.properties['description']
        else:    
            desc_fields = ['Properties:'] 
            for key, value in list(feature.properties.items()):
                if key in ["styleUrl", "title"]: continue 
                if isinstance(value, str):
                        value = str(value, "utf-8")
                desc_fields.append( "<b>%s</b>: %s" % (key, value) )
            description = "<![CDATA[%s]]>" % ("<br />".join(desc_fields))   
        
        styleUrl = "#allstyle"
        if "styleUrl" in feature.properties:
            styleUrl = feature.properties['styleUrl']
        
        attr_fields = []
        for key, value in list(feature.properties.items()):
            #key = re.sub(r'\W', '_', key)
            if key in ["title", "description", "styleUrl"]: continue
            attr_value = value
            if isinstance(attr_value, str):
                attr_value = str(attr_value, "utf-8")
            if hasattr(attr_value, "replace"): 
                attr_value = attr_value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            attr_fields.append( "<fs:%s>%s</fs:%s>" % (key, attr_value, key) )
        link = "" 
        if self.url is not None:
            edit_url = "%s/%s/%s.kml" % (self.url, self.layername, feature.id)  
            link = """<atom:link href="%s" type="edit" />""" % edit_url
        
        xml = """
        <Placemark id="%s">
        <name>%s</name>
        <description>%s</description>
        <styleUrl>%s</styleUrl>
        %s
        <Metadata>
          %s
        </Metadata>
        %s
        </Placemark>""" % (feature.id, name, description, styleUrl, link, "\n".join(attr_fields), self.geometry_to_place(feature.geometry)) 
        return xml
    
    def geometry_to_place(self, geometry):
        if geometry['type'] == "Point":
            coords = ",".join(map(str, geometry['coordinates']))
            return "<Point><coordinates>%s</coordinates></Point>" % coords
        elif geometry['type'] == "LineString":
            coords = " ".join([",".join(map(str, x)) for x in geometry['coordinates']])
            return "<LineString><coordinates>%s</coordinates></LineString>" % coords
        elif geometry['type'] == "Polygon":
            coords = " ".join([",".join(map(str, x)) for x in geometry['coordinates'][0]])
            out = """
              <outerBoundaryIs><LinearRing>
              <coordinates>%s</coordinates>
              </LinearRing></outerBoundaryIs>
            """ % coords 
            inner_rings = []
            for inner_ring in geometry['coordinates'][1:]:
                coords = " ".join([",".join(map(str, x)) for x in inner_ring])
                inner_rings.append("""
                  <innerBoundaryIs><LinearRing>
                  <coordinates>%s</coordinates>
                  </LinearRing></innerBoundaryIs>
                """ % coords) 
            return """<Polygon>
              %s %s
              </Polygon>""" % (out, "\n".join(inner_rings))
        else:
            raise Exception("Could not convert geometry of type %s." % geometry['type'])  
    
    def decode(self, data):
            import xml.dom.minidom as m
            actions = []
            
            doc = m.parseString(data)
            entries = doc.getElementsByTagName("Placemark")
            entries.reverse()
            for entry in entries:
                feature_obj = self.entry_to_feature(entry)
                actions.append(feature_obj)
            
            return actions

    def entry_to_feature(self, placemark_dom):
        feature = Feature()
        points = placemark_dom.getElementsByTagName("Point")
        lines = placemark_dom.getElementsByTagName("LineString")
        polys = placemark_dom.getElementsByTagName("Polygon")
        if len(points):
            coords = points[0].getElementsByTagName("coordinates")[0].firstChild.nodeValue.strip().split(",")
            feature.geometry = {'type':'Point', 'coordinates':list(map(float, coords))}
        elif len(lines):
            coordstring = lines[0].getElementsByTagName("coordinates")[0].firstChild.nodeValue.strip()
            coords = coordstring.split(" ")
            coords = [x.split(",") for x in coords]
            feature.geometry = {'type':'LineString', 'coordinates':coords}
        elif len(polys):
            rings = []
            poly = polys[0]
            outer = poly.getElementsByTagName("outerBoundaryIs")[0]
            outer_coordstring = outer.getElementsByTagName("coordinates")[0].firstChild.nodeValue.strip()
            outer_coords = outer_coordstring.split(" ")
            outer_coords = [list(map(float, x.split(","))) for x in outer_coords]
            rings.append(outer_coords)
            inners = poly.getElementsByTagName("innerBoundaryIs")
            for inner in inners:
                inner_coords = inner.getElementsByTagName("coordinates")[0].firstChild.nodeValue.strip().split(" ")
                inner_coords = [list(map(float, x.split(","))) for x in inner_coords]
                rings.append(inner_coords)
            
            feature.geometry = {'type':'Polygon', 'coordinates':rings}
            
        else:
            raise Exception("KML parser only understands points and lines, and polys. You seem to be missing something.") 
        nodeList = placemark_dom.childNodes
        if len(placemark_dom.getElementsByTagName("Metadata")):
            nodeList += placemark_dom.getElementsByTagName("Metadata")[0].childNodes
        for node in nodeList:
            try:
                attr_name = node.tagName.split(":")[-1]
                value = node.firstChild.nodeValue
                if node.tagName not in ['Point', 'LineString', 'Polygon', 'name', 'Metadata'] and not value.startswith("Properties:"):
                    feature.properties[attr_name] = value
            except:
                pass
            
            try:
                feature.properties['title'] = placemark_dom.getElementsByTagName("name")[0].firstChild.nodeValue
            except:
                pass
        
        return feature    
