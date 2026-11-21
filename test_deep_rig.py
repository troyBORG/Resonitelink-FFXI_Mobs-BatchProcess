"""Bounded deep-rig continuation with invented slots, no network."""
import copy
import unittest
import mob_processor as m
from synthetic_fixtures import batch

class DeepRigTests(unittest.TestCase):
    def fixture(self, levels=30, mode=None):
        scene, mats, ref = batch()
        original = scene.pop('children')
        node = scene
        for i in range(levels):
            child = {'id':f'bone-{i}','name':{'value':f'Bone {i}'},'parent':{'targetId':node['id']},'children':[], 'components':[]}
            node['children']=[child]; node=child
        node['children']=original
        original[0]['parent']={'targetId':node['id']}
        by_id={s['id']:s for _,s in m.walk(scene)}
        calls=[]
        def clip(s, depth):
            if depth < 0:
                return {k:copy.deepcopy(v) for k,v in s.items() if k in ('id','name','parent')} | {'isReferenceOnly':True}
            result=copy.deepcopy({k:v for k,v in s.items() if k!='children'})
            result['children']=[clip(c,depth-1) for c in s.get('children',[])]
            return result
        class Link:
            def req(self, typ, **kw):
                calls.append((typ,kw))
                if typ=='getSlot':
                    assert kw['slotId'] in by_id and kw['depth']==12
                    result=clip(by_id[kw['slotId']],12)
                    if len(calls)>1:
                        if mode=='stuck': result['isReferenceOnly']=True
                        if mode=='moved': result['parent']={'targetId':'outside'}
                        if mode=='cycle': result['children']=[copy.deepcopy(scene)]
                    return {'data':result}
                if typ=='getComponent': return {'data':mats.get(kw['componentId'],{'id':kw['componentId']})}
                raise AssertionError('Mutation attempted')
        return Link(),scene,mats,ref,calls

    def test_deep_rig_continues_only_selected_boundary_slots(self):
        link,scene,mats,ref,calls=self.fixture()
        result=m.snapshot(link,scene)
        self.assertEqual(len(m.make_plan(result['scene'],result['materials'],ref)),1)
        self.assertEqual(len([c for c in calls if c[0]=='getSlot']),3)
        self.assertFalse(any(s.get('isReferenceOnly') for _,s in m.walk(result['scene'])))

    def test_failed_continuation_is_closed(self):
        for mode in ('stuck','moved','cycle'):
            with self.subTest(mode=mode):
                link,scene,*_=self.fixture(mode=mode)
                with self.assertRaises(ValueError): m.snapshot(link,scene)

    def test_depth_budget_is_closed(self):
        link,scene,*_=self.fixture(levels=140)
        with self.assertRaisesRegex(ValueError,'depth'): m.snapshot(link,scene)

if __name__=='__main__': unittest.main()
