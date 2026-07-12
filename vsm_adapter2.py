from pathlib import Path
import numpy as np
import mammos_entity as me

from parse_vsm_final2 import parse_vsm_file
from magmeas import MH_major   # adjust import if the class name differs


def build_measurement_collection(parsed, description="Parsed VSM measurement"):
    fields = np.asarray(parsed["fields"], dtype=float)
    moments = np.asarray(parsed["moments"], dtype=float)

    collection = me.EntityCollection(
        description=description,
    )

    collection["H_ext"] = fields
    collection["H"] = fields
    collection["M"] = moments

    if parsed.get("temps"):
        collection["T"] = np.asarray(parsed["temps"], dtype=float)

    if parsed.get("errors"):
        collection["error"] = np.asarray(parsed["errors"], dtype=float)

    if parsed.get("mass") is not None:
        collection["mass"] = parsed["mass"]

    collection["source_file"] = parsed.get("file", "")
    return collection


class MHmajorFromParsed(MH_major):
    def __init__(self, parsed, path=None):
        super().__init__(path or parsed.get("file", "parsed_vsm.dat"))
        self.measurementdata = build_measurement_collection(parsed)