import unittest
import mob_processor as m

class SafetyTests(unittest.TestCase):
 def test_selection_is_explicit_bounded_unique(self):
  self.assertEqual(m.select_indices('1,3',3),[0,2])
  self.assertEqual(m.select_indices('all',3),[0,1,2])
  for bad in ['', '0','4','1,1','-1','1-99']:
   with self.assertRaises(ValueError):m.select_indices(bad,3)

class PlanTests(unittest.TestCase):
 def test_former_reference_is_planned_normally(self):
  from synthetic_fixtures import batch
  scene,mats,ref=batch(); scene['name']['value']=m.REFERENCE
  self.assertEqual(len(m.make_plan(scene,mats,ref)),1)
 def test_synthetic_fixture_plan_preserves_source_and_second_pass(self):
  from synthetic_fixtures import batch
  scene,mats,ref=batch()
  plan=m.make_plan(scene,mats,ref)
  self.assertEqual(len(plan),1)
  self.assertTrue(plan[0]['merge'])
  self.assertEqual(plan[0]['before_count'],28)
  source=mats[plan[0]['material_ids'][0]]
  desired=plan[0]['materials'][source['id']]
  self.assertEqual(desired['MainTexture']['targetId'],source['members']['MainTexture']['targetId'])
  self.assertEqual(desired['Color'],m.clean(source['members']['Color']))
  self.assertEqual(desired['Culling']['value'],'Off')
  renderer=next(c for _,s in m.walk(scene) for c in s.get('components') or [] if c['componentType']==m.SKIN)
  renderer['members']['Materials']['elements']=renderer['members']['Materials']['elements'][:1]
  source['members'].update(desired)
  self.assertEqual(m.make_plan(scene,mats,ref),[])

class RuntimeTests(unittest.TestCase):
 def test_apply_uses_native_merge_and_does_not_repeat(self):
  import copy
  r={'id':'r','componentType':m.SKIN,'members':{'Materials':{'$type':'list','elements':[{'$type':'reference','targetId':'mat'}]*3},'Mesh':{'$type':'reference','targetId':'old'},'Bones':{'$type':'list','elements':[{'targetId':'bone'}]}}}
  class Fake:
   def __init__(self):self.calls=[];self.components={'r':copy.deepcopy(r)}
   def req(self,t,**kw):
    self.calls.append((t,kw))
    if t=='getComponent':return {'data':copy.deepcopy(self.components[kw['componentId']])}
    if t=='callSyncMethod':
     self.components['r']['members']['Materials']['elements']=[{'$type':'reference','targetId':'mat'}]
     self.components['r']['members']['Mesh']['targetId']='merged'
    if t=='addComponent':self.components[kw['data']['id']]=copy.deepcopy(kw['data'])
    if t=='updateComponent':self.components[kw['data']['id']]['members'].update(copy.deepcopy(kw['data']['members']))
    return {'success':True}
  f=Fake();op={'path':'/test','slot_id':'slot','renderer_id':'r','merge':True,'before_count':3,'after_count':1,'material_ids':['mat'],'materials':{'mat':{'Culling':{'$type':'enum','value':'Off','enumType':'Culling'},'MainTexture':{'$type':'reference','targetId':'texture'},'Color':{'$type':'colorX','value':{'r':.2}}}},'before_renderer':r}
  m.apply_operations(f,[op])
  self.assertEqual([t for t,_ in f.calls].count('callSyncMethod'),1)
  before=len(f.calls);m.apply_operations(f,[]);self.assertEqual(len(f.calls),before)
  self.assertEqual(f.components['r']['members']['Bones'],r['members']['Bones'])
  new_id=f.components['r']['members']['Materials']['elements'][0]['targetId']
  self.assertEqual(f.components[new_id]['members']['MainTexture']['targetId'],'texture')

class DiscoveryTests(unittest.TestCase):
 def test_duplicate_names_refused_and_order_stable(self):
  roots=[{'id':'b','name':{'value':'b.glb'}},{'id':'a','name':{'value':'a.glb'}}]
  self.assertEqual([s['id'] for s in m.candidates(roots,{'a.glb','b.glb'})],['a','b'])
  with self.assertRaises(ValueError):m.candidates(roots+[roots[0]],{'a.glb','b.glb'})
 def test_native_method_requires_exact_signature(self):
  with self.assertRaises(ValueError):m.verify_merge({'methods':[]})
  with self.assertRaises(ValueError):m.verify_merge({'methods':[{'name':'MergeByMaterial','parameters':{'x':{}},'isStatic':False}]})
  m.verify_merge({'methods':[{'name':'MergeByMaterial','parameters':{},'isStatic':False}]})
 def test_cli_help(self):
  import subprocess,sys
  from pathlib import Path
  p=subprocess.run([sys.executable,str(Path(__file__).parent/'mob_processor.py'),'--help'],capture_output=True,text=True)
  self.assertEqual(p.returncode,0)
  self.assertIn('--host',p.stdout)
  self.assertIn('--dry-run',p.stdout)

class AdditionalSafetyTests(unittest.TestCase):
 def test_parent_user_hierarchy_and_reparent_are_rejected(self):
  with self.assertRaises(ValueError):m.check_parent({'components':[{'componentType':m.PREFIX+'UserRoot'}]})
  m.check_parent({'components':[]})
  old={'id':'a','name':{'value':'import'},'parent':{'targetId':'Root'}}
  with self.assertRaises(ValueError):m.check_identity(old,{**old,'parent':{'targetId':'avatar'}})
  with self.assertRaises(ValueError):m.check_identity(old,{**old,'id':'stale'})
  m.check_identity(old,old)
 def test_changed_renderer_cannot_mutate(self):
  class Fake:
   def req(self,t,**kw):
    if t!='getComponent':raise AssertionError('write attempted')
    return {'data':{'id':'different'}}
  with self.assertRaises(ValueError):m.apply_operations(Fake(),[{'renderer_id':'old','before_renderer':{'id':'old'}}])
 def test_tints_alpha_maps_and_reference_texture_are_preserved(self):
  import copy
  from synthetic_fixtures import material
  ref=material()
  src=copy.deepcopy(ref)
  src['members']['MainTexture']['targetId']='own texture'
  src['members']['Color']['value']['r']=.123
  src['members']['BlendMode']['value']='Alpha'
  src['members']['AlphaClip']['value']=.321
  src['members']['NormalMap']['targetId']='own normal'
  src['members']['Culling']['value']='Back'
  wanted=m.desired_material(src,ref)
  for k in ['MainTexture','Color','AlphaClip','NormalMap']:
   self.assertEqual(wanted[k],m.clean(src['members'][k]))
  self.assertEqual(wanted['Culling']['value'],'Off')
  self.assertEqual(wanted['BlendMode']['value'],'Opaque')
  src['componentType']=m.PREFIX+'PBS_Metallic'
  with self.assertRaises(ValueError):m.desired_material(src,ref)
 def test_truncated_or_avatar_hierarchy_is_rejected(self):
  for slot in [{'name':{'value':'test'},'isReferenceOnly':True},{'name':{'value':'test'},'components':[{'componentType':m.PREFIX+'UserRoot'}]}]:
   with self.assertRaises(ValueError):m.make_plan(slot,{}, {})

if __name__=='__main__':unittest.main()
