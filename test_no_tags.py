"""Synthetic full-CLI apply tests; no network or real scene data."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import mob_processor as m
from synthetic_fixtures import batch


class NoTagsTests(unittest.TestCase):
    def run_apply(self, legacy=False, former_reference=False):
        scene, materials, _ = batch()
        materials['synthetic-material']['members']['BlendMode']['value']='Cutout'
        if former_reference: scene["name"]["value"] = m.REFERENCE
        tag = {'id': 'synthetic-legacy-tag', 'componentType': m.PREFIX+'AI_GeneratedContent',
               'members': {'Source': {'$type': 'string', 'value': 'existing owner text'}}}
        if legacy:
            scene['components'].append(copy.deepcopy(tag))
        renderer = scene['children'][0]['components'][0]
        components = {renderer['id']: renderer, **materials}
        if legacy:
            components[tag['id']] = scene['components'][0]
        calls = []

        class Fixture:
            allow_writes = False
            def __init__(self, *args): pass
            def close(self): pass
            def req(self, typ, **kw):
                calls.append((typ, copy.deepcopy(kw)))
                if typ == 'requestSessionData': return {}
                if typ == 'getSlot':
                    data = ({'id': 'Root', 'name': {'value': 'Root'}, 'children': [scene]}
                            if kw['slotId'] == 'Root' else scene)
                    return {'data': copy.deepcopy(data)}
                if typ == 'getComponent':
                    return {'data': copy.deepcopy(components.get(kw['componentId'], {'id': kw['componentId']}))}
                if typ == 'getComponentDefinition':
                    return {'definition': {'methods': [{'name': 'MergeByMaterial', 'parameters': {}, 'isStatic': False}]}}
                if not self.allow_writes: raise AssertionError('Premature mutation')
                if typ == 'callSyncMethod':
                    renderer['members']['Materials']['elements'] = renderer['members']['Materials']['elements'][:1]
                    renderer['members']['Mesh']['targetId'] = 'synthetic-merged-mesh'
                elif typ == 'addComponent':
                    data = copy.deepcopy(kw['data'])
                    components[data['id']] = data
                    target = scene if kw['containerSlotId'] == scene['id'] else scene['children'][0]
                    target['components'].append(data)
                elif typ == 'updateComponent':
                    components[kw['data']['id']]['members'].update(copy.deepcopy(kw['data']['members']))
                else: raise AssertionError('Unexpected RPC '+typ)
                return {'success': True}

        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp)/'catalog'; catalog.mkdir()
            (catalog/scene['name']['value']).touch()
            with patch.object(m, 'Link', Fixture), patch('builtins.input', return_value='APPLY'), patch('sys.stdout', new_callable=io.StringIO) as out:
                self.assertEqual(m.main(['--host','unused','--port','12345','--catalog-dir',str(catalog),'--select','all','--apply','--output-dir',tmp]), 0)
            receipt = json.loads(next(Path(tmp).glob('run-*/receipt.json')).read_text())
            self.assertIn('BlendMode', out.getvalue())
            self.assertIn('Opaque', out.getvalue())
            bound=components[renderer['members']['Materials']['elements'][0]['targetId']]
            self.assertEqual(bound['members']['BlendMode']['value'],'Opaque')
            self.assertEqual(receipt['renderer_operations'], 1)
            self.assertEqual(receipt['second_pass_operations'], 0)
            self.assertTrue(any(t == 'callSyncMethod' for t, _ in calls))
            # Only isolated material creation is allowed, never tags or license components.
            self.assertEqual([k['data']['componentType'] for t,k in calls if t == 'addComponent'], [m.TOON])
            self.assertNotIn('automation attribution', out.getvalue())
            self.assertFalse(list(Path(tmp).glob('run-*/attribution.json')))
            self.assertNotIn(m.PREFIX+'AI_GeneratedContent', [k['componentType'] for t,k in calls if t == 'getComponentDefinition'])
            self.assertEqual(scene['components'], [tag] if legacy else [])
            if legacy:
                self.assertEqual(components[tag['id']], tag)
                self.assertFalse(any(k.get('data', {}).get('id') == tag['id'] for t,k in calls if t != 'getComponent'))

    def test_former_reference_included_in_normal_apply(self):
        self.run_apply(former_reference=True)

    def test_successful_apply_creates_only_materials(self):
        self.run_apply()

    def test_successful_apply_preserves_legacy_tags(self):
        self.run_apply(legacy=True)


if __name__ == '__main__': unittest.main()
