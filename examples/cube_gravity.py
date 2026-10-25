"""Minimal FLAC3D 7.0 example: 8 m cube under gravity, Mohr-Coulomb rock.

Run with the runner:  python ../flac3d/runner.py cube_gravity.py
Outputs land next to this file (out/ directory).
"""

import csv
import os

import itasca as it

OUT = "out"


def xyz(value):
    try:
        return (value.x(), value.y(), value.z())
    except Exception:
        return tuple(value)


try:
    os.makedirs(OUT, exist_ok=True)

    it.command("model large-strain off")
    it.command("zone create brick size 8 8 8")
    it.command("zone cmodel assign mohr-coulomb")
    it.command(
        "zone property density 2500 bulk 2.0e9 shear 8.0e8 "
        "friction 32 cohesion 5.0e4 tension 1.0e4"
    )
    it.command("zone gridpoint fix velocity-z range position-z 0")
    it.command("zone gridpoint fix velocity-x range position-x 0")
    it.command("zone gridpoint fix velocity-y range position-y 0")
    it.command("model gravity 0 0 -9.81")
    print("model zones=%d gridpoints=%d" % (it.zone.count(), it.gridpoint.count()))

    it.command("model solve")
    print("solved")

    rows = []
    for gp in it.gridpoint.list():
        pos = xyz(gp.pos())
        disp = xyz(gp.disp())
        rows.append((gp.id(),) + pos + disp)
    with open(os.path.join(OUT, "gridpoint_disp.csv"), "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "x", "y", "z", "ux", "uy", "uz"])
        writer.writerows(rows)
    print("csv rows", len(rows))

    top = max(rows, key=lambda r: r[3])
    print("top gridpoint id=%d z=%.3f uz=%.6e" % (top[0], top[3], top[6]))

    it.command("model save 'out/cube'")
    print("saved out/cube.sav")
except Exception as exc:
    print("EXCEPTION %s: %s" % (type(exc).__name__, exc))
finally:
    it.command("program exit")
