"""Hand-authored test data, NOT a captured Resonite scene or live receipt.

All identifiers are invented local labels. No asset files or asset URIs.
Each call returns fresh dictionaries so tests may safely mutate them.
"""
import copy
import mob_processor as m


def material(culling='Off', identifier='synthetic-reference'):
    return {'id': identifier, 'componentType': m.TOON, 'members': {
        'Culling': {'$type': 'enum', 'enumType': 'Culling', 'value': culling},
        'MainTexture': {'$type': 'reference', 'targetId': 'synthetic-texture'},
        'NormalMap': {'$type': 'reference', 'targetId': 'synthetic-normal'},
        'Color': {'$type': 'colorX', 'value': {'r': 1, 'g': 1, 'b': 1, 'a': 1}},
        'BlendMode': {'$type': 'enum', 'enumType': 'BlendMode', 'value': 'Opaque'},
        'AlphaClip': {'$type': 'float', 'value': .5},
        'UseVertexColors': {'$type': 'bool', 'value': False},
    }}


def batch():
    source = material('Back', 'synthetic-material')
    reference = material()
    renderer = {'id': 'synthetic-renderer', 'componentType': m.SKIN, 'members': {
        'Materials': {'$type': 'list', 'elements': [
            {'$type': 'reference', 'targetId': source['id']} for _ in range(28)]},
        'Mesh': {'$type': 'reference', 'targetId': 'synthetic-mesh'},
        'Bones': {'$type': 'list', 'elements': [
            {'$type': 'reference', 'targetId': 'synthetic-bone'}]},
    }}
    scene = {'id': 'synthetic-root', 'name': {'value': 'SyntheticMob.glb'},
             'parent': {'targetId': 'Root'}, 'components': [], 'children': [
                 {'id': 'synthetic-child', 'name': {'value': 'Mesh'},
                  'components': [renderer], 'children': []}]}
    return copy.deepcopy((scene, {source['id']: source, reference['id']: reference}, reference))
