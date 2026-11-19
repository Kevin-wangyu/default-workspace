import importlib
for m in ["matplotlib", "seaborn", "plotly", "jinja2", "PIL", "scipy", "weasyprint"]:
    try:
        x = importlib.import_module(m)
        print(m, getattr(x, "__version__", "?"))
    except Exception as e:
        print(m, "MISSING", type(e).__name__)
