'''
Created on Nov 3, 2012
    
@author: michel
'''

import os
from lxml import etree

class FilterAttributes(object):
    
    node = None
    
    def __init__(self, node):
        self.node = node
    
    def render(self):
        xslt = etree.parse(os.path.dirname(os.path.abspath(__file__))+"/../../../resources/filterencoding/filter_attributes.xsl")
        transform = etree.XSLT(xslt)
        result = transform(self.node)
        
        elements = result.xpath("//Attributes")
        if len(elements) > 0:
            str_list =  elements[0].text.strip().split(',')
            str_list = [_f for _f in str_list if _f]
            str_list = [x for x in str_list if len(x) > 0]
            return str_list
        return []

