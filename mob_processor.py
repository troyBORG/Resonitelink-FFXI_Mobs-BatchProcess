"""Owner-selected native ResoniteLink mob processor. Python 3.11+."""
def select_indices(text, count):
    if text == 'all':
        return list(range(count))
    try:
        values = [int(x.strip()) - 1 for x in text.split(',')]
    except ValueError:
        raise ValueError('Select all or comma-separated displayed indices') from None
    if len(set(values)) != len(values) or any(x < 0 or x >= count for x in values):
        raise ValueError('Duplicate or out-of-range selection')
    return sorted(values)

PREFIX = '[FrooxEngine]FrooxEngine.'
SKIN = PREFIX + 'SkinnedMeshRenderer'
TOON = PREFIX + 'XiexeToonMaterial'
REFERENCE = 'ROM_375_102-Original-Idle.glb'
VERSION = '1.2.0'
# Owner recipe: Culling Off and BlendMode Opaque; captures stay private.
# No texture or scene identifiers are embedded in the recipe.
RECORDED_RECIPE = {'componentType': TOON, 'members': {
    'Culling': {'$type': 'enum', 'enumType': 'Culling', 'value': 'Off'},
    'BlendMode': {'$type': 'enum', 'enumType': 'BlendMode', 'value': 'Opaque'}}}

def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k not in {'id', 'targetType'}}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value

def walk(slot, path=''):
    path += '/' + slot['name']['value']
    yield path, slot
    for child in slot.get('children') or []:
        yield from walk(child, path)

def desired_material(source, reference=RECORDED_RECIPE):
    if source['componentType'] != TOON or reference['componentType'] != TOON:
        raise ValueError('Only native XiexeToon imports are verified; other shader conversion is blocked')
    result = {k: clean(v) for k,v in source['members'].items()
              if not k.startswith('_') and k not in {'persistent','UpdateOrder','Enabled','HighPriorityIntegration'}}
    # Clone every other source payload; only these two owner-approved overrides.
    for field, expected in RECORDED_RECIPE['members'].items():
        if clean(reference['members'].get(field)) != expected:
            raise ValueError('Reference '+field+' differs from validated recipe')
        current = result.get(field, {})
        if not isinstance(current, dict) or current.get('$type') != 'enum' or current.get('enumType') != expected['enumType'] or 'value' not in current:
            raise ValueError('Source '+field+' missing or incompatible; no guessed fields')
        result[field] = dict(expected)
    return result

def make_plan(scene, materials, reference):
    plan = []
    for path,slot in walk(scene):
        if slot.get('isReferenceOnly'):
            raise ValueError('Hierarchy truncated; no partial processing')
        if any('UserRoot' in c['componentType'] or 'Avatar' in c['componentType'] for c in slot.get('components') or []):
            raise ValueError('Avatar/user hierarchy rejected')
        for r in slot.get('components') or []:
            if r['componentType'] not in {SKIN, PREFIX+'MeshRenderer'}:
                continue
            ids = [x.get('targetId') for x in r['members']['Materials']['elements']]
            if not ids or None in ids:
                raise ValueError('Empty/null material reference')
            if r['members'].get('MaterialPropertyBlocks',{}).get('elements'):
                raise ValueError('Material property blocks need separate validation')
            unique = list(dict.fromkeys(ids))
            desired = {i:desired_material(materials[i], reference) for i in unique}
            changed = {i:v for i,v in desired.items() if any(clean(materials[i]['members'].get(k)) != x for k,x in v.items())}
            merge = len(ids) != len(unique)
            if merge or changed:
                plan.append({'path':path,'slot_id':slot['id'],'renderer_id':r['id'],
                             'merge':merge,'before_count':len(ids),'after_count':len(unique),
                             'material_ids':unique,'materials':changed,
                             'before_renderer':r})
    return plan

def apply_operations(link, operations):
    import time, uuid
    results = []
    for op in operations:
        rid = op['renderer_id']
        before = link.req('getComponent', componentId=rid)['data']
        if before != op['before_renderer']:
            raise ValueError('Renderer changed since preview; rerun to select again')
        current = before
        if op['merge']:
            link.req('callSyncMethod', targetID=rid, methodName='MergeByMaterial', arguments={})
            deadline = time.monotonic() + 30
            while True:
                current = link.req('getComponent', componentId=rid)['data']
                elements = current['members']['Materials']['elements']
                if len(elements) == op['after_count']:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError('Native merge did not converge. Stop; no material writes performed.')
                time.sleep(.2)
            if [x['targetId'] for x in elements] != op['material_ids']:
                raise RuntimeError('Native merge returned unexpected material ordering; stopped')
            if clean(current['members'].get('Bones')) != clean(before['members'].get('Bones')):
                raise RuntimeError('Bone references changed during native merge; stopped')
            if current['members']['Mesh']['targetId'] == before['members']['Mesh']['targetId']:
                raise RuntimeError('Native merge did not replace mesh provider; stopped')
        mapping = {}
        for source_id, members in op['materials'].items():
            new_id = 'MobProcessor_' + uuid.uuid4().hex
            link.req('addComponent', containerSlotId=op['slot_id'], data={
                'id':new_id,'componentType':TOON,'members':members})
            readback = link.req('getComponent',componentId=new_id)['data']
            if any(clean(readback['members'].get(k)) != v for k,v in members.items()):
                raise RuntimeError('New isolated material failed readback; original binding retained')
            mapping[source_id] = new_id
        if mapping:
            elements = clean(current['members']['Materials']['elements'])
            for element in elements:
                element['targetId'] = mapping.get(element['targetId'],element['targetId'])
            link.req('updateComponent', data={'id':rid,'members':{'Materials':{'$type':'list','elements':elements}}})
            after = link.req('getComponent',componentId=rid)['data']
            if clean(after['members']['Materials']['elements']) != elements:
                raise RuntimeError('Material binding readback failed; stop, inspect journal')
            if clean(after['members'].get('Bones')) != clean(before['members'].get('Bones')):
                raise RuntimeError('Bone references changed; stop, inspect journal')
        else:
            after = current
        results.append({'path':op['path'],'renderer':after,'material_mapping':mapping})
    return results


def check_parent(slot):
    if any('UserRoot' in c['componentType'] or 'Avatar' in c['componentType'] for c in slot.get('components') or []):
        raise ValueError('User/avatar ancestor is outside the import-processing scope')


def check_identity(before, after):
    if any(before.get(k)!=after.get(k) for k in ('id','name','parent')):
        raise ValueError('Import renamed/reparented or identity changed; rediscover')


def candidates(children, names):
    found = sorted([s for s in children if s['name']['value'] in names], key=lambda s:s['name']['value'])
    labels = [s['name']['value'] for s in found]
    if len(labels) != len(set(labels)):
        raise ValueError('Duplicate sibling names are ambiguous; separate/rename imports before running')
    return found


def verify_merge(definition):
    methods = [x for x in definition.get('methods',[]) if x.get('name')=='MergeByMaterial' and x.get('parameters')=={} and x.get('isStatic') is False]
    if len(methods)!=1:
        raise ValueError('BLOCKED: live MeshRenderer does not expose exact instance MergeByMaterial() via Link. No merge or materials will be changed.')


class Link:
    """Persistent connection; never reconnect/replay a potentially executed write."""
    def __init__(self, host, port, journal):
        import socket, websocket
        self.allow_writes = False
        self.journal = journal
        sock = socket.create_connection((host,port),timeout=15)
        # .NET listener rejects a literal IPv6 Host header on some builds.
        header_host = 'localhost' if ':' in host else host
        try:
            self.ws = websocket.create_connection(f'ws://{header_host}:{port}',socket=sock,host=f'{header_host}:{port}',timeout=60,enable_multithread=True)
        except Exception:
            sock.close()
            raise
    def req(self, typ, **kw):
        import json, uuid, time
        if not self.allow_writes and typ not in {'requestSessionData','getSlot','getComponent','getComponentDefinition'}:
            raise PermissionError('Read-only connection rejected RPC: '+typ)
        request = {'$type':typ,'messageId':'mob_'+uuid.uuid4().hex,**kw}
        self.journal.write(json.dumps({'time':time.time(),'request':request})+'\n');self.journal.flush()
        self.ws.send(json.dumps(request))
        while True:
            response = json.loads(self.ws.recv())
            if response.get('sourceMessageId')==request['messageId']:
                break
        self.journal.write(json.dumps({'time':time.time(),'response':response})+'\n');self.journal.flush()
        if not response.get('success'):
            raise RuntimeError(f'{typ}: {response.get("errorInfo")}')
        return response
    def close(self):
        self.ws.close()


def snapshot(link, root):
    scene = link.req('getSlot',slotId=root['id'],depth=12,includeComponentData=True)['data']
    # Expand only boundary stubs encountered beneath this selected import.
    # Every request stays depth-bounded; IDs, parent edges, cycles and total work
    # are checked before any material reads or processing can occur.
    stack = [(scene, 0, None)]
    seen = set()
    requests = 1
    while stack:
        node, depth, parent_id = stack.pop()
        if depth > 128:
            raise ValueError('Import hierarchy exceeds depth 128 safety bound')
        sid = node.get('id')
        if not sid or sid in seen:
            raise ValueError('Hierarchy has missing/duplicate/cyclic slot identity')
        seen.add(sid)
        if len(seen) > 5000:
            raise ValueError('Import hierarchy exceeds 5000-slot safety bound')
        if node.get('isReferenceOnly'):
            if requests >= 256:
                raise ValueError('Hierarchy continuation exceeds 256-request safety bound')
            expanded = link.req('getSlot',slotId=sid,depth=12,includeComponentData=True)['data']
            requests += 1
            if expanded.get('id') != sid or expanded.get('isReferenceOnly'):
                raise ValueError('Hierarchy continuation incomplete or identity changed')
            if parent_id is not None and expanded.get('parent',{}).get('targetId') != parent_id:
                raise ValueError('Hierarchy continuation reparented outside observed edge')
            if 'name' in node and expanded.get('name') != node['name']:
                raise ValueError('Hierarchy continuation renamed')
            node.clear(); node.update(expanded)
        check_parent(node)
        children = node.get('children') or []
        if len(seen) + len(stack) + len(children) > 5000:
            raise ValueError('Import hierarchy exceeds 5000-slot safety bound')
        stack.extend((child, depth+1, sid) for child in reversed(children))
    renderers = [c for _,s in walk(scene) for c in s.get('components') or [] if c['componentType'] in {SKIN,PREFIX+'MeshRenderer'}]
    ids = set(x['targetId'] for r in renderers for x in r['members']['Materials']['elements'])
    if None in ids:
        raise ValueError('Null material')
    mats = {i:link.req('getComponent',componentId=i)['data'] for i in sorted(ids)}
    meshes = {r['members']['Mesh']['targetId'] for r in renderers}
    providers = {i:link.req('getComponent',componentId=i)['data'] for i in meshes if i}
    return {'scene':scene,'materials':mats,'mesh_providers':providers}


def catalog_names(paths, max_files=100000):
    """Recursively discover case-sensitive names, without directory symlink walks."""
    import os
    from pathlib import Path
    paths = [Path(p).absolute() for p in paths]
    for p in paths:
        if any(part.is_symlink() for part in (p, *p.parents)):
            raise ValueError('Catalog directory symlink is not allowed: '+str(p))
    roots = sorted({p.resolve(strict=True) for p in paths}, key=lambda p: (len(p.parts), str(p)))
    selected = []
    for root in roots:
        if root.is_file() and root.suffix.lower() != '.glb':
            continue  # Shell Catalog/* also expands catalog README/metadata files.
        if not root.is_dir():
            raise ValueError('Catalog input must be a directory: '+str(root))
        if not any(root.is_relative_to(parent) for parent in selected):
            selected.append(root)
    files = {}
    hashes = {}
    def digest(p):
        import hashlib
        canonical = p.resolve(strict=True)
        if canonical not in hashes:
            with canonical.open("rb") as stream:
                hashes[canonical] = hashlib.file_digest(stream, "sha256").digest()
        return hashes[canonical]
    count = 0
    def fail(error):
        raise error
    for root in selected:
        for directory, dirs, names in os.walk(root, followlinks=False, onerror=fail):
            dirs[:] = sorted(d for d in dirs if not (Path(directory)/d).is_symlink())
            for name in sorted(names):
                p = Path(directory)/name
                if p.suffix.lower() != '.glb':
                    continue
                if not p.is_file():
                    raise ValueError('Catalog GLB is not a regular file: '+str(p))
                count += 1
                if count > max_files:
                    raise ValueError('Catalog exceeds discovered GLB limit: '+str(max_files))
                if name in files and p.resolve(strict=True) != files[name].resolve(strict=True):
                    if digest(p) != digest(files[name]):
                        raise ValueError("Conflicting GLB filename: "+name)
                files.setdefault(name, p)
    if not files:
        raise ValueError('Catalog contains no GLBs')
    return set(files)


def main(argv=None):
    import argparse, json, os, sys, time
    from pathlib import Path
    ap=argparse.ArgumentParser(description='Manual native import first; select exact catalog siblings, preview, then confirm native merge and isolated XiexeToon materials.')
    ap.add_argument('--version',action='version',version=VERSION)
    ap.add_argument('--host',required=True,help='Link host; desktop local IPv6 listener: ::1')
    ap.add_argument('--port',required=True,type=int)
    ap.add_argument('--catalog-dir',required=True,type=Path,nargs='+',action='extend',help='One or more recursive catalog directories; repeatable, shell globs supported; no asset upload')
    ap.add_argument('--parent-path',default='Root',help='Exact slash-separated slot path, unique at each level')
    ap.add_argument('--reference',default=REFERENCE,help='Exact name used only by --refresh-reference; no normal-batch exclusion')
    ap.add_argument('--refresh-reference',action='store_true',help='Read-only capture of one exact reference; validates recorded Culling Off and BlendMode Opaque, saves evidence and exits without processing')
    ap.add_argument('--select',help='Explicit displayed indices (1,3) or all; omitted prompts')
    ap.add_argument('--select-name',help='One exact candidate name instead of displayed indices')
    ap.add_argument('--dry-run',action='store_true',help='Read-only preview (default unless --apply)')
    ap.add_argument('--apply',action='store_true',help='Prompt APPLY before writes; no unattended yes option')
    ap.add_argument('--output-dir',type=Path,default=Path.home()/'.local/state/ffxi-mob-processor',help='New private run subdirectory holds snapshots and journal')
    args=ap.parse_args(argv)
    if not 1<=args.port<=65535:ap.error('invalid port')
    if args.apply and args.dry_run:ap.error('--apply and --dry-run conflict')
    if args.apply and args.refresh_reference:ap.error('--refresh-reference cannot be combined with --apply')
    if args.select and args.select_name:ap.error('choose --select or --select-name')
    names=catalog_names(args.catalog_dir)
    os.umask(0o077)
    run=args.output_dir/('run-'+str(time.time_ns()));run.mkdir(parents=True,exist_ok=False)
    def save(name,obj):
        (run/name).write_text(json.dumps(obj,indent=2)+'\n')
    print('Evidence:',run,flush=True)
    link=None
    try:
        with (run/'transport.jsonl').open('x') as journal:
            link=Link(args.host,args.port,journal)
            session=link.req('requestSessionData');save('session.json',session)
            print('Resonite',session.get('resoniteVersion'),'Link',session.get('resoniteLinkVersion'))
            parent=link.req('getSlot',slotId='Root',depth=0,includeComponentData=False)['data']
            check_parent(parent)
            parts=args.parent_path.split('/')
            if not parts or parts[0]!='Root' or any(not p for p in parts):raise ValueError('parent path must start Root')
            for part in parts[1:]:
                found=[s for s in parent.get('children') or [] if s['name']['value']==part]
                if len(found)!=1:raise ValueError('Parent path missing/ambiguous: '+part)
                parent=link.req('getSlot',slotId=found[0]['id'],depth=0,includeComponentData=False)['data']
                check_parent(parent)
            # A recorded recipe is portable; reference slots are never prerequisites.
            if args.refresh_reference:
                refs=[s for s in parent.get('children') or [] if s['name']['value']==args.reference]
                if len(refs)!=1:raise ValueError('Exact reference missing/ambiguous under parent')
                reference=snapshot(link,refs[0]);save('reference-capture.json',reference)
                if not reference['materials']:raise ValueError('Reference has no materials')
                for mat in reference['materials'].values():
                    desired_material(mat,mat)
                save('recipe.json',RECORDED_RECIPE)
                print('Reference captured; validated recorded Culling Off and BlendMode Opaque. No recipe expansion. DRY RUN: no world writes.')
                return 0
            roots=candidates(parent.get('children') or [],names)
            refmat=RECORDED_RECIPE
            save('recipe.json',refmat)
            for index,root in enumerate(roots,1):
                print(f"[{index}] {args.parent_path}/{root['name']['value']}")
            if not roots:raise ValueError('No candidate siblings')
            if args.select_name:
                indices=[i for i,s in enumerate(roots) if s['name']['value']==args.select_name]
                if len(indices)!=1:raise ValueError('Selected name missing/ambiguous')
            else:
                indices=select_indices(args.select if args.select is not None else input('Select indices or all (no default): '),len(roots))
            if not 1 <= len(indices) <= 200:
                raise ValueError("Select 1..200 live imports per batch; narrow --select or --parent-path")
            observations={i:snapshot(link,roots[i]) for i in indices}
            definitions={}
            for typ in [SKIN,PREFIX+'MeshRenderer',TOON]:
                definitions[typ]=link.req('getComponentDefinition',componentType=typ)['definition']
            save('reflection.json',definitions)
            verify_merge(definitions[PREFIX+'MeshRenderer'])
            selected=[observations[i] for i in indices]
            save('before.json',selected)
            operations=[op for obs in selected for op in make_plan(obs['scene'],obs['materials'],refmat)]
            save('plan.json',operations)
            for op in operations:
                print(op['path'])
                print('  native MergeByMaterial()' if op['merge'] else '  merge already converged',f"material slots {op['before_count']} -> {op['after_count']}")
                for mid,desired in op['materials'].items():
                    source=next(obs['materials'][mid] for obs in selected if mid in obs['materials'])
                    delta={k:{'before':clean(source['members'].get(k)),'after':v} for k,v in desired.items() if clean(source['members'].get(k))!=v}
                    print('  clone source material locally, preserve all source texture references/tints; changes:',json.dumps(delta,sort_keys=True))
            print(f'Preview: {len(indices)} selected imports; {len(operations)} renderer operations.')
            if not args.apply:
                print('DRY RUN: no world writes.');return 0
            if not operations:
                print('Already converged: no world writes.');return 0
            print('Native merge is non-transactional. Do not edit/move selected objects during this run. Original material assets are not modified. Save your world first.')
            if input('Type APPLY to execute this exact preview: ')!='APPLY':
                print('Cancelled; no world writes.');return 0
            # Re-read selected inputs before writes. Animated bone transforms may move;
            # compare component state and root identity, not unrelated world objects.
            for i in indices:
                fresh=snapshot(link,roots[i])
                check_identity(observations[i]['scene'],fresh['scene'])
                if fresh['materials']!=observations[i]['materials'] or make_plan(fresh['scene'],fresh['materials'],refmat)!=make_plan(observations[i]['scene'],observations[i]['materials'],refmat):
                    raise ValueError('Selected import changed since preview; restart')
            link.allow_writes=True  # Only after --apply, typed APPLY, and revalidation.
            result=apply_operations(link,operations);save('results.json',result)
            after=[snapshot(link,roots[i]) for i in indices];save('after.json',after)
            remaining=[op for obs in after for op in make_plan(obs['scene'],obs['materials'],refmat)]
            if remaining:raise RuntimeError('Post-apply plan is not empty; stopped')
            save('receipt.json',{'selected':[roots[i]['name']['value'] for i in indices],'renderer_operations':len(operations),'second_pass_operations':len(remaining),'reference_mode':'recorded recipe; reference name is not excluded from selection','visual_validation':'owner pending','session':session})
            print('VERIFIED: native merge/material readbacks and empty second-pass plan. Visual/animation/save-reload checks remain owner-side.')
            return 0
    finally:
        if link:link.close()

if __name__=='__main__':
    import sys
    try:
        sys.exit(main())
    except (Exception,KeyboardInterrupt) as exc:
        print(f'STOPPED: {type(exc).__name__}: {exc}. No automatic retry/reconnect; inspect journal, reconnect and rediscover before another selection.',file=sys.stderr)
        sys.exit(2)
