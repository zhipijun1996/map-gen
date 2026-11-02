"""Pure generation entry point: explicit snapshots in, data result out."""
import copy
from dataclasses import dataclass, field
import time

from .contracts import GenerationRequest, GeneratorConfig, InputError, request_fingerprint, require
from .library import ModuleLibrary, PreparedLibrary
from .solver import StableSolver, SearchFailure, BudgetExhausted, Cancelled
from .audit import audit, configured_connections
from .metrics import actual_paths, quality
from .export import export_runtime


def _not_cancelled():
    return False


@dataclass(frozen=True)
class GenerationHooks:
    clock: object = time.perf_counter
    cancelled: object = _not_cancelled
    on_checkpoint: object = None
    on_failure: object = None


@dataclass
class GenerationResult:
    status: str
    fingerprint: str | None = None
    map: dict | None = None
    content_store: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)

    def to_dict(self):
        return copy.deepcopy(dict(schema='mapgen/generation-result/v1', status=self.status,
                                  request_fingerprint=self.fingerprint, map=self.map, content_store=self.content_store,
                                  metrics=self.metrics, diagnostics=self.diagnostics))


def _generate(request, library, config, *, hooks=None):
    """No file/network access, library mutation, implicit config, fallback or seed substitution.

    Load/validate JSON and the archive at the I/O boundary, then call this function.
    The library can be reused across simultaneous requests with different inputs.
    """
    try:
        require(isinstance(request, GenerationRequest), 'request: expected GenerationRequest')
        require(isinstance(config, GeneratorConfig), 'config: expected GeneratorConfig')
        require(isinstance(library, ModuleLibrary), 'library: expected ModuleLibrary')
        # Validate even objects constructed without the public from_dict helper.
        request = GenerationRequest.from_dict(request.to_dict())
        config = GeneratorConfig.from_dict(config.to_dict())
        prepared = PreparedLibrary(library, request, config)
        fingerprint = request_fingerprint(request, config, library)
        hooks = hooks or GenerationHooks()
        require(isinstance(hooks, GenerationHooks) and callable(hooks.clock) and callable(hooks.cancelled), 'hooks: invalid clock/cancellation callbacks')
        require(all(v is None or callable(v) for v in (hooks.on_checkpoint, hooks.on_failure)), 'hooks: invalid progress callbacks')
    except (InputError, KeyError, TypeError, ValueError) as exc:
        return GenerationResult('INVALID_INPUT', diagnostics=dict(error=dict(type=type(exc).__name__, message=str(exc))))
    params = config.solver_parameters(); gen = StableSolver(request.to_dict()['seed'], prepared, params, hooks)
    gen.on_checkpoint = hooks.on_checkpoint; gen.on_failure = hooks.on_failure
    result = None; error = None; status = 'PASS'
    started = hooks.clock()
    try:
        result = gen.build()
    except Exception as exc:
        status = 'CANCELLED' if isinstance(exc, Cancelled) else 'BUDGET_EXHAUSTED' if isinstance(exc, BudgetExhausted) else 'SEARCH_EXHAUSTED' if isinstance(exc, SearchFailure) else 'ERROR'
        error = dict(type=type(exc).__name__, message=str(exc), phase=gen.phase)
        gen.record_failure(str(exc))
    metrics = dict(expansions=gen.expanded, backtracks=gen.backtracks, layout_repairs=gen.repairs,
                   terminal_states=gen.terminal_states, recorded_failures=len(gen.failures),
                   closed_loops_across_search=gen.closed_loops, pruning=dict(gen.rejections),
                   generation_seconds=hooks.clock() - started)
    diagnostics = dict(error=error, solver_state=dict(seed=gen.seed, phase=gen.phase, instances=copy.deepcopy(gen.items)),
                       decisions=copy.deepcopy(gen.decisions), failures=copy.deepcopy(gen.failures))
    if status != 'PASS':
        return GenerationResult(status, fingerprint=fingerprint, metrics=metrics, diagnostics=diagnostics)
    items = copy.deepcopy(gen.items)
    notes, blockers = prepared.decorate(items); checked = audit(items, prepared, params['reward_target'])
    paths = actual_paths(checked['edges'], params['main_paths_required'])
    q = quality(items, paths, not blockers and not checked['blockers'], params)
    diagnostics.update(physical_notes=notes, blockers=blockers + checked['blockers'], independent_audit=checked, quality=q)
    if not q['effect_pass']:
        return GenerationResult('REJECTED', fingerprint=fingerprint, metrics=metrics, diagnostics=diagnostics)
    connections = [dict(a=a['id']+'.'+ap, b=b['id']+'.'+bp, world2=p['world2'], surface=p['surface'])
                   for (a, ap, p), (b, bp, _) in configured_connections(items)]
    source = dict(instances=items, connections=connections, main_paths=paths, independent_audit=checked, quality=q)
    runtime, content = export_runtime(source, prepared.catalog, request, config, prepared, fingerprint)
    return GenerationResult('PASS', fingerprint=fingerprint, map=runtime, content_store=content, metrics=metrics, diagnostics=diagnostics)


def generate(request, library, config, *, hooks=None):
    """Generate from explicit, immutable snapshots; perform no file/network I/O.

    Returns a typed result for invalid input, cancellation, exhausted search,
    budget exhaustion, rejected audit, success or an unexpected implementation
    error. Failed results never expose a usable map or substitute a seed/goal.
    """
    try:
        return _generate(request, library, config, hooks=hooks)
    except Exception as exc:
        return GenerationResult('ERROR', diagnostics=dict(error=dict(type=type(exc).__name__, message=str(exc))))
