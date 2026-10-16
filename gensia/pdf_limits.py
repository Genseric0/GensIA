"""Fixed, child-only Linux resource limits. These are not an OS sandbox."""
import sys

ADDRESS_SPACE_BYTES = 512 * 1024 * 1024
CPU_SECONDS = 30
FILE_BYTES = 2 * 1024 * 1024


def apply_worker_limits():
    """Call inside the worker before parsing; never change the parent's limits."""
    if not sys.platform.startswith('linux'):
        return {'applied': False, 'platform': sys.platform}
    import resource
    policy = ((resource.RLIMIT_CORE, 'core_bytes', 0),
              (resource.RLIMIT_AS, 'address_space_bytes', ADDRESS_SPACE_BYTES),
              (resource.RLIMIT_CPU, 'cpu_seconds', CPU_SECONDS),
              (resource.RLIMIT_FSIZE, 'file_bytes', FILE_BYTES))
    report = {'applied': True, 'platform': sys.platform}
    for kind, name, requested in policy:
        soft, hard = resource.getrlimit(kind)
        # Never raise an inherited soft or hard limit, even if our cap is larger.
        cap = min([requested] + [value for value in (soft, hard)
                                if value != resource.RLIM_INFINITY])
        resource.setrlimit(kind, (cap, cap))
        if resource.getrlimit(kind) != (cap, cap):
            raise RuntimeError('Não foi possível confirmar o limite do worker PDF.')
        report[name] = cap
    return report


def validate_worker_limits(report):
    """Reject incomplete/false claims before accepting any extracted content."""
    if not isinstance(report, dict) or report.get('platform') != sys.platform:
        return False
    if not sys.platform.startswith('linux'):
        return set(report) == {'applied', 'platform'} and report['applied'] is False
    caps = {'core_bytes': 0, 'address_space_bytes': ADDRESS_SPACE_BYTES,
            'cpu_seconds': CPU_SECONDS, 'file_bytes': FILE_BYTES}
    return (set(report) == {'applied', 'platform', *caps}
            and report['applied'] is True
            and all(type(report[name]) is int and 0 <= report[name] <= maximum
                    for name, maximum in caps.items()))
