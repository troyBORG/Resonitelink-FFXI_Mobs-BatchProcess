"""CLI regressions using invented synthetic data; transport rejects writes."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import mob_processor as m

BASE = Path(__file__).parent

class ReusableBatchTests(unittest.TestCase):
    def run_batch(self, state, extra=(), confirmation=None):
        from synthetic_fixtures import batch
        scene, materials, reference = batch()
        root = {'id': scene['id'], 'name': scene['name']}
        ref = {'id': 'protected-reference', 'name': {'value': m.REFERENCE}}
        children = [root]
        if state == 'present': children += [ref]
        if state == 'duplicates': children += [ref, {**ref, 'id': 'duplicate'}]
        if state == 'moved': children += [{'id':'elsewhere','name':{'value':'Elsewhere'},'children':[ref]}]
        calls = []
        class ReadOnlyFixture:
            def __init__(self, *args): pass
            def close(self): pass
            def req(self, typ, **kw):
                calls.append((typ, kw))
                if typ == 'requestSessionData': return {}
                if typ == 'getSlot':
                    if kw['slotId'] == 'Root': return {'data': {'id':'Root','name':{'value':'Root'},'children':children}}
                    if kw['slotId'] == scene['id']: return {'data':copy.deepcopy(scene)}
                    if kw['slotId'] == ref['id'] and state == 'present':
                        captured=copy.deepcopy(scene)
                        for _,slot in m.walk(captured):
                            for component in slot.get('components') or []:
                                if component['componentType']==m.SKIN:
                                    component['members']['Materials']['elements']=[{'$type':'reference','targetId':reference['id']}]
                        return {'data':captured}
                    raise AssertionError('Unselected/reference subtree was read')
                if typ == 'getComponent': return {'data':copy.deepcopy(materials.get(kw['componentId'], {'id':kw['componentId']}))}
                if typ == 'getComponentDefinition': return {'definition':{'methods':[{'name':'MergeByMaterial','parameters':{},'isStatic':False}]}}
                raise AssertionError('Mutation RPC: '+typ)
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp)/'catalog'; catalog.mkdir()
            (catalog/scene['name']['value']).touch()
            # Reference filename in allowlist must not make duplicate references candidates.
            (catalog/m.REFERENCE).touch()
            with patch.object(m,'Link',ReadOnlyFixture), patch('sys.stdout',new_callable=io.StringIO) as out, patch('builtins.input',side_effect=AssertionError('Unexpected prompt') if confirmation is None else None,return_value=confirmation):
                code = m.main(['--host','unused','--port','12345','--catalog-dir',str(catalog),'--select','all','--output-dir',tmp,*extra])
            self.assertEqual(code, 0)
            self.assertIn('DRY RUN' if confirmation is None else 'Cancelled',out.getvalue())
            plans = list(Path(tmp).glob('run-*/plan.json'))
            if '--refresh-reference' in extra:
                self.assertEqual(plans,[])
                self.assertEqual(len(list(Path(tmp).glob('run-*/reference-capture.json'))),1)
            else:
                self.assertEqual(len(json.loads(plans[0].read_text())),1)
        return calls

    def test_default_dry_run_reference_absent_moved_or_duplicated(self):
        for state in ('absent','moved','duplicates'):
            with self.subTest(state=state): self.run_batch(state)

    def test_explicit_dry_run_reference_absent(self):
        self.run_batch('absent', ['--dry-run'])

    def test_apply_requires_typed_confirmation_without_reference(self):
        self.run_batch('absent',['--apply'],confirmation='no')

class RecipeTests(unittest.TestCase):
    def test_recipe_changes_only_culling_and_requires_source_field(self):
        from synthetic_fixtures import material
        ref=material()
        src=copy.deepcopy(ref)
        src['members']['Culling']['value']='Back'
        src['members']['BlendMode']['value']='Cutout'
        src['members']['UseVertexColors']['value']=True
        # A non-texture scalar differing from the reference must also survive.
        src['members']['AlphaClip']['value']=.37
        src['members']['ZOffsetFactor']={'$type':'float','value':.23}
        ref['members']['ZOffsetFactor']={'$type':'float','value':0}
        wanted=m.desired_material(src,ref)
        for k,v in wanted.items():
            if k!='Culling': self.assertEqual(v,m.clean(src['members'][k]))
        del src['members']['Culling']
        with self.assertRaisesRegex(ValueError,'Culling'): m.desired_material(src,ref)

    def test_readonly_transport_blocks_mutation_before_send(self):
        link=m.Link.__new__(m.Link)
        link.allow_writes=False
        link.journal=io.StringIO()
        class Socket:
            def send(self,*args): raise AssertionError('Reached transport')
        link.ws=Socket()
        for typ in ['addComponent','updateComponent','callSyncMethod','addSlot','removeSlot']:
            with self.subTest(typ=typ), self.assertRaises(PermissionError): link.req(typ)

class ReferenceCaptureTests(unittest.TestCase):
    run_batch=ReusableBatchTests.run_batch

    def test_capture_present_validated_reference_reads_only(self):
        self.run_batch('present',['--refresh-reference'])

    def test_capture_absent_moved_duplicates_fails_closed(self):
        for state in ('absent','moved','duplicates'):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError,'Exact reference missing/ambiguous'):
                self.run_batch(state,['--refresh-reference'])

if __name__ == '__main__': unittest.main()
