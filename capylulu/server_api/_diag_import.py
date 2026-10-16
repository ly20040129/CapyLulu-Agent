import sys, traceback
sys.path.insert(0, r"E:\capylulu")
try:
    import capylulu.server_api.main as m
    print("MAIN_OK")
    print("KB_ROUTES:", sorted({p for p in [getattr(r, "path", None) for r in m.app.routes] if p and "kb" in p}))
except Exception:
    traceback.print_exc()

try:
    import capylulu.tools
    from capylulu.tools.registry import _TOOLS
    print("TOOLS_OK")
    print("KB_TOOLS:", [n for n in _TOOLS if n.startswith("kb_")])
except Exception:
    traceback.print_exc()

import pathlib
print("DATA_KB_EXISTS:", pathlib.Path(r"E:\capylulu\data\kb").exists())
