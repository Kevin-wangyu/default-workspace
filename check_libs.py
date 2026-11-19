import importlib
for m in ["sklearn", "scipy", "xgboost", "lightgbm", "pyarrow", "numpy", "pandas", "optuna"]:
    try:
        x = importlib.import_module(m)
        print(m, getattr(x, "__version__", "?"))
    except Exception as e:
        print(m, "MISSING", type(e).__name__)
