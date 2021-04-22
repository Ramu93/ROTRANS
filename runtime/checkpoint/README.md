**Committee-Checkpoint-Incentive:B**


This module covers the logic for the committee creation with VRF, checkpoint creation and stake calculation at
checkpoint(incentive option B form target agreement).

**Development Setup**


Initialize the required submodules and check it out:


    >> git submodule init
    >> git submodule update

Create a virtual environment under ``./.venv`` and activate it:


    >> python3 -m venv .venv
    >> source .venv/bin/activate

In the virtual environment now install the requirements:


    >> pip install -r REQUIREMENTS.txt

Note that the submodule ``./network`` is installed in development mode.
Changes to the code in ``./network`` will automatically reflect in the installation.

**Tests**

To implement all tests of checkpoint module run the following in root directory:
`python -m unittest discover tests`
