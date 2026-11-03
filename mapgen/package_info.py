"""Release identity; does not change algorithm, request fingerprints or map schemas."""
PACKAGE_VERSION = '0.2.0'
ALGORITHM_ID = 'stable-v2'
IMPLEMENTATION_ID = 'mapgen/interface-v1'
RUNTIME_TARGET = 'python-reference'
SCHEMAS = {
    'request': 'mapgen/generation-request/v1',
    'config': 'mapgen/generator-config/v1',
    'result': 'mapgen/generation-result/v1',
    'map': 'mapgen/runtime-map/v2',
    'content': 'pcg/compiled-module-content/v1',
}
READINESS = {
    'stage': 'reference-only',
    'godot_runtime': 'NOT_IMPLEMENTED',
    'web_runtime': 'NOT_IMPLEMENTED',
    'desktop_game_runtime': 'NOT_IMPLEMENTED',
    'host_integration': 'NOT_VALIDATED',
    'whole_map_physics': 'NOT_RUN',
}
