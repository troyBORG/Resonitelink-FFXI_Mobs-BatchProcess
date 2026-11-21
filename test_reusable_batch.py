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
    def run_batch(self, state, extra=(), confirmation=None, many=False):
        from synthetic_fixtures import batch
        scene, materials, reference = batch()
        root = {'id': scene['id'], 'name': scene['name']}
        ref = {'id': 'protected-reference', 'name': {'value': m.REFERENCE}}
        children = [root]
        if state == 'present': children += [ref]
        if state == 'duplicates': children += [ref, {**ref, 'id': 'duplicate'}]
        if state == 'moved': children += [{'id':'elsewhere','name':{'value':'Elsewhere'},'children':[ref]}]
        if many:
            children.extend({"id":f"extra-{i}","name":{"value":f"Extra{i}.glb"}} for i in range(201))
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
            # Unlisted reference siblings do not affect ordinary batches.
            if '--refresh-reference' in extra: (catalog/m.REFERENCE).touch()
            if many:
                for i in range(201): (catalog/f'Extra{i}.glb').touch()
            second = Path(tmp)/'second'; second.mkdir()
            (second/'Unimported.glb').touch()
            with patch.object(m,'Link',ReadOnlyFixture), patch('sys.stdout',new_callable=io.StringIO) as out, patch('builtins.input',side_effect=AssertionError('Unexpected prompt') if confirmation is None else None,return_value=confirmation):
                code = m.main(['--host','unused','--port','12345','--catalog-dir',str(catalog),str(second),'--catalog-dir',str(catalog),'--select','all','--output-dir',tmp,*extra])
            self.assertEqual(code, 0)
            self.assertNotIn('automation attribution', out.getvalue())
            self.assertNotIn(m.PREFIX+'AI_GeneratedContent', [kw['componentType'] for typ,kw in calls if typ == 'getComponentDefinition'])
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

    def test_selected_limit_before_scene_reads(self):
        with self.assertRaisesRegex(ValueError, "200"):
            self.run_batch("absent", many=True)

    def test_unselected_subtrees_not_read(self):
        self.run_batch("absent", ["--select", "202"], many=True)

    def test_explicit_dry_run_reference_absent(self):
        self.run_batch('absent', ['--dry-run'])

    def test_apply_requires_typed_confirmation_without_reference(self):
        self.run_batch('absent',['--apply'],confirmation='no')

class RecipeTests(unittest.TestCase):
    def test_recipe_changes_only_culling_blend_and_requires_source_fields(self):
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
            if k not in {'Culling','BlendMode'}: self.assertEqual(v,m.clean(src['members'][k]))
        self.assertEqual(wanted['BlendMode']['value'],'Opaque')
        del src['members']['Culling']
        with self.assertRaisesRegex(ValueError,'Culling'): m.desired_material(src,ref)

    def test_cutout_off_changes_but_opaque_off_is_noop(self):
        from synthetic_fixtures import batch
        scene,mats,ref=batch()
        renderer=scene['children'][0]['components'][0]
        renderer['members']['Materials']['elements']=renderer['members']['Materials']['elements'][:1]
        source=mats['synthetic-material']
        source['members']['Culling']['value']='Off'
        source['members']['BlendMode']['value']='Cutout'
        plan=m.make_plan(scene,mats,ref)
        self.assertEqual(len(plan),1)
        self.assertFalse(plan[0]['merge'])
        self.assertEqual(plan[0]['materials'][source['id']]['BlendMode']['value'],'Opaque')
        source['members']['BlendMode']['value']='Opaque'
        self.assertEqual(m.make_plan(scene,mats,ref),[])
        del source['members']['BlendMode']
        with self.assertRaisesRegex(ValueError,'BlendMode'): m.make_plan(scene,mats,ref)

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
