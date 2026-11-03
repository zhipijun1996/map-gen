"""Temporary diagnostic instrumentation; not used by candidate or regression."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[2]
import argparse
a=argparse.ArgumentParser();a.add_argument('--source',default='.cache/bench04');a.add_argument('--out',default='.cache/bench04-traced');args=a.parse_args()
source=ROOT/args.source;target=ROOT/args.out
shutil.copytree(source,target,ignore=shutil.ignore_patterns('.godot','build','unused'))
p=target/'addons/mapgen/work_gate.gd';s=p.read_text()
s=s.replace('var _created_usec', 'var trace_stack: Array=[]\nvar trace_self: Dictionary={}\nvar trace_calls: Dictionary={}\nvar trace_clock:=0\nvar _created_usec')
s=s.replace('\t\t_running = true\n\t\tif not _started:', '\t\t_running = true\n\t\ttrace_clock=Time.get_ticks_usec()\n\t\tif not _started:')
s=s.replace('\t\t_running = false\n\tvar elapsed', '\t\ttrace_flush()\n\t\ttrace_clock=0\n\t\t_running = false\n\tvar elapsed')
s=s.replace('"wall_usec": Time.', '"function_self_usec":trace_self.duplicate(),"function_calls":trace_calls.duplicate(),"wall_usec": Time.')
s+='''
func trace_flush():
 if trace_clock>0:
  var now:=Time.get_ticks_usec()
  if not trace_stack.is_empty():trace_self[trace_stack[-1]]=trace_self.get(trace_stack[-1],0)+now-trace_clock
  trace_clock=now
func trace_enter(name: String):
 trace_flush();trace_stack.append(name);trace_calls[name]=trace_calls.get(name,0)+1
func trace_leave():
 trace_flush();trace_stack.pop_back()
'''.replace('\n ', '\n\t').replace('\n\t if ', '\n\t\tif ').replace('\n\t var ', '\n\t\tvar ').replace('\n\t trace_clock=now','\n\t\ttrace_clock=now')
p.write_text(s)
p=target/'addons/mapgen/solver.gd';s=p.read_text()
specs={
 'graph':('occupied: Array, potential := false','occupied,potential','Array'),
 'reachable':('g: Dictionary, start: String','g,start','Dictionary'),
 'configuration_ok':('item: Dictionary, connected: Dictionary','item,connected','bool'),
 'sort_rows':('rows: Array, less: Callable','rows,less','Array'),
 'growth_options':('','','Array'),
 'reservation':('occupied: Array, limit: int, require_boss := false','occupied,limit,require_boss','Array'),
 'exit_features':('item: Dictionary, pin: String, occupied: Array, lookup: Dictionary','item,pin,occupied,lookup','Array'),
 'reward_options':('','','Array')}
for name,(params,args,kind) in specs.items():
 s=s.replace('func '+name+'(', 'func _trace_impl_'+name+'(',1)
 s+=f'\nfunc {name}({params}) -> {kind}:\n\tvar job=owner.get_ref()\n\tjob.trace_enter("{name}")\n\tvar value: {kind}=await _trace_impl_{name}({args})\n\tjob.trace_leave()\n\treturn value\n'
p.write_text(s)
print(target)
