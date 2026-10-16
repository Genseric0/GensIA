"""Read-only capability metadata: not an enforcement test or security approval."""
import argparse
import importlib
import json
import sys

from . import __version__, document_io, pdf_limits


def _worker_capabilities():
    configured = {'address_space_bytes': pdf_limits.ADDRESS_SPACE_BYTES,
                  'cpu_seconds': pdf_limits.CPU_SECONDS, 'file_bytes': pdf_limits.FILE_BYTES,
                  'core_bytes': 0}
    report = {'state': 'unsupported', 'backend': None, 'configured_caps': configured,
              'planned_caps': None, 'enforcement_validated': False, 'limits_changed': False}
    if not sys.platform.startswith('linux'):
        return report
    report['state'], report['backend'] = 'unavailable', 'linux_rlimit'
    try:
        resource = importlib.import_module('resource')
        if not callable(resource.setrlimit):
            return report
        names = {'address_space_bytes': 'RLIMIT_AS', 'cpu_seconds': 'RLIMIT_CPU',
                 'file_bytes': 'RLIMIT_FSIZE', 'core_bytes': 'RLIMIT_CORE'}
        planned = {}
        for name, symbol in names.items():
            soft, hard = resource.getrlimit(getattr(resource, symbol))
            inherited = [value for value in (soft, hard) if value != resource.RLIM_INFINITY]
            if any(type(value) is not int or value < 0 for value in inherited):
                return report
            planned[name] = min([configured[name], *inherited])
        report.update(state='available_unverified', planned_caps=planned)
    except (ImportError, AttributeError, OSError, ValueError, TypeError):
        # Never include exception text, local paths, environment or service bodies.
        return report
    return report


def protection_report():
    """Inspect interpreter capabilities/current rlimits, without opening documents."""
    descriptor_reads = document_io.DESCRIPTOR_READS_SUPPORTED
    worker = _worker_capabilities()
    warnings = ['Não é sandbox, snapshot transacional nem aprovação para uso comercial.']
    if not descriptor_reads:
        warnings.append('Leitura por caminho de compatibilidade: sem a proteção POSIX contra trocas concorrentes.')
    if worker['state'] != 'available_unverified':
        warnings.append('Quotas Linux do worker não confirmadas como disponíveis; o timeout não é uma quota de memória.')
    return {
        'schema_version': 1, 'gensia_version': __version__, 'platform': sys.platform,
        'document_reads': {'mode': 'descriptor_relative' if descriptor_reads else 'path_compatibility',
                           'capability_available': descriptor_reads, 'execution_validated': False,
                           'transactional_snapshot': False},
        'pdf_worker': {'separate_process_implemented': True, 'wall_timeout_implemented': True,
                       'resource_limits': worker},
        'network_requests': False, 'processes_started': False, 'personal_data_accessed': False,
        'limits_changed': False, 'os_sandbox': False, 'commercial_approval': False,
        'warnings': warnings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='GensIA: capacidades de proteção, sem rede ou alterações')
    parser.parse_args(argv)
    print(json.dumps(protection_report(), ensure_ascii=False, indent=2))
    # Success means report produced, never that security requirements passed.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
