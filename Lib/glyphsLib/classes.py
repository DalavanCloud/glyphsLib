#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2016 Georg Seifert. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function, unicode_literals
import re
import traceback
import uuid
from glyphsLib.types import (
    transform, point, glyphs_datetime, color, floatToString, readIntlist,
    writeIntlist, needsQuotes, feature_syntax_encode, baseType
)
from glyphsLib.parser import Parser
from glyphsLib.writer import GlyphsWriter
from collections import OrderedDict
from fontTools.misc.py23 import unicode, basestring, StringIO, unichr

__all__ = [
    "GSFont", "GSCustomParameter", "GSInstance", "GSBase",
]


def hint_target(line=None):
    if line is None:
        return None
    if line[0] == "{":
        return point(line)
    else:
        return line


def isString(string):
    return isinstance(string, (str, unicode))


class GSBase(object):
    _classesForName = {}
    _defaultsForName = {}
    _wrapperKeysTranslate = {}

    def __init__(self):
        for key in self._classesForName.keys():
            if not hasattr(self, key):
                try:
                    klass = self._classesForName[key]
                    if issubclass(klass, GSBase):
                        value = []
                    elif key in self._defaultsForName:
                        value = self._defaultsForName.get(key)
                    else:
                        value = klass()
                    setattr(self, key, value)
                except:
                    pass

    def __repr__(self):
        content = ""
        if hasattr(self, "_dict"):
            content = str(self._dict)
        return "<%s %s>" % (self.__class__.__name__, content)

    def classForName(self, name):
        return self._classesForName.get(name, str)

    def __contains__(self, key):
        return hasattr(self, key) and getattr(self, key) is not None

    def __setitem__(self, key, value):
        try:
            if isinstance(value, bytes) and key in self._classesForName:
                new_type = self._classesForName[key]
                if new_type is unicode:
                    value = value.decode('utf-8')
                else:
                    try:
                        value = new_type().read(value)
                    except:
                        value = new_type(value)
            key = self._wrapperKeysTranslate.get(key, key)
            setattr(self, key, value)
        except:
            print(traceback.format_exc())

    def shouldWriteValueForKey(self, key):
        getKey = self._wrapperKeysTranslate.get(key, key)
        value = getattr(self, getKey)
        klass = self._classesForName[key]
        default = self._defaultsForName.get(key, None)
        if default is not None:
            return default != value
        if klass in (int, float, bool) and value == 0:
            return False
        if isinstance(value, baseType) and value.value is None:
            return False
        return True


class Proxy(object):
    def __init__(self, owner):
        self._owner = owner

    def __repr__(self):
        """Return list-lookalike of representation string of objects"""
        strings = []
        for currItem in self:
            strings.append("%s" % (currItem))
        return "(%s)" % (', '.join(strings))

    def __len__(self):
        values = self.values()
        if values is not None:
            return len(values)
        return 0

    def pop(self, i):
        if type(i) == int:
            node = self[i]
            del self[i]
            return node
        else:
            raise(KeyError)

    def __iter__(self):
        values = self.values()
        if values is not None:
            for element in values:
                yield element

    def index(self, value):
        return self.values().index(value)

    def __copy__(self):
        return list(self)

    def __deepcopy__(self, memo):
        return [x.copy() for x in self.values()]

    def setter(self, values):
        method = self.setterMethod()
        if type(values) == list:
            method(values)
        elif (type(values) == tuple or
                values.__class__.__name__ == "__NSArrayM" or
                type(values) == type(self)):
            method(list(values))
        elif values is None:
            method(list())
        else:
            raise TypeError


'''
class LayersIterator:
    def __init__(self, owner):
        self.curInd = 0
        self._owner = owner

    def __iter__(self):
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        if self._owner.parent:
            if self.curInd < len(self._owner.parent.masters):
                FontMaster = self._owner.parent.masters[self.curInd]
                Item = self._owner._layers.get(FontMaster.id, None)
            else:
                if self.curInd >= len(self._owner.layers):
                    raise StopIteration
                ExtraLayerIndex = self.curInd - len(self._owner.parent.masters)
                Index = 0
                ExtraLayer = None
                while ExtraLayerIndex >= 0:
                    ExtraLayer = self._owner._layers.values()[Index]
                    if ExtraLayer.layerId != ExtraLayer.associatedMasterId:
                        ExtraLayerIndex = ExtraLayerIndex - 1
                    Index = Index + 1
                Item = ExtraLayer
            self.curInd += 1
            return Item
        else:
            if self.curInd >= len(self._owner._layers):
                raise StopIteration
            Item = self._owner._layers[self.curInd]
            self.curInd += 1
            return Item
        return None
'''


class FontGlyphsProxy(Proxy):
    """The list of glyphs. You can access it with the index or the glyph name.
    Usage:
        Font.glyphs[index]
        Font.glyphs[name]
        for glyph in Font.glyphs:
        ...
    """
    def __getitem__(self, key):
        if type(key) == slice:
            return self.values().__getitem__(key)

        # by index
        if isinstance(key, int):
            return self._owner._glyphs[key]

        if isinstance(key, basestring):
            # by glyph name
            for glyph in self._owner._glyphs:
                if glyph.name == key:
                    return glyph
            # by string representation as u'ä'
            if len(key) == 1:
                for glyph in self._owner._glyphs:
                    if glyph.unicode == "%04X" % (ord(key)):
                        return glyph
            # by unicode
            else:
                for glyph in self._owner._glyphs:
                    if glyph.unicode == key.upper():
                        return glyph
        return None

    def __setitem__(self, key, glyph):
        if type(key) is int:
            self._owner._setupGlyph(glyph)
            self._owner._glyphs[key] = glyph
        else:
            raise KeyError  # TODO: add other access methods

    def __delitem__(self, key):
        if type(key) is int:
            del(self._owner._glyph[key])
        else:
            raise KeyError  # TODO: add other access methods

    def __contains__(self, item):
        if isString(item):
            raise "not implemented"
        return item in self._owner._glyphs

    def values(self):
        return self._owner._glyphs

    def items(self):
        items = []
        for value in self._owner._glyphs:
            key = value.name
            items.append((key, value))
        return items

    def append(self, glyph):
        self._owner._setupGlyph(glyph)
        self._owner._glyphs.append(glyph)

    def extend(self, objects):
        for glyph in objects:
            self._owner._setupGlyph(glyph)
        self._owner._glyphs.extend(list(objects))

    def __len__(self):
        return len(self._owner._glyphs)

    def setter(self, values):
        if isinstance(values, Proxy):
            values = list(values)
        self._owner._glyphs = values
        for g in self._owner._glyphs:
            g.parent = self._owner
            for layer in g.layers.values():
                if (not hasattr(layer, "associatedMasterId") or
                        layer.associatedMasterId is None or
                        len(layer.associatedMasterId) == 0):
                    g._setupLayer(layer, layer.layerId)


class FontClassesProxy(Proxy):

    def __getitem__(self, key):
        if isinstance(key, (slice, int)):
            return self.values().__getitem__(key)
        if isinstance(key, (str, unicode)):
            for index, klass in enumerate(self.values()):
                if klass.name == key:
                    return self.values()[index]
        raise KeyError

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.values()[key] = value
            value._parent = self._owner
        elif isinstance(key, (str, unicode)):
            for index, klass in enumerate(self.values()):
                if klass.name == key:
                    self.values()[index] = value
                    value._parent = self._owner
        else:
            raise KeyError

    def __delitem__(self, key):
        if isinstance(key, int):
            del self.values()[key]
        elif isinstance(key, (str, unicode)):
            for index, klass in enumerate(self.values()):
                if klass.name == key:
                    del self.values()[index]

    def append(self, item):
        self.values().append(item)
        item._parent = self._owner

    def insert(self, key, item):
        self.values().insert(key, item)
        item._parent = self._owner

    def extend(self, items):
        self.values().extend(items)
        for value in items:
            value._parent = self._owner

    def remove(self, item):
        self.values().remove(item)

    def values(self):
        return self._owner._classes

    def setter(self, values):
        if isinstance(values, Proxy):
            values = list(values)
        self._owner._classes = values
        for value in values:
            value._parent = self._owner


class GlyphLayerProxy(Proxy):
    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.values().__getitem__(key)
        if isinstance(key, int):
            if key < 0:
                key = self.__len__() + key
            # This is how it is handled in Glyphs.app. For now, just use
            # whatever order we have
            '''
            if self._owner.parent:
                masterCount = len(self._owner.parent.masters)
                if key < masterCount:
                    fontMaster = self._owner.parent.masters[key]
                    return self._owner._layers.get(fontMaster.id, None)
                else:
                    extraLayerIndex = key - masterCount
                    index = 0
                    extraLayer = None
                    while extraLayerIndex >= 0:
                        extraLayer = self._owner._layers[index]
                        if extraLayer.layerId != extraLayer.associatedMasterId:
                            extraLayerIndex = extraLayerIndex - 1
                        index = index + 1
                    return extraLayer
            '''
            return list(self._owner._layers.values())[key]
        layer = self._owner._layers.get(key, None)
        if layer is None:
            keyIsMasterId = False
            for master in self._owner.parent.masters:
                if master.id == key:
                    keyIsMasterId = True
            if keyIsMasterId:
                layer = GSLayer()
                self.__setitem__(key, layer)
        return layer

    def __setitem__(self, key, layer):
        if isinstance(key, int) and self._owner.parent:
            if key < 0:
                key = self.__len__() + key
            master = self._owner.parent.masters[key]
            key = master.id
        self._owner._setupLayer(layer, key)
        self._owner._layers[key] = layer

    def __delitem__(self, key):
        if isinstance(key, int) and self._owner.parent:
            if key < 0:
                key = self.__len__() + key
            Layer = self.__getitem__(key)
            key = Layer.layerId
        del(self._owner._layers[key])

    # def __iter__(self):
    #    return LayersIterator(self._owner)

    def __len__(self):
        return len(self._owner._layers)

    def keys(self):
        return self._owner._layers.keys()

    def values(self):
        return self._owner._layers.values()

    def append(self, layer):
        assert layer is not None
        if not layer.associatedMasterId:
            layer.associatedMasterId = self._owner.parent.masters[0].id
        if not layer.layerId:
            layer.layerId = uuid.uuid4()
        self._owner._setupLayer(layer, layer.layerId)
        self._owner._layers[layer.layerId] = layer

    def extend(self, layers):
        for layer in layers:
            self.append(layer)

    def remove(self, layer):
        return self._owner.removeLayerForKey_(layer.layerId)

    def insert(self, index, layer):
        self.append(layer)

    def setter(self, values):
        newLayers = OrderedDict()
        if (type(values) == list or
                type(values) == tuple or
                type(values) == type(self)):
            for layer in values:
                newLayers[layer.layerId] = layer
        elif type(values) == dict:  # or isinstance(values, NSDictionary)
            for (key, layer) in values.items():
                newLayers[layer.layerId] = layer
        else:
            raise TypeError
        for (key, layer) in newLayers.items():
            self._owner._setupLayer(layer, key)
        self._owner._layers = newLayers


class LayerAnchorsProxy(Proxy):

    def __getitem__(self, key):
        if isinstance(key, (slice, int)):
            return self.values().__getitem__(key)
        elif isinstance(key, (str, unicode)):
            for i, a in enumerate(self._owner._anchors):
                if a.name == key:
                    return self._owner._anchors[i]
        else:
            raise KeyError

    def __setitem__(self, key, anchor):
        if isinstance(key, (str, unicode)):
            anchor.name = key
            for i, a in enumerate(self._owner._anchors):
                if a.name == key:
                    self._owner._anchors[i] = anchor
                    return
            anchor._parent = self._owner
            self._owner._anchors.append(anchor)
        else:
            raise TypeError

    def __delitem__(self, key):
        if isinstance(key, int):
            del self._owner._anchors[key]
        elif isinstance(key, (str, unicode)):
            for i, a in enumerate(self._owner._anchors):
                if a.name == key:
                    self._owner._anchors[i]._parent = None
                    del self._owner._anchors[i]
                    return

    def values(self):
        return self._owner._anchors

    def append(self, anchor):
        for i, a in enumerate(self._owner._anchors):
            if a.name == anchor.name:
                anchor._parent = self._owner
                self._owner._anchors[i] = anchor
                return
        if anchor.name:
            self._owner._anchors.append(anchor)
        else:
            raise ValueError("Anchor must have name")

    def extend(self, anchors):
        for anchor in anchors:
            anchor._parent = self._owner
        self._owner._anchors.extend(anchors)

    def remove(self, anchor):
        if isinstance(anchor, (str, unicode)):
            anchor = self.values()[anchor]
        return self._owner._anchors.remove(anchor)

    def insert(self, index, anchor):
        anchor._parent = self._owner
        self._owner._anchors.insert(index, anchor)

    def __len__(self):
        return len(self._owner._anchors)

    def setter(self, anchors):
        if isinstance(anchors, Proxy):
            anchors = list(anchors)
        self._owner._anchors = anchors
        for anchor in anchors:
            anchor._parent = self._owner


class IndexedObjectsProxy(Proxy):
    def __getitem__(self, key):
        if isinstance(key, (slice, int)):
            return self.values().__getitem__(key)
        else:
            raise KeyError

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.values()[key] = value
            value._parent = self._owner
        else:
            raise KeyError

    def __delitem__(self, key):
        if isinstance(key, int):
            del self.values()[key]
        else:
            raise KeyError

    def values(self):
        return getattr(self._owner, self._objects_name)

    def append(self, value):
        self.values().append(value)
        value._parent = self._owner

    def extend(self, values):
        self.values().extend(values)
        for value in values:
            value._parent = self._owner

    def remove(self, value):
        self.values().remove(value)

    def insert(self, index, value):
        self.values().insert(index, value)
        value._parent = self._owner

    def __len__(self):
        return len(self.values())

    def setter(self, values):
        setattr(self._owner, self._objects_name, list(values))
        for value in self.values():
            value._parent = self._owner


class LayerPathsProxy(IndexedObjectsProxy):
    _objects_name = "_paths"

    def __init__(self, owner):
        super(LayerPathsProxy, self).__init__(owner)


class LayerComponentsProxy(IndexedObjectsProxy):
    _objects_name = "_components"

    def __init__(self, owner):
        super(LayerComponentsProxy, self).__init__(owner)


class LayerAnnotationProxy(IndexedObjectsProxy):
    _objects_name = "_annotations"

    def __init__(self, owner):
        super(LayerAnnotationProxy, self).__init__(owner)


class LayerGuideLinesProxy(IndexedObjectsProxy):
    _objects_name = "_guideLines"

    def __init__(self, owner):
        super(LayerGuideLinesProxy, self).__init__(owner)


class PathNodesProxy(IndexedObjectsProxy):
    _objects_name = "_nodes"

    def __init__(self, owner):
        super(PathNodesProxy, self).__init__(owner)


class CustomParametersProxy(Proxy):
    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.values().__getitem__(key)
        if isinstance(key, int):
            return self._owner._customParameters[key]
        else:
            for customParameter in self._owner._customParameters:
                if customParameter.name == key:
                    return customParameter.value
        return None

    def __setitem__(self, key, value):
        Value = self.__getitem__(key)
        if Value is not None:
            Value.value = value
        else:
            parameter = GSCustomParameter(name=key, value=value)
            self._owner._customParameters.append(parameter)

    def __delitem__(self, key):
        if isinstance(key, int):
            del self._owner._customParameters[key]
        elif isinstance(key, basestring):
            for parameter in self._owner._customParameters:
                if parameter.name == key:
                    self._owner._customParameters.remove(parameter)
        else:
            raise KeyError

    def __contains__(self, item):
        if isString(item):
            return self._owner.__getitem__(item) is not None
        return item in self._owner._customParameters

    def __iter__(self):
        for index in range(len(self._owner._customParameters)):
            yield self._owner._customParameters[index]

    def append(self, parameter):
        parameter.parent = self._owner
        self._owner._customParameters.append(parameter)

    def extend(self, parameters):
        for parameter in parameters:
            parameter.parent = self._owner
        self._owner._customParameters.extend(parameters)

    def remove(self, parameter):
        if isString(parameter):
            parameter = self.__getitem__(parameter)
        self._owner._customParameters.remove(parameter)

    def insert(self, index, parameter):
        parameter.parent = self._owner
        self._owner._customParameters.insert(index, parameter)

    def __len__(self):
        return len(self._owner._customParameters)

    def values(self):
        return self._owner._customParameters

    def __setter__(self, parameters):
        for parameter in parameters:
            parameter.parent = self._owner
        self._owner._customParameters = parameters

    def setterMethod(self):
        return self.__setter__


class UserDataProxy(Proxy):

    def __getitem__(self, key):
        return self._owner._userData.get(key)

    def __setitem__(self, key, value):
        if self._owner._userData is not None:
            self._owner._userData[key] = value
        else:
            self._owner._userData = {key: value}

    def __delitem__(self, key):
        if key in self._owner._userData:
            del self._owner._userData[key]

    def __contains__(self, item):
        return item in self._owner._userData.values()

    def __iter__(self):
        for value in self._owner._userData.values():
            yield value

    def values(self):
        return self._owner._userData.values()

    def keys(self):
        return self._owner._userData.keys()

    def get(self, key):
        return self._owner._userData.get(key)

    def setter(self, values):
        self._owner._userData = values


class GSCustomParameter(GSBase):
    _classesForName = {
        "name": unicode,
        "value": None,
    }

    _CUSTOM_INT_PARAMS = frozenset((
        'ascender', 'blueShift', 'capHeight', 'descender', 'hheaAscender',
        'hheaDescender', 'hheaLineGap', 'macintoshFONDFamilyID',
        'openTypeHeadLowestRecPPEM', 'openTypeHheaAscender',
        'openTypeHheaCaretOffset',
        'openTypeHheaCaretSlopeRise', 'openTypeHheaCaretSlopeRun',
        'openTypeHheaDescender', 'openTypeHheaLineGap',
        'openTypeOS2StrikeoutPosition', 'openTypeOS2StrikeoutSize',
        'openTypeOS2SubscriptXOffset', 'openTypeOS2SubscriptXSize',
        'openTypeOS2SubscriptYOffset', 'openTypeOS2SubscriptYSize',
        'openTypeOS2SuperscriptXOffset', 'openTypeOS2SuperscriptXSize',
        'openTypeOS2SuperscriptYOffset', 'openTypeOS2SuperscriptYSize',
        'openTypeOS2TypoAscender', 'openTypeOS2TypoDescender',
        'openTypeOS2TypoLineGap', 'openTypeOS2WeightClass',
        'openTypeOS2WidthClass',
        'openTypeOS2WinAscent', 'openTypeOS2WinDescent',
        'openTypeVheaCaretOffset',
        'openTypeVheaCaretSlopeRise', 'openTypeVheaCaretSlopeRun',
        'openTypeVheaVertTypoAscender', 'openTypeVheaVertTypoDescender',
        'openTypeVheaVertTypoLineGap', 'postscriptBlueFuzz',
        'postscriptBlueShift',
        'postscriptDefaultWidthX', 'postscriptSlantAngle',
        'postscriptUnderlinePosition', 'postscriptUnderlineThickness',
        'postscriptUniqueID', 'postscriptWindowsCharacterSet',
        'shoulderHeight',
        'smallCapHeight', 'typoAscender', 'typoDescender', 'typoLineGap',
        'underlinePosition', 'underlineThickness', 'unitsPerEm',
        'vheaVertAscender',
        'vheaVertDescender', 'vheaVertLineGap', 'weightClass', 'widthClass',
        'winAscent', 'winDescent', 'xHeight', 'year', 'Grid Spacing'))
    _CUSTOM_FLOAT_PARAMS = frozenset((
        'postscriptBlueScale',))

    _CUSTOM_BOOL_PARAMS = frozenset((
        'isFixedPitch', 'postscriptForceBold', 'postscriptIsFixedPitch',
        'Don\u2019t use Production Names', 'DisableAllAutomaticBehaviour',
        'Use Typo Metrics', 'Has WWS Names', 'Use Extension Kerning'))
    _CUSTOM_INTLIST_PARAMS = frozenset((
        'fsType', 'openTypeOS2CodePageRanges', 'openTypeOS2FamilyClass',
        'openTypeOS2Panose', 'openTypeOS2Type', 'openTypeOS2UnicodeRanges',
        'panose', 'unicodeRanges', 'codePageRanges', 'openTypeHeadFlags'))
    _CUSTOM_DICT_PARAMS = frozenset((
        'GASP Table'))

    def __init__(self, name="New Value", value="New Parameter"):
        self.name = name
        self.value = value

    def __repr__(self):
        return "<%s %s: %s>" % \
            (self.__class__.__name__, self.name, self._value)

    def plistValue(self):
        name = self.name
        if needsQuotes(name):
            name = '"%s"' % name
        value = self.value
        if self.name in self._CUSTOM_INT_PARAMS:
            value = str(value)
        elif self.name in self._CUSTOM_FLOAT_PARAMS:
            value = floatToString(value)
        elif self.name in self._CUSTOM_BOOL_PARAMS:
            value = '1' if value else '0'
        elif self.name in self._CUSTOM_INTLIST_PARAMS:
            values = writeIntlist(value)
            if len(values) > 0:
                value = ",\n".join(values)
                value = "(\n%s\n)" % value
            else:
                value = "(\n)"
        # elif self.name == "TTFStems":

        elif isinstance(value, (str, unicode)):
            value = feature_syntax_encode(value)
        elif isinstance(value, list):
            values = []
            for v in value:
                if isinstance(v, (int, float)):
                    v = str(v)
                elif isinstance(v, dict):
                    string = StringIO()
                    writer = GlyphsWriter(fp=string)
                    writer.writeDict(v)
                    v = string.getvalue()
                else:
                    v = str(v)
                    if needsQuotes(v):
                        v = '"%s"' % v
                values.append(v)
            value = ",\n".join(values)
            value = "(\n%s\n)" % value
        elif isinstance(value, dict):
            values = []
            keys = sorted(value.keys())
            for key in keys:
                v = value[key]
                if needsQuotes(key):
                    key = '"%s"' % key
                if needsQuotes(v):
                    v = '"%s"' % v
                values.append("%s = %s;" % (key, v))
            value = "\n".join(values)
            value = "{\n%s\n}" % value
        else:
            raise TypeError

        return "{\nname = %s;\nvalue = %s;\n}" % (name, value)

    def getValue(self):
        return self._value

    def setValue(self, value):
        """Cast some known data in custom parameters."""
        if self.name in self._CUSTOM_INT_PARAMS:
            value = int(value)
        elif self.name in self._CUSTOM_FLOAT_PARAMS:
            value = float(value)
        elif self.name in self._CUSTOM_BOOL_PARAMS:
            value = bool(value)
        elif self.name in self._CUSTOM_INTLIST_PARAMS:
            value = readIntlist(value)
        elif self.name in self._CUSTOM_DICT_PARAMS:
            parser = Parser()
            value = parser.parse(value)
        elif self.name == 'note':
            value = unicode(value)
        self._value = value

    value = property(getValue, setValue)


class GSAlignmentZone(GSBase):

    def __init__(self, pos=0, size=20):
        self.position = pos
        self.size = size

    def read(self, src):
        if src is not None:
            p = point(src)
            self.position = float(p.value[0])
            self.size = float(p.value[1])
        return self

    def __repr__(self):
        return "<%s pos:%g size:%g>" % \
            (self.__class__.__name__, self.position, self.size)

    def __lt__(self, other):
        return (self.position, self.size) < (other.position, other.size)

    def plistValue(self):
        return '"{%s, %s}"' % \
            (floatToString(self.position), floatToString(self.size))


class GSGuideLine(GSBase):
    _classesForName = {
        "alignment": str,
        "angle": float,
        "locked": bool,
        "position": point,
        "showMeasurement": bool,
        "filter": str,
        "name": unicode,
    }
    _parent = None

    def __init__(self):
        super(GSGuideLine, self).__init__()

    def __repr__(self):
        return "<%s x=%.1f y=%.1f angle=%.1f>" % \
            (self.__class__.__name__, self.position[0], self.position[1],
             self.angle)

    @property
    def parent(self):
        return self._parent


class GSPartProperty(GSBase):
    _classesForName = {
         "name": unicode,
         "bottomName": unicode,
         "bottomValue": int,
         "topName": unicode,
         "topValue": int,
    }
    _keyOrder = (
         "name",
         "bottomName",
         "bottomValue",
         "topName",
         "topValue",
    )

    def plistValue(self):
        return ("{\nname = %s;\nbottomName = %s;\nbottomValue = %i;"
                "\ntopName = %s;\ntopValue = %i;\n}" %
                (self.name,  self.bottomName, self.bottomValue,
                 self.topName, self.topValue))


class GSFontMaster(GSBase):
    _classesForName = {
        "alignmentZones": GSAlignmentZone,
        "ascender": float,
        "capHeight": float,
        "custom": unicode,
        "customParameters": GSCustomParameter,
        "customValue": float,
        "descender": float,
        "guideLines": GSGuideLine,
        "horizontalStems": int,
        "id": str,
        "italicAngle": float,
        "userData": dict,
        "verticalStems": int,
        "visible": bool,
        "weight": str,
        "weightValue": float,
        "width": str,
        "widthValue": float,
        "xHeight": float,
    }
    _defaultsForName = {
        "weightValue": 100.0,
        "widthValue": 100.0,
    }
    _wrapperKeysTranslate = {
        "guideLines": "guides"
    }
    _userData = {}

    def __init__(self):
        super(GSFontMaster, self).__init__()
        self._name = None
        self._customParameters = []
        self._weight = "Regular"
        self._width = "Regular"
        self._custom = ""
        self._custom1 = None
        self._custom2 = None
        self.italicAngle = 0.0
        self.customValue = 0.0

    def __repr__(self):
        return '<GSFontMaster "%s" width %s weight %s>' % \
            (self.name, self.widthValue, self.weightValue)

    def shouldWriteValueForKey(self, key):
        if key in ("width", "weight"):
            if getattr(self, key) == "Regular":
                return False
            return True
        return super(GSFontMaster, self).shouldWriteValueForKey(key)

    @property
    def name(self):
        if self._name is not None:
            return self._name
        name = self.customParameters["Master Name"]
        if name is None:
            names = [self._weight, self._width]
            if (self._custom and len(self._custom) and
                    self._custom not in names):
                names.append(self._custom)
            if (self._custom1 and len(self._custom1) and
                    self._custom1 not in names):
                names.append(self._custom1)
            if (self._custom2 and len(self._custom2) and
                    self._custom2 not in names):
                names.append(self._custom2)

            if len(names) > 1:
                names.remove("Regular")

            if abs(self.italicAngle) > 0.01:
                names.add("Italic")
            name = " ".join(list(names))
        self._name = name
        return name

    customParameters = property(
        lambda self: CustomParametersProxy(self),
        lambda self, value: CustomParametersProxy(self).setter(value))

    userData = property(
        lambda self: UserDataProxy(self),
        lambda self, value: UserDataProxy(self).setter(value))

    @property
    def weight(self):
        if self._weight is not None:
            return self._weight
        return "Regular"

    @weight.setter
    def weight(self, value):
        self._weight = value

    @property
    def width(self):
        if self._width is not None:
            return self._width
        return "Regular"

    @width.setter
    def width(self, value):
        self._width = value

    customName = property(
        lambda self: self._custom,
        lambda self, value: setattr(self, "_custom", value))


class GSNode(GSBase):
    _rx = '([-.e\d]+) ([-.e\d]+) (LINE|CURVE|QCURVE|OFFCURVE|n/a)'\
          '(?: (SMOOTH))?'
    MOVE = "move"
    LINE = "line"
    CURVE = "curve"
    OFFCURVE = "offcurve"
    QCURVE = "qcurve"
    _userData = {}
    _parent = None

    def __init__(self, line=None, position=(0, 0), nodetype='line',
                 smooth=False):
        if line is not None:
            m = re.match(self._rx, line).groups()
            self.position = (float(m[0]), float(m[1]))
            self.type = m[2].lower()
            self.smooth = bool(m[3])
        else:
            self.position = position
            self.type = nodetype
            self.smooth = smooth
        self._parent = None

    def __repr__(self):
        content = self.type
        if self.smooth:
            content += " smooth"
        return "<%s %g %g %s>" % \
            (self.__class__.__name__, self.position[0], self.position[1],
             content)

    userData = property(
        lambda self: UserDataProxy(self),
        lambda self, value: UserDataProxy(self).setter(value))

    @property
    def parent(self):
        return self._parent

    def plistValue(self):
        content = self.type.upper()
        if self.smooth:
            content += " SMOOTH"
        return '"%s %s %s"' % \
            (floatToString(self.position[0]), floatToString(self.position[1]),
             content)


class GSPath(GSBase):
    _classesForName = {
        "nodes": GSNode,
        "closed": bool
    }
    _defaultsForName = {
        "closed": True,
    }
    _parent = None

    def __init__(self):
        self._closed = True
        self.nodes = []

    @property
    def parent(self):
        return self._parent

    def shouldWriteValueForKey(self, key):
        if key == "closed":
            return True
        return super(GSPath, self).shouldWriteValueForKey(key)

    nodes = property(
        lambda self: PathNodesProxy(self),
        lambda self, value: PathNodesProxy(self).setter(value))

    # TODO
    @property
    def segments(self):
        raise NotImplementedError

    @segments.setter
    def segments(self, value):
        raise NotImplementedError

    # TODO
    @property
    def direction(self):
        raise NotImplementedError

    @direction.setter
    def direction(self, value):
        raise NotImplementedError


class GSComponent(GSBase):
    _classesForName = {
        "alignment": int,
        "anchor": str,
        "locked": bool,
        "name": unicode,
        "piece": dict,
        "transform": transform,
    }
    _defaultsForName = {
        "transform": (1, 0, 0, 1, 0, 0),
    }
    _parent = None

    # TODO: glyph arg is required
    def __init__(self, glyph="", offset=(0, 0), scale=(1, 1), transform=None):
        super(GSComponent, self).__init__()
        if transform is None:
            if scale != (1, 1) or offset != (0, 0):
                xx, yy = scale
                dx, dy = offset
                self.transform = (xx, 0, 0, yy, dx, dy)
        else:
            self.transform = transform

        if isinstance(glyph, (str, unicode)):
            self.name = glyph
        elif isinstance(glyph, GSGlyph):
            self.name = glyph.name

    def __repr__(self):
        return '<GSComponent "%s" x=%.1f y=%.1f>' % \
            (self.name, self.transform[4], self.transform[5])

    def shouldWriteValueForKey(self, key):
        if key == "piece":
            value = getattr(self, key)
            return len(value) > 0
        return super(GSComponent, self).shouldWriteValueForKey(key)

    @property
    def parent(self):
        return self._parent


class GSAnchor(GSBase):
    _classesForName = {
        "name": unicode,
        "position": point,
    }
    _parent = None

    def __init__(self):
        super(GSAnchor, self).__init__()

    def __repr__(self):
        return '<%s "%s" x=%.1f y=%.1f>' % \
                (self.__class__.__name__, self.name, self.position[0],
                 self.position[1])

    @property
    def parent(self):
        return self._parent


class GSHint(GSBase):
    _classesForName = {
        "horizontal": bool,
        "options": int,  # bitfield
        "origin": point,  # Index path to node
        "other1": point,  # Index path to node for third node
        "other2": point,  # Index path to node for fourth node
        "place": point,  # (position, width)
        "scale": point,  # for corners
        "stem": int,  # index of stem
        "target": hint_target,  # Index path to node or 'up'/'down'
        "type": str,
    }

    # Hint types
    TOPGHOST = -1
    STEM = 0
    BOTTOMGHOST = 1
    TTANCHOR = 2
    TTSTEM = 3
    TTALIGN = 4
    TTINTERPOLATE = 5
    TTDIAGONAL = 6
    TTDELTA = 8
    CORNER = 16
    CAP = 17
    # Hint options
    TTROUND = 0
    TTROUNDUP = 1
    TTROUNDDOWN = 2
    TTDONROUND = 4
    TRIPLE = 128


class GSFeature(GSBase):
    _classesForName = {
        "automatic": bool,
        "code": unicode,
        "name": str,
        "notes": unicode,
        "disabled": bool,
    }

    def __init__(self, name="xxxx", code=""):
        super(GSFeature, self).__init__()
        self.name = name
        self.code = code

    def getCode(self):
        return self._code

    def setCode(self, code):
        replacements = (
            ('\\012', '\n'), ('\\011', '\t'), ('\\U2018', "'"),
            ('\\U2019', "'"), ('\\U201C', '"'), ('\\U201D', '"'))
        for escaped, unescaped in replacements:
            code = code.replace(escaped, unescaped)
        self._code = code
    code = property(getCode, setCode)

    def __repr__(self):
        return '<%s "%s">' % \
            (self.__class__.__name__, self.name)


class GSClass(GSFeature):
    _classesForName = {
        "automatic": bool,
        "code": unicode,
        "name": str,
        "notes": unicode,
        "disabled": bool,
    }
    _parent = None

    def __init__(self, name="xxxx", code=None):
        super(GSClass, self).__init__()
        self.name = name
        if code is not None:
            self.code = code

    def __repr__(self):
        return '<%s "%s">' % \
            (self.__class__.__name__, self.name)

    @property
    def parent(self):
        return self._parent


class GSFeaturePrefix(GSClass):
    pass


class GSAnnotation(GSBase):
    _classesForName = {
        "angle": float,
        "position": point,
        "text": unicode,
        "type": str,
        "width": float,  # the width of the text field or size of the cicle
    }
    _parent = None

    @property
    def parent(self):
        return self._parent


class GSInstance(GSBase):
    _classesForName = {
        "customParameters": GSCustomParameter,
        "exports": bool,
        "instanceInterpolations": dict,
        "interpolationCustom": float,
        "interpolationCustom1": float,
        "interpolationCustom2": float,
        "interpolationWeight": float,
        "interpolationWidth": float,
        "isBold": bool,
        "isItalic": bool,
        "linkStyle": str,
        "manualInterpolation": bool,
        "name": unicode,
        "weightClass": str,
        "widthClass": str,
    }
    _defaultsForName = {
        "exports": True,
        "interpolationWeight": 100,
        "interpolationWidth": 100,
        "weightClass": "Regular",
        "widthClass": "Medium (normal)",
    }
    _keyOrder = (
        "exports",
        "customParameters",
        "interpolationCustom",
        "interpolationCustom1",
        "interpolationCustom2",
        "interpolationWeight",
        "interpolationWidth",
        "instanceInterpolations",
        "isBold",
        "isItalic",
        "linkStyle",
        "manualInterpolation",
        "name",
        "weightClass",
        "widthClass",
    )

    def interpolateFont():
        pass

    def __init__(self):
        self.exports = True
        self.name = "Regular"
        self.weight = "Regular"
        self.width = "Regular"
        self.custom = None
        self.linkStyle = ""
        self.interpolationWeight = 100.0
        self.interpolationWidth = 100.0
        self.interpolationCustom = 0.0
        self.visible = True
        self.isBold = False
        self.isItalic = False
        self.widthClass = "Medium (normal)"
        self.weightClass = "Regular"
        self._customParameters = []

    customParameters = property(
        lambda self: CustomParametersProxy(self),
        lambda self, value: CustomParametersProxy(self).setter(value))

    weightValue = property(
        lambda self: self.interpolationWeight,
        lambda self, value: setattr(self, "interpolationWeight", value))

    widthValue = property(
        lambda self: self.interpolationWidth,
        lambda self, value: setattr(self, "interpolationWidth", value))

    customValue = property(
        lambda self: self.interpolationCustom,
        lambda self, value: setattr(self, "interpolationCustom", value))

    @property
    def familyName(self):
        value = self.customParameters["familyName"]
        if value:
            return value
        return self.parent.familyName

    @familyName.setter
    def familyName(self, value):
        self.customParameters["famiyName"] = value

    @property
    def preferredFamily(self):
        value = self.customParameters["preferredFamily"]
        if value:
            return value
        return self.parent.familyName

    @preferredFamily.setter
    def preferredFamily(self, value):
        self.customParameters["preferredFamily"] = value

    @property
    def preferredSubfamilyName(self):
        value = self.customParameters["preferredSubfamilyName"]
        if value:
            return value
        return self.name

    @preferredSubfamilyName.setter
    def preferredSubfamilyName(self, value):
        self.customParameters["preferredSubfamilyName"] = value

    @property
    def windowsFamily(self):
        value = self.customParameters["styleMapFamilyName"]
        if value:
            return value
        if self.name not in ("Regular", "Bold", "Italic", "Bold Italic"):
            return self.familyName + " " + self.name
        else:
            return self.familyName

    @windowsFamily.setter
    def windowsFamily(self, value):
        self.customParameters["styleMapFamilyName"] = value

    @property
    def windowsStyle(self):
        if self.name in ("Regular", "Bold", "Italic", "Bold Italic"):
            return self.name
        else:
            return "Regular"

    @property
    def windowsLinkedToStyle(self):
        value = self.linkStyle
        return value
        if self.name in ("Regular", "Bold", "Italic", "Bold Italic"):
            return self.name
        else:
            return "Regular"

    @property
    def fontName(self):
        value = self.customParameters["postscriptFontName"]
        if value:
            return value
        # TODO: strip invalid characters
        return "".join(self.familyName.split(" ")) + "-" + self.name

    @fontName.setter
    def fontName(self, value):
        self.customParameters["postscriptFontName"] = value

    @property
    def fullName(self):
        value = self.customParameters["postscriptFullName"]
        if value:
            return value
        return self.familyName + " " + self.name

    @fullName.setter
    def fullName(self, value):
        self.customParameters["postscriptFullName"] = value


class GSBackgroundLayer(GSBase):
    _classesForName = {
        "anchors": GSAnchor,
        "annotations": GSAnnotation,
        "backgroundImage": dict,  # TODO
        "components": GSComponent,
        "guideLines": GSGuideLine,
        "hints": GSHint,
        "paths": GSPath,
        "visible": bool,
    }

    def shouldWriteValueForKey(self, key):
        if key == "backgroundImage":
            value = getattr(self, key)
            return len(value) > 0
        return super(GSBackgroundLayer, self).shouldWriteValueForKey(key)


class GSLayer(GSBase):
    _classesForName = {
        "anchors": GSAnchor,
        "annotations": GSAnnotation,
        "associatedMasterId": str,
        "background": GSBackgroundLayer,
        "backgroundImage": dict,  # TODO
        "color": color,
        "components": GSComponent,
        "guideLines": GSGuideLine,
        "hints": GSHint,
        "layerId": str,
        "leftMetricsKey": unicode,
        "name": unicode,
        "paths": GSPath,
        "rightMetricsKey": unicode,
        "userData": dict,
        "vertWidth": float,
        "visible": bool,
        "width": float,
        "widthMetricsKey": unicode,
    }
    _defaultsForName = {
        "name": "Regular",
        "weight": 600,
    }
    _wrapperKeysTranslate = {
        "guideLines": "guides",
    }
    _userData = {}

    def __init__(self):
        super(GSLayer, self).__init__()
        self._anchors = []
        self._annotations = []
        self._components = []
        self._guideLines = []
        self._paths = []
        self._selection = []

    def __repr__(self):
        name = self.name
        try:
            # assert self.name
            name = self.name
        except:
            name = 'orphan (n)'
        try:
            assert self.parent.name
            parent = self.parent.name
        except:
            parent = 'orphan'
        return "<%s \"%s\" (%s)>" % (self.__class__.__name__, name, parent)

    def shouldWriteValueForKey(self, key):
        if key in ("associatedMasterId", "name"):
            return self.layerId != self.associatedMasterId
        if key in ("width"):
            return True
        if key == "backgroundImage":
            value = getattr(self, key)
            return len(value) > 0
        return super(GSLayer, self).shouldWriteValueForKey(key)

    @property
    def name(self):
        if (self.associatedMasterId and
                self.associatedMasterId == self.layerId and self.parent):
            master = self.parent.parent.masterForId(self.associatedMasterId)
            if master:
                return master.name
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    anchors = property(
        lambda self: LayerAnchorsProxy(self),
        lambda self, value: LayerAnchorsProxy(self).setter(value))

    paths = property(
        lambda self: LayerPathsProxy(self),
        lambda self, value: LayerPathsProxy(self).setter(value))

    components = property(
        lambda self: LayerComponentsProxy(self),
        lambda self, value: LayerComponentsProxy(self).setter(value))

    guideLines = property(
        lambda self: LayerGuideLinesProxy(self),
        lambda self, value: LayerGuideLinesProxy(self).setter(value))

    annotations = property(
        lambda self: LayerAnnotationProxy(self),
        lambda self, value: LayerAnnotationProxy(self).setter(value))

    userData = property(
        lambda self: UserDataProxy(self),
        lambda self, value: UserDataProxy(self).setter(value))


class GSGlyph(GSBase):
    _classesForName = {
        "bottomKerningGroup": str,
        "bottomMetricsKey": str,
        "category": str,
        "color": color,
        "export": bool,
        "glyphname": unicode,
        "lastChange": glyphs_datetime,
        "layers": GSLayer,
        "leftKerningGroup": unicode,
        "leftKerningKey": unicode,
        "leftMetricsKey": unicode,
        "note": unicode,
        "partsSettings": GSPartProperty,
        "production": str,
        "rightKerningGroup": unicode,
        "rightKerningKey": unicode,
        "rightMetricsKey": unicode,
        "script": str,
        "subCategory": str,
        "topKerningGroup": str,
        "topMetricsKey": str,
        "unicode": unicode,
        "userData": dict,
        "vertWidthMetricsKey": str,
        "widthMetricsKey": unicode,
    }
    _wrapperKeysTranslate = {
        "glyphname": "name"
    }
    _defaultsForName = {
        "category": None,
        "color": None,
        "export": True,
        "lastChange": None,
        "leftKerningGroup": None,
        "leftMetricsKey": None,
        "name": None,
        "note": None,
        "rightKerningGroup": None,
        "rightMetricsKey": None,
        "script": None,
        "subCategory": None,
        "userData": None,
        "widthMetricsKey": None,
        "unicode": None,
    }
    _keyOrder = (
        "color",
        "export",
        "glyphname",
        "production",
        "lastChange",
        "layers",
        "leftKerningGroup",
        "leftMetricsKey",
        "widthMetricsKey",
        "vertWidthMetricsKey",
        "note",
        "rightKerningGroup",
        "rightMetricsKey",
        "topKerningGroup",
        "topMetricsKey",
        "bottomKerningGroup",
        "bottomMetricsKey",
        "unicode",
        "script",
        "category",
        "subCategory",
        "userData",
        "partsSettings"
    )
    _userData = {}

    def __init__(self, name=None):
        super(GSGlyph, self).__init__()
        self._layers = OrderedDict()
        self.name = name
        self.parent = None
        self.export = True
        self.selected = False

    def __repr__(self):
        return '<GSGlyph "%s" with %s layers>' % (self.name, len(self.layers))

    layers = property(lambda self: GlyphLayerProxy(self),
                      lambda self, value: GlyphLayerProxy(self).setter(value))

    def _setupLayer(self, layer, key):
        layer.parent = self
        layer.layerId = key
        # TODO use proxy `self.parent.masters[key]`
        if self.parent and self.parent.masterForId(key):
            layer.associatedMasterId = key

    # def setLayerForKey(self, layer, key):
    #     if Layer and Key:
    #         Layer.parent = self
    #         Layer.layerId = Key
    #         if self.parent.fontMasterForId(Key):
    #             Layer.associatedMasterId = Key
    #         self._layers[key] = layer

    def removeLayerForKey_(self, key):
        for layer in list(self._layers):
            if layer == key:
                del self._layers[key]

    @property
    def string(self):
        if self.unicode:
            return unichr(int(self.unicode, 16))

    userData = property(
        lambda self: UserDataProxy(self),
        lambda self, value: UserDataProxy(self).setter(value))


class GSFont(GSBase):
    _classesForName = {
        ".appVersion": int,
        "DisplayStrings": unicode,
        "classes": GSClass,
        "copyright": unicode,
        "customParameters": GSCustomParameter,
        "date": glyphs_datetime,
        "designer": unicode,
        "designerURL": unicode,
        "disablesAutomaticAlignment": bool,
        "disablesNiceNames": bool,
        "familyName": unicode,
        "featurePrefixes": GSFeaturePrefix,
        "features": GSFeature,
        "fontMaster": GSFontMaster,
        "glyphs": GSGlyph,
        "grid": int,
        "gridLength": int,
        "gridSubDivision": int,
        "instances": GSInstance,
        "keepAlternatesTogether": bool,
        "kerning": OrderedDict,
        "manufacturer": unicode,
        "manufacturerURL": unicode,
        "unitsPerEm": int,
        "userData": dict,
        "versionMajor": int,
        "versionMinor": int,
    }
    _wrapperKeysTranslate = {
        ".appVersion": "appVersion",
        "fontMaster": "masters",
        "unitsPerEm": "upm",
    }
    _defaultsForName = {
        "classes": [],
        "customParameters": [],
        "disablesAutomaticAlignment": False,
        "disablesNiceNames": False,
        "gridLength": 1,
        "gridSubDivision": 1,
        "unitsPerEm": 1000,
        "kerning": OrderedDict(),
    }
    _userData = {}

    def __init__(self, path=None):
        super(GSFont, self).__init__()

        self.familyName = "Unnamed font"
        self._versionMinor = 0
        self.versionMajor = 1
        self.appVersion = 0
        self._glyphs = []
        self._masters = []
        self._instances = []
        self._customParameters = []
        self._classes = []
        self.filepath = None

        if path:
            assert isinstance(path, (str, unicode)), \
                "Please supply a file path"
            assert path.endswith(".glyphs"), \
                "Please supply a file path to a .glyphs file"
            fp = open(path)
            p = Parser()
            # logger.info('Parsing .glyphs file')
            print("____loads")
            p.parse_into_object(self, fp.read())
            fp.close()

    def __repr__(self):
        return "<%s \"%s\">" % (self.__class__.__name__, self.familyName)

    def shouldWriteValueForKey(self, key):
        if key in ("unitsPerEm", "versionMinor"):
            return True
        return super(GSFont, self).shouldWriteValueForKey(key)

    def save(self, path=None):
        if self.filepath:
            path = self.filepath
        elif path is None:
            raise ValueError
        writer = GlyphsWriter(path)
        writer.write(self)

    def getVersionMinor(self):
        return self._versionMinor

    def setVersionMinor(self, value):
        """Ensure that the minor version number is between 0 and 999."""
        assert value >= 0 and value <= 999
        self._versionMinor = value

    versionMinor = property(getVersionMinor, setVersionMinor)

    glyphs = property(lambda self: FontGlyphsProxy(self),
                      lambda self, value: FontGlyphsProxy(self).setter(value))

    def _setupGlyph(self, glyph):
        glyph.parent = self
        for layer in glyph.layers.values():
            if (not hasattr(layer, "associatedMasterId") or
                    layer.associatedMasterId is None or
                    len(layer.associatedMasterId) == 0):
                glyph._setupLayer(layer, layer.layerId)

    @property
    def classes(self):
        return self._classes

    @classes.setter
    def classes(self, value):
        self._classes = value
        for g in self._classes:
            g.parent = self

    @property
    def features(self):
        return self._features

    @features.setter
    def features(self, value):
        self._features = value
        for g in self._features:
            g.parent = self

    @property
    def masters(self):
        return self._masters

    @masters.setter
    def masters(self, value):
        self._masters = value
        for m in self._masters:
            m.parent = self

    def masterForId(self, key):
        for master in self._masters:
            if master.id == key:
                return master
        return None

    @property
    def instances(self):
        return self._instances

    @instances.setter
    def instances(self, value):
        self._instances = value
        for i in self._instances:
            i.parent = self

    classes = property(
        lambda self: FontClassesProxy(self),
        lambda self, value: FontClassesProxy(self).setter(value))

    customParameters = property(
        lambda self: CustomParametersProxy(self),
        lambda self, value: CustomParametersProxy(self).setter(value))

    userData = property(
        lambda self: UserDataProxy(self),
        lambda self, value: UserDataProxy(self).setter(value))

    @property
    def kerning(self):
        return self._kerning

    @kerning.setter
    def kerning(self, kerning):
        self._kerning = kerning
        for master_id, master_map in kerning.items():
            for left_glyph, glyph_map in master_map.items():
                for right_glyph, value in glyph_map.items():
                    glyph_map[right_glyph] = float(value)

    @property
    def selection(self):
        return (glyph for glyph in self.glyphs if glyph.selected)

    @property
    def note(self):
        value = self.customParameters["note"]
        if value:
            return value
        else:
            return ""

    @note.setter
    def note(self, value):
        self.customParameters["note"] = value
