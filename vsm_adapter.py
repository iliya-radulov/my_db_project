from dataclasses import dataclass
from pathlib import Path
import numpy as np

# your existing parser
from parse_vsm_final2 import parse_vsm_file

# import the base.py classes you want to reuse
from  magmeas import MH_major   # adjust if the class name differs


@dataclass
class ParsedVSMData:
    fields: np.ndarray
    moments: np.ndarray
    temps: np.ndarray | None = None
    errors: np.ndarray | None = None
    mass: float | None = None
    ms: float | None = None
    mr: float | None = None
    hc: float | None = None
    ms_per_g: float | None = None
    file: str | None = None


def load_parsed_vsm(file_path: str) -> ParsedVSMData:
    result = parse_vsm_file(file_path)

    if 'error' in result:
        raise ValueError(result['error'])

    fields = np.asarray(result['fields'], dtype=float)
    moments = np.asarray(result['moments'], dtype=float)

    temps = np.asarray(result['temps'], dtype=float) if result.get('temps') else None
    errors = np.asarray(result['errors'], dtype=float) if result.get('errors') else None

    return ParsedVSMData(
        fields=fields,
        moments=moments,
        temps=temps,
        errors=errors,
        mass=result.get('mass'),
        ms=result.get('ms'),
        mr=result.get('mr'),
        hc=result.get('hc'),
        ms_per_g=result.get('ms_per_g'),
        file=result.get('file', str(file_path)),
    )


def build_mhmajor_from_parsed(parsed: ParsedVSMData, path: str | None = None):
    """
    Build an MHmajor-like object from parsed arrays.

    This assumes base.MHmajor can be instantiated with a file path or can be
    created empty and then populated. Adjust the constructor/payload mapping
    to match your actual base.py API.
    """
    obj = MH_major(path or parsed.file)

    # These assignments are the adapter layer.
    # Adjust attribute names to match the actual object model in base.py.
    obj.H_ext = parsed.fields
    obj.H = parsed.fields
    obj.M = parsed.moments

    if parsed.temps is not None:
        obj.T = parsed.temps
    if parsed.errors is not None:
        obj.error = parsed.errors

    if parsed.mass is not None:
        obj.mass = parsed.mass

    return obj


def load_vsm_as_base_object(file_path: str):
    parsed = load_parsed_vsm(file_path)
    return build_mhmajor_from_parsed(parsed, path=file_path)