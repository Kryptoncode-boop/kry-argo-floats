# Argo Environment Setup 

From the `float` directory, create and activate the environment:

```bash
python3 -m venv argo-env
source argo-env/bin/activate
python -m pip install --upgrade pip
python -m pip install argopy numpy pandas matplotlib
```

Run a script from the `files` directory while the environment is active:

```bash
cd files
python med_argo.py
```

In VS Code, choose **Python: Select Interpreter** and select `float/argo-env/bin/python`.

Run `deactivate` to leave the environment. `matplotlib` is only needed for `interpret_argo.py --plot`.
