#execfile(r'D:\Projects\Dev\pymel\maintenance\compare_caches.py')

import os
import re
import types

import pymel.internal.startup
import pymel.util.arguments as arguments

from pprint import pprint

cachedir = r'D:\Projects\Dev\pymel\pymel\cache'

names = {
    'old': 'mayaApi2020.py',
    'new': 'mayaApi2021.py',
}

caches = {}
for key, cachename in names.items():
    cachepath = os.path.join(cachedir, cachename)
    cache_globals = {}
    data = pymel.internal.startup._pyload(cachepath)
    caches[key] = data

# we only care about the diffs of the classInfo
both, onlyOld, onlyNew, diffs = arguments.compareCascadingDicts(
    caches['old'][-1],
    caches['new'][-1],
    useAddedKeys=True, useChangedKeys=True)

#eliminate known diffs

################################################################################

# # {'methods': {'className': {0: {'doc': ChangedKey('Class name.', 'Returns the name of this class.'),
#                                'returnInfo': {'doc': ChangedKey('', 'Name of this class.')},
#                                'static': ChangedKey(False, True)}},
#              'type': {0: {'doc': ChangedKey('Function set type.', 'Function set type'),
#                           'returnInfo': {'doc': ChangedKey('', 'the class type.')}}}}}


# Doc for 'className' method got more verbose, and it became static
#'className': {0: {'doc': ChangedKey('Class name.', 'Returns the name of this class.')

for clsname, clsDiffs in diffs.items():
    if not isinstance(clsDiffs, dict):
        continue
    methods = clsDiffs.get('methods')
    if not methods:
        continue
    methodDiffs = methods.get('className')
    if not methodDiffs:
        continue
    for overloadIndex, overloadDiffs in methodDiffs.iteritems():
        docDiff = overloadDiffs.get('doc')
        if docDiff and isinstance(docDiff, arguments.ChangedKey):
            if set([
                        docDiff.oldVal.lower().rstrip('.'),
                        docDiff.newVal.lower().rstrip('.'),
                    ]) == set([
                        'class name',
                        'returns the name of this class',
                    ]):
                del overloadDiffs['doc']
        staticDiff = overloadDiffs.get('static')
        if (isinstance(staticDiff, arguments.ChangedKey)
                and not staticDiff.oldVal
                and staticDiff.newVal):
            del overloadDiffs['static']

################################################################################

# It's ok if it didn't use to have a doc, and now it does
def hasNewDoc(arg):
    if not isinstance(arg, dict):
        return False
    doc = arg.get('doc')
    if not doc:
        return False
    if isinstance(doc, arguments.AddedKey):
        return True
    if isinstance(doc, arguments.ChangedKey):
        if not doc.oldVal:
            return True
    return False

def removeDocDiff(arg):
    del arg['doc']
    return arg
arguments.deepPatchAltered(diffs, hasNewDoc, removeDocDiff)

################################################################################

# It's ok if the doc is now longer
# (as long as it doesn't now include "\param" or "\return" codes)
def hasLongerDoc(arg):
    if not isinstance(arg, dict):
        return False
    doc = arg.get('doc')
    if not doc:
        return False
    if isinstance(doc, arguments.ChangedKey):
        if not doc.newVal.startswith(doc.oldVal):
            return False
        extraDoc = doc.newVal[len(doc.oldVal):]
        return '\\param' not in extraDoc and '\\return' not in extraDoc
    return False

arguments.deepPatchAltered(diffs, hasLongerDoc, removeDocDiff)

################################################################################

# ignore changes in only capitalization or punctuation
# ...also strip out any "\\li " or <b>/</b> items
# ...or whitespace length...
PUNCTUATION = """;-'"`,."""
def strip_punctuation(input):
    return input.translate(None, PUNCTUATION)

MULTI_SPACE_RE = re.compile('\s+')

def normalize_str(input):
    result = strip_punctuation(input.lower())
    result = result.replace(' \\li ', ' ')
    result = result.replace('<b>', '')
    result = result.replace('</b>', '')
    result = result.replace('\n', '')
    result = MULTI_SPACE_RE.sub(' ', result)
    return result

def same_after_normalize(input):
    if not isinstance(input, arguments.ChangedKey):
        return False
    if not isinstance(input.oldVal, basestring) or not isinstance(input.newVal, basestring):
        return False
    return normalize_str(input.oldVal) == normalize_str(input.newVal)

def returnNone(input):
    return None

arguments.deepPatchAltered(diffs, same_after_normalize, returnNone)

################################################################################

# {'enums': {'ColorTable': {'valueDocs': {'activeColors': RemovedKey('Colors for active objects.'),
#                                         'backgroundColor': RemovedKey('Colors for background color.'),
#                                         'dormantColors': RemovedKey('Colors for dormant objects.'),
#                                         'kActiveColors': RemovedKey('Colors for active objects.'),
#                                         'kBackgroundColor': RemovedKey('Colors for background color.'),
#                                         'kDormantColors': RemovedKey('Colors for dormant objects.'),
#                                         'kTemplateColor': RemovedKey('Colors for templated objects.'),
#                                         'templateColor': RemovedKey('Colors for templated objects.')}},

# enums are now recorded in a way where there's no documentation for values...
for clsname, clsDiffs in diffs.items():
    if not isinstance(clsDiffs, dict):
        continue
    enums = clsDiffs.get('enums')
    if not enums:
        continue
    for enumName in list(enums):
        enumDiffs = enums[enumName]
        if not isinstance(enumDiffs, dict):
            continue
        valueDocs = enumDiffs.get('valueDocs')
        if not valueDocs:
            continue
        if all(isinstance(val, arguments.RemovedKey) for val in valueDocs.values()):
            del enumDiffs['valueDocs']
        if not enumDiffs:
            del enums[enumName]
    if not enums:
        del clsDiffs['enums']
    if not clsDiffs:
        del diffs[clsname]

################################################################################

# new methods are ok
for clsname, clsDiffs in diffs.items():
    if not isinstance(clsDiffs, dict):
        continue
    methods = clsDiffs.get('methods')
    if not methods or not isinstance(methods, dict):
        continue
    to_remove = []
    for methodName in list(methods):
        methodDiff = methods[methodName]
        if isinstance(methodDiff, arguments.AddedKey):
            del methods[methodName]

################################################################################

# KNOWN PROBLEMS

KNOWN_PROBLEMS = [
    # These methods got removed - need to figure out why
    ('MEulerRotation', 'methods', '__imul__'),
    ('MEulerRotation', 'methods', '__mul__'),
    ('MTime', 'methods', '__imul__'),
    ('MTime', 'methods', '__isub__'),
    ('MTime', 'methods', '__mul__'),
    ('MTime', 'methods', '__ne__'),
    ('MTime', 'methods', '__sub__'),
]

for probKey in KNOWN_PROBLEMS:
    dictsAndKeys = []
    currentItem = diffs
    for piece in probKey:
        dictsAndKeys.append((currentItem, piece))
        currentItem = currentItem[piece]

    for currentItem, piece in reversed(dictsAndKeys):
        del currentItem[piece]
        if currentItem:
            break

################################################################################

# clean up any diff dicts that are now empty
def pruneEmpty(diffs):
    def isempty(arg):
        return isinstance(arg, (dict, list, tuple, set, types.NoneType)) and not arg

    def hasEmptyChildren(arg):
        if not isinstance(arg, dict):
            return False
        return any(isempty(child) for child in arg.values())

    def pruneEmptyChildren(arg):
        keysToDel = []
        for key, val in arg.items():
            if isempty(val):
                keysToDel.append(key)
        for key in keysToDel:
            del arg[key]
        return arg

    altered = True        

    while altered:
        diffs, altered = arguments.deepPatchAltered(diffs, hasEmptyChildren, pruneEmptyChildren)
    return diffs

# afterPrune = pruneEmpty({'foo': 7, 'bar': {5:None, 8:None}})
# print(afterPrune)
diffs = pruneEmpty(diffs)
diff_classes = sorted(diffs)
print(diff_classes)
print(len(diffs))

print('###########')
print(diff_classes[0])
pprint(diffs[diff_classes[0]])